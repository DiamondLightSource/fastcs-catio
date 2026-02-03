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
from fastcs_catio.catio_coe import (
    CoEAdsItem,
    add_coe_attribute,
    generate_coe_attr_name,
    process_coe_subindex,
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
                add_coe_attribute(
                    controller, attr_name, ads_item, is_readonly, desc, type_name
                )
                return
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
                attr_name = generate_coe_attr_name(base_name, f"CoE{coe_obj.index:04X}")
                desc = f"CoE{coe_obj.index:04X}"
                is_readonly = coe_obj.access.lower() in ("ro", "read-only")
                datatype = Int()  # TODO: map coe_obj.type_name to FastCS type
                ads_item = CoEAdsItem(
                    coe_obj.name, coe_obj.type_name, index=coe_obj.index, subindex=0
                )
                _add_attribute(self, attr_name, ads_item, is_readonly, desc, datatype)
            else:
                # Process each subindex
                for sub in coe_obj.subindices:
                    process_coe_subindex(
                        coe_obj, sub, created_coe_attrs, self, _add_attribute
                    )

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
