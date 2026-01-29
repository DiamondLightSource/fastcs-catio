"""Terminal configuration loading and symbol parsing.

This module handles loading terminal definitions from YAML files,
parsing symbols, and converting them to FastCS/ADS naming conventions.
"""

import glob
from pathlib import Path

from fastcs.datatypes import Int
from fastcs.logging import bind_logger

from catio_terminals.models import (
    RuntimeSymbolsConfig,
    SymbolNode,
    TerminalConfig,
    TerminalType,
)

logger = bind_logger(logger_name=__name__)

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


def load_terminal_config() -> TerminalConfig:
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


def load_runtime_symbols() -> RuntimeSymbolsConfig:
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


def symbol_to_fastcs_name(symbol: SymbolNode, channel: int | None = None) -> str:
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


def symbol_to_ads_name(symbol: SymbolNode, channel: int | None = None) -> str:
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


def get_datatype_for_symbol(symbol: SymbolNode) -> Int:
    """Get the FastCS datatype for a symbol.

    Args:
        symbol: The SymbolNode to get the datatype for.

    Returns:
        FastCS Int datatype (currently all symbols map to Int).
    """
    # For now, all symbols map to Int
    # TODO this needs to be mapped using symbol.type_name
    return Int()


def set_terminal_types_patterns(patterns: list[str]) -> None:
    """Set the glob patterns for terminal type YAML files.

    Args:
        patterns: List of glob patterns (e.g., ['path/to/*.yaml', 'path/**/*.yaml'])
    """
    global _TERMINAL_TYPES_PATTERNS, _terminal_config
    _TERMINAL_TYPES_PATTERNS = patterns
    # Clear cached config when patterns change
    _terminal_config = None


def clear_config_cache() -> None:
    """Clear the cached terminal configuration and runtime symbols.

    Useful for testing or when terminal definitions change.
    """
    global _terminal_config, _runtime_symbols_config
    _terminal_config = None
    _runtime_symbols_config = None


def get_terminal_type(terminal_id: str) -> TerminalType:
    """Get a terminal type definition by ID.

    Args:
        terminal_id: Terminal identifier (e.g., "EL1004", "EL3104").

    Returns:
        TerminalType instance.

    Raises:
        KeyError: If the terminal type is not found.
    """
    config = load_terminal_config()
    if terminal_id not in config.terminal_types:
        raise KeyError(
            f"Terminal type '{terminal_id}' not found in terminal_types.yaml"
        )
    return config.terminal_types[terminal_id]
