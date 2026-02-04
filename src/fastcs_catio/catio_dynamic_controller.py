"""Dynamic controller generation from YAML terminal definitions.

This module provides a factory function that generates FastCS controller classes
dynamically from terminal YAML definitions. This enables gradual replacement of
explicit hardware classes with generated ones.

Usage:
    from fastcs_catio.catio_dynamic_controller import get_terminal_controller_class

    # Get or create a controller class for a terminal type
    controller_class = get_terminal_controller_class("EL1004")

    # Use it like any other controller class
    controller = controller_class(name="MOD1", node=node)
"""

from fastcs.logging import bind_logger

from catio_terminals.models import SymbolNode
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.catio_dynamic_coe import (
    CoEAdsItem,
    add_coe_attribute,
)
from fastcs_catio.catio_dynamic_symbol import add_symbol_attribute
from fastcs_catio.terminal_config import (
    clear_config_cache,
    get_terminal_type,
    load_runtime_symbols,
)

logger = bind_logger(logger_name=__name__)


# -----------------------------------------------------------------------------
# Dynamic Controller Cache and Helpers
# -----------------------------------------------------------------------------

# Cache of dynamically generated controller classes
_DYNAMIC_CONTROLLER_CACHE: dict[str, type[CATioTerminalController]] = {}


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
            add_symbol_attribute(self, symbol)

        # Then process PDO symbols
        for symbol in pdo_symbols:
            add_symbol_attribute(self, symbol)

        # Add CoE objects and subindices as FastCS attributes
        # Track created attribute names to detect collisions
        created_coe_attrs: set[str] = set()

        for coe_obj in coe_objects:
            # If no subindices, treat as single value
            if not getattr(coe_obj, "subindices", []):
                ads_item = CoEAdsItem(
                    name=coe_obj.name,
                    type_name=coe_obj.type_name,
                    index=coe_obj.index,
                    subindex=0,
                    fastcs_name=coe_obj.fastcs_name,
                    access=coe_obj.access,
                    bit_size=coe_obj.bit_size,
                )
                add_coe_attribute(self, ads_item)
                # TODO use this to make sure all names are unique
                created_coe_attrs.add(ads_item.fastcs_name)
            else:
                # Process each subindex
                for subindex in coe_obj.subindices:
                    ads_item = CoEAdsItem(
                        name=coe_obj.name,
                        type_name=subindex.type_name,
                        index=coe_obj.index,
                        subindex=subindex.subindex,
                        fastcs_name=subindex.fastcs_name,
                        access=subindex.access,
                        bit_size=subindex.bit_size,
                    )
                    if ads_item.fastcs_name in created_coe_attrs:
                        logger.warning(
                            f"Attribute name collision for CoE object "
                            f"{ads_item.name} index {ads_item.index} subindex "
                            f"{ads_item.subindex}: {ads_item.fastcs_name} "
                            "already exists. Skipping attribute creation."
                        )
                        continue
                    add_coe_attribute(self, ads_item)
                    created_coe_attrs.add(ads_item.fastcs_name)

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

    _DYNAMIC_CONTROLLER_CACHE.clear()
    clear_config_cache()
