"""Dynamic controller generation from YAML terminal definitions.

This module provides a factory function that generates FastCS controller classes
dynamically from terminal YAML definitions. This enables gradual replacement of
explicit hardware classes with generated ones.

Usage:
    from fastcs_catio.catio_dynamic import get_terminal_controller_class

    # Get or create a controller class for a terminal type
    controller_class = get_terminal_controller_class("EL1004")

    # Use it like any other controller class
    controller = controller_class(name="MOD1", node=node)
"""

from dataclasses import dataclass

from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Int
from fastcs.logging import bind_logger

from catio_terminals.models import SymbolNode
from fastcs_catio.catio_attribute_io import (
    CATioControllerSymbolAttributeIORef,
)
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.terminal_config import (
    get_datatype_for_symbol,
    get_terminal_type,
    load_runtime_symbols,
    symbol_to_ads_name,
    symbol_to_fastcs_name,
)

logger = bind_logger(logger_name=__name__)


@dataclass
class SymbolAdsItem:
    """ADS item for processing data symbols.

    Stores the symbol name for use with CATioControllerSymbolAttributeIORef.

    Args:
        name: The symbol name (e.g., "Channel 1").
    """

    name: str
    type_name: str

    def __str__(self) -> str:
        """Return the symbol name."""
        return self.name

    @property
    def is_coe(self) -> bool:
        """Return False since this is not a CoE item."""
        return False


@dataclass
class CoEAdsItem(SymbolAdsItem):
    """ADS item for CoE (CANopen over EtherCAT) objects.

    Stores the index and subindex as integers for use with
    CATioControllerCoEAttributeIORef.

    Args:
        index: The CoE object index (e.g., 0x8000).
        subindex: The CoE object subindex (e.g., 0x01).
    """

    index: int
    subindex: int

    def __str__(self) -> str:
        """Return the string representation like 'CoE:8000:01'."""
        return f"CoE:{self.index:04X}:{self.subindex:02X}"

    @property
    def is_coe(self) -> bool:
        """Return True since this is a CoE item."""
        return True

    @property
    def index_hex(self) -> str:
        """Return the index as a hex string (e.g., '8000')."""
        return f"{self.index:04X}"

    @property
    def subindex_hex(self) -> str:
        """Return the subindex as a hex string (e.g., '01')."""
        return f"{self.subindex:02X}"


# Type alias for either ADS item type
AdsItem = SymbolAdsItem | CoEAdsItem


# -----------------------------------------------------------------------------
# Dynamic Controller Cache and Helpers
# -----------------------------------------------------------------------------

# Cache of dynamically generated controller classes
_DYNAMIC_CONTROLLER_CACHE: dict[str, type[CATioTerminalController]] = {}


def _add_attribute(
    controller: CATioTerminalController,
    attr_name: str,
    ads_item: AdsItem,
    is_readonly: bool,
    desc: str,
    type_name: Int,
) -> None:
    """Add a FastCS attribute to a controller.

    Args:
        controller: The controller to add the attribute to.
        attr_name: The FastCS attribute name.
        ads_item: The ADS item (CoEAdsItem or SymbolAdsItem).
        is_readonly: Whether the attribute is read-only.
        desc: The attribute description.
        datatype: The FastCS datatype.
    """
    if is_readonly:
        controller.add_attribute(
            attr_name,
            AttrR(
                datatype=type_name,
                io_ref=None,
                group=controller.attr_group_name,
                initial_value=None,
                description=desc,
            ),
        )
    else:
        match ads_item:
            case CoEAdsItem():
                # CoE attributes need address and dtype which aren't available yet.
                # Store the CoEAdsItem; io_ref created when device connects.
                # For now, create without io_ref - populated by bind_io_refs.
                io_ref = None
                # TODO - we will want to make an IORef something like this
                # can we collect enough info from the YAML and the current
                # client to build this?????
                #
                # io_ref = CATioControllerCoEAttributeIORef(
                #     name=ads_item.name,
                #     index=ads_item.index_hex,
                #     subindex=ads_item.subindex_hex,
                #     address=AmsAddress.from_string(
                #         "5.166.203.208.2.1:88"
                #     ),  # Placeholder, real address set later
                #     dtype=np.dtype("uint32"),  # Placeholder, real dtype set later
                # )
            case SymbolAdsItem(name=name):
                io_ref = CATioControllerSymbolAttributeIORef(name)
        controller.add_attribute(
            attr_name,
            AttrRW(
                datatype=type_name,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=desc,
            ),
        )
    controller.ads_name_map[attr_name] = str(ads_item)
    # Store the typed AdsName for later io_ref binding
    ads_names_attr = "ads_names"
    if not hasattr(controller, ads_names_attr):
        setattr(controller, ads_names_attr, {})
    getattr(controller, ads_names_attr)[attr_name] = ads_item


def _generate_coe_attr_name(base_name: str, fallback: str) -> str:
    """Generate a PascalCase attribute name from a base name.

    Args:
        base_name: The base name to convert (e.g., "max_velocity").
        fallback: Fallback name if base_name is invalid (e.g., "CoE8000").

    Returns:
        PascalCase attribute name (e.g., "MaxVelocity").
    """
    attr_name = "".join(
        word.capitalize() for word in base_name.replace("_", " ").split()
    )
    if not attr_name or not attr_name[0].isalpha():
        attr_name = fallback
    return attr_name


def _ensure_unique_coe_name(
    attr_name: str, created_attrs: dict[str, int], max_length: int = 39
) -> str:
    """Ensure CoE attribute name is unique by adding suffix if needed.

    Args:
        attr_name: The proposed attribute name.
        created_attrs: Dict of already-created attribute names.
        max_length: Maximum length before truncation (leaves room for suffix).

    Returns:
        Unique attribute name with suffix if collision detected.
    """
    # Truncate to max_length to leave room for collision suffix
    attr_name = attr_name[:max_length]

    original_name = attr_name
    suffix = 0
    while attr_name in created_attrs:
        if suffix < 10:
            attr_name = f"{original_name}{suffix}"
        else:
            # Use letters after digits exhausted
            attr_name = f"{original_name}{chr(ord('A') + suffix - 10)}"
        suffix += 1
    return attr_name


def _process_coe_subindex(
    coe_obj,
    sub,
    created_coe_attrs: dict[str, int],
    controller: CATioTerminalController,
) -> None:
    """Process a single CoE subindex and add it as an attribute.

    Args:
        coe_obj: The parent CoE object.
        sub: The subindex to process.
        created_coe_attrs: Dict tracking created attribute names.
        controller: The controller to add the attribute to.
    """
    # Skip subindex 0 (count/descriptor, EtherCAT standard)
    if sub.subindex == 0:
        return

    # Generate attribute name from subindex name
    base_name = sub.name if sub.name else f"Sub{sub.subindex:02X}"
    fallback = f"CoE{coe_obj.index:04X}{sub.subindex:02X}"
    attr_name = _generate_coe_attr_name(base_name, fallback)

    # Ensure unique name with collision handling
    attr_name = _ensure_unique_coe_name(attr_name, created_coe_attrs)
    created_coe_attrs[attr_name] = sub.subindex

    # Generate description and ADS name
    desc = f"CoE{coe_obj.index:04X}{sub.subindex:02X}"
    if len(desc) > 40:
        desc = desc[:40]

    is_readonly = (sub.access or coe_obj.access).lower() in ("ro", "read-only")

    datatype = Int()  # TODO: map sub.type_name to FastCS type
    ads_name = CoEAdsItem(
        name=coe_obj.name,
        type_name=coe_obj.type_name,
        index=coe_obj.index,
        subindex=sub.subindex,
    )

    _add_attribute(controller, attr_name, ads_name, is_readonly, desc, datatype)


def _add_symbol_attribute(
    controller: CATioTerminalController, symbol: SymbolNode
) -> None:
    """Add FastCS attributes for a symbol to a controller.

    Handles both single-channel and multi-channel symbols.

    Args:
        controller: The controller to add attributes to.
        symbol: The symbol definition.
    """
    datatype = get_datatype_for_symbol(symbol)
    if symbol.channels > 1:
        # Multi-channel symbol - create one attribute per channel
        for ch in range(1, symbol.channels + 1):
            fastcs_name = symbol_to_fastcs_name(symbol, ch)
            ads_name = SymbolAdsItem(
                symbol_to_ads_name(symbol, ch), type_name=symbol.type_name
            )
            is_readonly = symbol.access is None or "write" not in symbol.access.lower()
            desc = symbol.tooltip or f"{symbol.name_template} ch {ch}"
            _add_attribute(
                controller, fastcs_name, ads_name, is_readonly, desc, datatype
            )
    else:
        # Single-channel symbol
        fastcs_name = symbol_to_fastcs_name(symbol)
        ads_name = SymbolAdsItem(symbol_to_ads_name(symbol), type_name=symbol.type_name)
        is_readonly = symbol.access is None or "write" not in symbol.access.lower()
        desc = symbol.tooltip or symbol.name_template
        _add_attribute(controller, fastcs_name, ads_name, is_readonly, desc, datatype)


def _create_dynamic_controller_class(
    terminal_id: str, terminal_type
) -> type[CATioTerminalController]:
    """Create a dynamic controller class for a terminal type.

    Args:
        terminal_id: Terminal identifier (e.g., "EL1004").
        terminal_type: TerminalType instance with symbol definitions.

    Returns:
        A new controller class that extends CATioTerminalController.
    """
    # Determine io_function from description
    io_function = terminal_type.description or f"{terminal_id} terminal"

    # Get selected symbols only
    selected_symbols = [s for s in terminal_type.symbol_nodes if s.selected]

    # Get applicable runtime symbols for this terminal
    runtime_config = load_runtime_symbols()
    runtime_symbols: list[SymbolNode] = []
    for rs in runtime_config.runtime_symbols:
        if rs.applies_to_terminal(terminal_id, terminal_type.group_type):
            runtime_symbols.append(rs.to_symbol_node())

    # Create the class body
    class_dict: dict[str, object] = {
        "__module__": __name__,
        "__doc__": f"Dynamically generated controller for {terminal_id} terminal.",
        "io_function": io_function,
        "_terminal_id": terminal_id,
        "_selected_symbols": selected_symbols,
        "_runtime_symbols": runtime_symbols,
        "_coe_objects": terminal_type.coe_objects,
    }

    @property
    def coe_objects(self) -> list:
        """Return the list of CoE objects for this terminal."""
        return getattr(self.__class__, "_coe_objects", [])

    class_dict["coe_objects"] = coe_objects

    async def get_io_attributes(self: CATioTerminalController) -> None:
        """
        Get and create all terminal attributes from YAML definition, including CoE.
        """
        initial_attr_count = len(self.attributes)
        await CATioTerminalController.get_io_attributes(self)

        runtime_syms: list[SymbolNode] = getattr(self.__class__, "_runtime_symbols", [])
        pdo_symbols: list[SymbolNode] = getattr(self.__class__, "_selected_symbols", [])
        coe_objects = getattr(self.__class__, "_coe_objects", [])

        # Process runtime symbols first
        for symbol in runtime_syms:
            _add_symbol_attribute(self, symbol)

        # Then process PDO symbols
        for symbol in pdo_symbols:
            _add_symbol_attribute(self, symbol)

        # Add CoE objects and subindices as FastCS attributes
        # Track created attribute names to detect collisions
        created_coe_attrs: dict[str, int] = {}

        for coe_obj in coe_objects:
            # If no subindices, treat as single value
            if not getattr(coe_obj, "subindices", []):
                base_name = coe_obj.name or f"CoE{coe_obj.index:04X}"
                attr_name = _generate_coe_attr_name(
                    base_name, f"CoE{coe_obj.index:04X}"
                )
                desc = f"CoE{coe_obj.index:04X}"
                is_readonly = coe_obj.access.lower() in ("ro", "read-only")
                datatype = Int()  # TODO: map coe_obj.type_name to FastCS type
                ads_name = CoEAdsItem(
                    coe_obj.name, coe_obj.type_name, index=coe_obj.index, subindex=0
                )
                _add_attribute(self, attr_name, ads_name, is_readonly, desc, datatype)
            else:
                # Process each subindex
                for sub in coe_obj.subindices:
                    _process_coe_subindex(coe_obj, sub, created_coe_attrs, self)

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(
            f"Created {attr_count} attributes for dynamic controller {self.name}."
        )

    class_dict["get_io_attributes"] = get_io_attributes

    # Create and return the new class
    new_class = type(
        f"Dynamic{terminal_id}Controller",
        (CATioTerminalController,),
        class_dict,
    )

    return new_class


def get_terminal_controller_class(terminal_id: str) -> type[CATioTerminalController]:
    """Get or create a controller class for a terminal type.

    This factory function returns a dynamically generated controller class
    based on the YAML terminal definition. Classes are cached so only one
    class is created per terminal type.

    Args:
        terminal_id: Terminal identifier (e.g., "EL1004", "EL3104").

    Returns:
        A controller class that extends CATioTerminalController.

    Raises:
        KeyError: If the terminal type is not defined in terminal_types.yaml.
    """
    # Check cache first
    if terminal_id in _DYNAMIC_CONTROLLER_CACHE:
        return _DYNAMIC_CONTROLLER_CACHE[terminal_id]

    # Get the terminal definition
    terminal_type = get_terminal_type(terminal_id)

    # Create the dynamic controller class
    controller_class = _create_dynamic_controller_class(terminal_id, terminal_type)

    # Cache it
    _DYNAMIC_CONTROLLER_CACHE[terminal_id] = controller_class
    logger.info(f"Created dynamic controller class for {terminal_id}")

    return controller_class


def clear_controller_cache() -> None:
    """Clear the dynamic controller cache.

    Useful for testing or when terminal definitions change.
    """
    from fastcs_catio.terminal_config import clear_config_cache

    _DYNAMIC_CONTROLLER_CACHE.clear()
    clear_config_cache()
