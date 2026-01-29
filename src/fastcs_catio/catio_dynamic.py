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

import glob
from pathlib import Path

from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Int
from fastcs.logging import bind_logger

from catio_terminals.models import (
    RuntimeSymbolsConfig,
    SymbolNode,
    TerminalConfig,
    TerminalType,
)
from fastcs_catio.catio_controller import CATioTerminalController

logger = bind_logger(logger_name=__name__)

# Cache of dynamically generated controller classes
_DYNAMIC_CONTROLLER_CACHE: dict[str, type[CATioTerminalController]] = {}

# Configurable path(s) to terminal types YAML files (supports glob patterns)
# Default to terminal_types.yaml in catio_terminals/terminals/
_TERMINAL_TYPES_PATTERNS: list[str] = [
    str(Path(__file__).parent.parent / "catio_terminals" / "terminals" / "*.yaml")
]

# Path to the runtime symbols YAML file
_RUNTIME_SYMBOLS_PATH = (
    Path(__file__).parent.parent / "catio_terminals" / "config" / "runtime_symbols.yaml"
)

# Cached terminal configuration (loaded once)
_terminal_config: TerminalConfig | None = None

# Cached runtime symbols configuration (loaded once)
_runtime_symbols_config: RuntimeSymbolsConfig | None = None


def _load_terminal_config() -> TerminalConfig:
    """Load and cache the terminal configuration.

    Returns:
        TerminalConfig instance with all terminal definitions.

    Raises:
        FileNotFoundError: If no terminal YAML files found.
    """
    global _terminal_config
    if _terminal_config is None:
        # Expand glob patterns to get list of YAML files
        yaml_files: list[Path] = []
        for pattern in _TERMINAL_TYPES_PATTERNS:
            # Expand the glob pattern
            matches = glob.glob(str(pattern), recursive=True)
            yaml_files.extend(Path(m) for m in matches if Path(m).is_file())

        if not yaml_files:
            raise FileNotFoundError(
                f"No terminal YAML files found matching patterns: "
                f"{_TERMINAL_TYPES_PATTERNS}"
            )

        # Load all matching YAML files and merge them
        _terminal_config = TerminalConfig()
        for yaml_path in yaml_files:
            config = TerminalConfig.from_yaml(yaml_path)
            _terminal_config.terminal_types.update(config.terminal_types)
            logger.debug(f"Loaded terminal definitions from {yaml_path}")

        logger.info(
            f"Loaded {len(_terminal_config.terminal_types)} terminal definitions "
            f"from {len(yaml_files)} file(s)"
        )
    return _terminal_config


def _load_runtime_symbols() -> RuntimeSymbolsConfig:
    """Load and cache the runtime symbols configuration.

    Returns:
        RuntimeSymbolsConfig instance with all runtime symbol definitions.
    """
    global _runtime_symbols_config
    if _runtime_symbols_config is None:
        if _RUNTIME_SYMBOLS_PATH.exists():
            _runtime_symbols_config = RuntimeSymbolsConfig.from_yaml(
                _RUNTIME_SYMBOLS_PATH
            )
            logger.info(
                f"Loaded {len(_runtime_symbols_config.runtime_symbols)} "
                "runtime symbol definitions"
            )
        else:
            _runtime_symbols_config = RuntimeSymbolsConfig()
            logger.warning(f"Runtime symbols YAML not found at {_RUNTIME_SYMBOLS_PATH}")
    return _runtime_symbols_config
    return _terminal_config


def _symbol_to_fastcs_name(symbol: SymbolNode, channel: int | None = None) -> str:
    """Convert a SymbolNode to a FastCS attribute name.

    Uses the fastcs_name field if available, otherwise generates a PascalCase
    name from the name_template.

    Args:
        symbol: The SymbolNode to convert.
        channel: Channel number for multi-channel symbols.

    Returns:
        a camel case attribute name as supplied in the YAML but expanded if
        it is multi channel
    """
    if symbol.fastcs_name:
        # Use provided fastcs_name with channel substitution
        if channel is not None and "{channel}" in symbol.fastcs_name:
            return symbol.fastcs_name.replace("{channel}", str(channel))
        return symbol.fastcs_name
    else:
        raise RuntimeError("Symbol does not have a fastcs_name defined")


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
    # TODO this needs to be mapped using symbol.type_name
    return Int()


def _add_single_attribute(
    controller: CATioTerminalController,
    fastcs_name: str,
    ads_name: str,
    is_readonly: bool,
    desc: str,
    symbol: SymbolNode,
) -> None:
    """Add a single FastCS attribute to a controller.

    Args:
        controller: The controller to add the attribute to.
        fastcs_name: The FastCS attribute name.
        ads_name: The ADS symbol name.
        is_readonly: Whether the attribute is read-only.
        desc: The attribute description.
        symbol: The symbol definition (for datatype).
    """
    if is_readonly:
        controller.add_attribute(
            fastcs_name,
            AttrR(
                datatype=_get_datatype_for_symbol(symbol),
                io_ref=None,
                group=controller.attr_group_name,
                initial_value=0,
                description=desc,
            ),
        )
    else:
        controller.add_attribute(
            fastcs_name,
            AttrRW(
                datatype=_get_datatype_for_symbol(symbol),
                io_ref=None,
                group=controller.attr_group_name,
                initial_value=0,
                description=desc,
            ),
        )

    # Map FastCS name to ADS name
    controller.ads_name_map[fastcs_name] = ads_name


def _add_coe_attribute(
    controller: CATioTerminalController,
    attr_name: str,
    ads_name: str,
    is_readonly: bool,
    desc: str,
    datatype: Int,
) -> None:
    """Add a single CoE attribute to a controller.

    Args:
        controller: The controller to add the attribute to.
        attr_name: The FastCS attribute name.
        ads_name: The ADS CoE symbol name (e.g., "CoE:8000:01").
        is_readonly: Whether the attribute is read-only.
        desc: The attribute description.
        datatype: The FastCS datatype for this CoE object.
    """
    io_ref = None  # Could be extended for custom IO
    if is_readonly:
        controller.add_attribute(
            attr_name,
            AttrR(
                datatype=datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=0,
                description=desc,
            ),
        )
    else:
        controller.add_attribute(
            attr_name,
            AttrRW(
                datatype=datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=0,
                description=desc,
            ),
        )
    controller.ads_name_map[attr_name] = ads_name


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
    ads_name = f"CoE:{coe_obj.index:04X}:{sub.subindex:02X}"

    _add_coe_attribute(controller, attr_name, ads_name, is_readonly, desc, datatype)


def _add_symbol_attribute(
    controller: CATioTerminalController, symbol: SymbolNode
) -> None:
    """Add FastCS attributes for a symbol to a controller.

    Handles both single-channel and multi-channel symbols.

    Args:
        controller: The controller to add attributes to.
        symbol: The symbol definition.
    """
    if symbol.channels > 1:
        # Multi-channel symbol - create one attribute per channel
        for ch in range(1, symbol.channels + 1):
            fastcs_name = _symbol_to_fastcs_name(symbol, ch)
            ads_name = _symbol_to_ads_name(symbol, ch)
            is_readonly = symbol.access is None or "write" not in symbol.access.lower()
            desc = symbol.tooltip or f"{symbol.name_template} ch {ch}"
            _add_single_attribute(
                controller, fastcs_name, ads_name, is_readonly, desc, symbol
            )
    else:
        # Single-channel symbol
        fastcs_name = _symbol_to_fastcs_name(symbol)
        ads_name = _symbol_to_ads_name(symbol)
        is_readonly = symbol.access is None or "write" not in symbol.access.lower()
        desc = symbol.tooltip or symbol.name_template
        _add_single_attribute(
            controller, fastcs_name, ads_name, is_readonly, desc, symbol
        )


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

    # Get applicable runtime symbols for this terminal
    runtime_config = _load_runtime_symbols()
    runtime_symbols: list[SymbolNode] = []
    for rs in runtime_config.runtime_symbols:
        if rs.applies_to_terminal(terminal_id, terminal.group_type):
            runtime_symbols.append(rs.to_symbol_node())

    # Create the class body
    class_dict: dict[str, object] = {
        "__module__": __name__,
        "__doc__": f"Dynamically generated controller for {terminal_id} terminal.",
        "io_function": io_function,
        "_terminal_id": terminal_id,
        "_selected_symbols": selected_symbols,
        "_runtime_symbols": runtime_symbols,
        "_coe_objects": terminal.coe_objects,
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
                ads_name = f"CoE:{coe_obj.index:04X}:0"
                _add_coe_attribute(
                    self, attr_name, ads_name, is_readonly, desc, datatype
                )
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


def set_terminal_types_patterns(patterns: list[str]) -> None:
    """Set the glob patterns for terminal type YAML files.

    Args:
        patterns: List of glob patterns (e.g., ['path/to/*.yaml', 'path/**/*.yaml'])
    """
    global _TERMINAL_TYPES_PATTERNS, _terminal_config
    _TERMINAL_TYPES_PATTERNS = patterns
    # Clear cached config when patterns change
    _terminal_config = None
    _DYNAMIC_CONTROLLER_CACHE.clear()


def clear_controller_cache() -> None:
    """Clear the dynamic controller cache.

    Useful for testing or when terminal definitions change.
    """
    _DYNAMIC_CONTROLLER_CACHE.clear()
    global _terminal_config, _runtime_symbols_config
    _terminal_config = None
    _runtime_symbols_config = None
