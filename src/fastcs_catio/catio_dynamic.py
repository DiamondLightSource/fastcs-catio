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

from pathlib import Path

from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Int
from fastcs.logging import bind_logger

from catio_terminals.models import SymbolNode, TerminalConfig, TerminalType
from fastcs_catio.catio_controller import CATioTerminalController

logger = bind_logger(logger_name=__name__)

# Cache of dynamically generated controller classes
_DYNAMIC_CONTROLLER_CACHE: dict[str, type[CATioTerminalController]] = {}

# Path to the terminal types YAML file
_TERMINAL_TYPES_PATH = (
    Path(__file__).parent.parent
    / "catio_terminals"
    / "terminals"
    / "terminal_types.yaml"
)

# Cached terminal configuration (loaded once)
_terminal_config: TerminalConfig | None = None


def _load_terminal_config() -> TerminalConfig:
    """Load and cache the terminal configuration.

    Returns:
        TerminalConfig instance with all terminal definitions.

    Raises:
        FileNotFoundError: If terminal_types.yaml does not exist.
    """
    global _terminal_config
    if _terminal_config is None:
        if not _TERMINAL_TYPES_PATH.exists():
            raise FileNotFoundError(
                f"Terminal types YAML not found at {_TERMINAL_TYPES_PATH}"
            )
        _terminal_config = TerminalConfig.from_yaml(_TERMINAL_TYPES_PATH)
        logger.info(
            f"Loaded {len(_terminal_config.terminal_types)} terminal definitions"
        )
    return _terminal_config


def _symbol_to_fastcs_name(symbol: SymbolNode, channel: int | None = None) -> str:
    """Convert a SymbolNode to a FastCS attribute name.

    Uses the fastcs_name field if available, otherwise generates a PascalCase
    name from the name_template.

    Args:
        symbol: The SymbolNode to convert.
        channel: Channel number for multi-channel symbols.

    Returns:
        PascalCase attribute name (e.g., "DICh1Value", "Channel1").
    """
    if symbol.fastcs_name:
        # Use provided fastcs_name with channel substitution
        if channel is not None and "{channel}" in symbol.fastcs_name:
            return symbol.fastcs_name.replace("{channel}", str(channel))
        return symbol.fastcs_name

    # Generate from name_template
    name = symbol.name_template
    if channel is not None and "{channel}" in name:
        name = name.replace("{channel}", str(channel))

    # Convert to PascalCase: "Channel 1" -> "Channel1", "WcState" -> "WcState"
    # Remove spaces and capitalize each word
    words = name.replace("_", " ").split()
    return "".join(word.capitalize() for word in words)


def _symbol_to_ads_name(symbol: SymbolNode, channel: int | None = None) -> str:
    """Convert a SymbolNode to the ADS symbol name.

    This is the name used to look up the symbol in ADS.

    Args:
        symbol: The SymbolNode to convert.
        channel: Channel number for multi-channel symbols.

    Returns:
        ADS symbol name (e.g., "Channel 1", "WcState").
    """
    name = symbol.name_template
    if channel is not None and "{channel}" in name:
        name = name.replace("{channel}", str(channel))
    return name


def _get_datatype_for_symbol(symbol: SymbolNode) -> Int:
    """Get the FastCS datatype for a symbol.

    Args:
        symbol: The SymbolNode to get the datatype for.

    Returns:
        FastCS Int datatype (currently all symbols map to Int).
    """
    # For now, all symbols map to Int
    # In the future, we could use Float for REAL types, etc.
    return Int()


def _create_dynamic_controller_class(
    terminal_id: str, terminal: TerminalType
) -> type[CATioTerminalController]:
    """Create a dynamic controller class for a terminal type.

    Args:
        terminal_id: Terminal identifier (e.g., "EL1004").
        terminal: TerminalType instance with symbol definitions.

    Returns:
        A new controller class that extends CATioTerminalController.
    """
    # Determine io_function from description
    io_function = terminal.description or f"{terminal_id} terminal"

    # Get selected symbols only
    selected_symbols = [s for s in terminal.symbol_nodes if s.selected]

    # Create the class body
    class_dict: dict[str, object] = {
        "__module__": __name__,
        "__doc__": f"Dynamically generated controller for {terminal_id} terminal.",
        "io_function": io_function,
        "_terminal_id": terminal_id,
        "_selected_symbols": selected_symbols,
    }

    async def get_io_attributes(self: CATioTerminalController) -> None:
        """Get and create all terminal attributes from YAML definition."""
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await CATioTerminalController.get_io_attributes(self)

        # Get symbols from class attribute
        symbols: list[SymbolNode] = getattr(self.__class__, "_selected_symbols", [])

        # Create attributes for each selected symbol
        for symbol in symbols:
            if symbol.channels > 1:
                # Multi-channel symbol - create one attribute per channel
                for ch in range(1, symbol.channels + 1):
                    fastcs_name = _symbol_to_fastcs_name(symbol, ch)
                    ads_name = _symbol_to_ads_name(symbol, ch)

                    # Determine if read-only or read-write
                    is_readonly = (
                        symbol.access is None or "read" in symbol.access.lower()
                    )

                    desc = symbol.tooltip or f"{symbol.name_template} ch {ch}"
                    if is_readonly:
                        self.add_attribute(
                            fastcs_name,
                            AttrR(
                                datatype=_get_datatype_for_symbol(symbol),
                                io_ref=None,
                                group=self.attr_group_name,
                                initial_value=0,
                                description=desc,
                            ),
                        )
                    else:
                        self.add_attribute(
                            fastcs_name,
                            AttrRW(
                                datatype=_get_datatype_for_symbol(symbol),
                                io_ref=None,
                                group=self.attr_group_name,
                                initial_value=0,
                                description=desc,
                            ),
                        )

                    # Map FastCS name to ADS name
                    self.ads_name_map[fastcs_name] = ads_name
            else:
                # Single-channel symbol
                fastcs_name = _symbol_to_fastcs_name(symbol)
                ads_name = _symbol_to_ads_name(symbol)

                is_readonly = symbol.access is None or "read" in symbol.access.lower()

                if is_readonly:
                    self.add_attribute(
                        fastcs_name,
                        AttrR(
                            datatype=_get_datatype_for_symbol(symbol),
                            io_ref=None,
                            group=self.attr_group_name,
                            initial_value=0,
                            description=symbol.tooltip or symbol.name_template,
                        ),
                    )
                else:
                    self.add_attribute(
                        fastcs_name,
                        AttrRW(
                            datatype=_get_datatype_for_symbol(symbol),
                            io_ref=None,
                            group=self.attr_group_name,
                            initial_value=0,
                            description=symbol.tooltip or symbol.name_template,
                        ),
                    )

                # Map FastCS name to ADS name if different
                if fastcs_name != ads_name:
                    self.ads_name_map[fastcs_name] = ads_name

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

    # Load terminal configuration
    config = _load_terminal_config()

    # Find the terminal definition
    if terminal_id not in config.terminal_types:
        raise KeyError(
            f"Terminal type '{terminal_id}' not found in terminal_types.yaml"
        )

    terminal = config.terminal_types[terminal_id]

    # Create the dynamic controller class
    controller_class = _create_dynamic_controller_class(terminal_id, terminal)

    # Cache it
    _DYNAMIC_CONTROLLER_CACHE[terminal_id] = controller_class
    logger.info(f"Created dynamic controller class for {terminal_id}")

    return controller_class


def clear_controller_cache() -> None:
    """Clear the dynamic controller cache.

    Useful for testing or when terminal definitions change.
    """
    _DYNAMIC_CONTROLLER_CACHE.clear()
    global _terminal_config
    _terminal_config = None
