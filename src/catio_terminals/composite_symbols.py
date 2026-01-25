"""Composite symbol grouping for terminal definitions.

This module provides logic to group primitive symbols from XML into composite
type symbols that TwinCAT would generate at runtime. The grouping is based on
patterns defined in composite_types.yaml.

The XML defines individual PDO entries like:
- Underrange {channel}
- Overrange {channel}
- Error {channel}
- Value {channel}

TwinCAT groups these into composite symbols like:
- AI Standard Channel {channel} (type: AI Standard Channel 1_TYPE)

This module provides the mapping between these two representations.
"""

from dataclasses import dataclass, field

from catio_terminals.models import (
    CompositeType,
    CompositeTypesConfig,
    SymbolNode,
    TerminalType,
)


@dataclass
class CompositeSymbolMapping:
    """Mapping between a composite type and the terminal group types it applies to.

    Attributes:
        type_name: The composite type name (e.g., "AI Standard Channel 1_TYPE")
        name_template: Symbol name template (e.g., "AI Standard Channel {channel}")
        group_types: Terminal group types this mapping applies to (e.g., ["AnaIn"])
        member_patterns: Patterns to match primitive symbols to members
    """

    type_name: str
    name_template: str
    group_types: list[str]
    member_patterns: dict[str, list[str]] = field(default_factory=dict)


# Define mappings from composite types to terminal groups and member patterns
COMPOSITE_MAPPINGS: list[CompositeSymbolMapping] = [
    # Analog Input - Standard 16-bit
    CompositeSymbolMapping(
        type_name="AI Standard Channel 1_TYPE",
        name_template="AI Standard Channel {channel}",
        group_types=["AnaIn"],
        member_patterns={
            # Maps composite member name to primitive symbol patterns
            "Status": ["Underrange", "Overrange", "Limit", "Error", "TxPDO"],
            "Value": ["Value"],
        },
    ),
    # Analog Input - 24-bit
    CompositeSymbolMapping(
        type_name="AI Inputs Channel 1_TYPE",
        name_template="AI Inputs Channel {channel}",
        group_types=["AnaIn"],
        member_patterns={
            "Status": ["Underrange", "Overrange", "Limit", "Error", "TxPDO"],
            "Value": ["Value"],
        },
    ),
    # Analog Output
    CompositeSymbolMapping(
        type_name="AO Output Channel 1_TYPE",
        name_template="AO Output Channel {channel}",
        group_types=["AnaOut"],
        member_patterns={
            "AnalogOutput": ["Analog output", "Output"],
        },
    ),
    # Digital Input
    CompositeSymbolMapping(
        type_name="Inputs_TYPE",
        name_template="Inputs Channel {channel}",
        group_types=["DigIn"],
        member_patterns={
            "Inputs": ["Input", "Channel"],
        },
    ),
    # Digital Output
    CompositeSymbolMapping(
        type_name="Outputs_TYPE",
        name_template="Outputs Channel {channel}",
        group_types=["DigOut"],
        member_patterns={
            "Outputs": ["Output", "Channel"],
        },
    ),
    # Counter Input
    CompositeSymbolMapping(
        type_name="CNT Inputs_TYPE",
        name_template="CNT Inputs Channel {channel}",
        group_types=["Counting"],
        member_patterns={
            "Status": ["Status"],
            "CounterValue": ["Counter", "Value"],
        },
    ),
]


@dataclass
class CompositeSymbol:
    """A composite symbol with its grouped primitive members.

    Attributes:
        name_template: Composite symbol name template
        type_name: Composite type name
        index_group: ADS index group
        channels: Number of channels
        access: Access mode
        fastcs_name: PascalCase name for FastCS
        composite_type: The CompositeType definition
        primitive_symbols: List of primitive symbols grouped into this composite
        selected: Whether this composite symbol is selected for YAML output
    """

    name_template: str
    type_name: str
    index_group: int
    channels: int
    access: str
    fastcs_name: str
    composite_type: CompositeType
    primitive_symbols: list[SymbolNode] = field(default_factory=list)
    selected: bool = True  # Default to selected for new terminals


@dataclass
class GroupedSymbols:
    """Result of grouping primitive symbols into composite types.

    Attributes:
        composite_symbols: List of composite symbols with grouped primitives
        ungrouped_symbols: List of primitive symbols that couldn't be grouped
    """

    composite_symbols: list[CompositeSymbol]
    ungrouped_symbols: list[SymbolNode]


def _find_mapping_for_terminal(group_type: str | None) -> CompositeSymbolMapping | None:
    """Find the composite mapping that applies to a terminal group type.

    Args:
        group_type: Terminal group type (e.g., "AnaIn", "DigOut")

    Returns:
        Matching CompositeSymbolMapping or None
    """
    if not group_type:
        return None

    for mapping in COMPOSITE_MAPPINGS:
        if group_type in mapping.group_types:
            return mapping
    return None


def _symbol_matches_member(symbol: SymbolNode, patterns: list[str]) -> bool:
    """Check if a symbol's name matches any of the member patterns.

    Args:
        symbol: Symbol node to check
        patterns: List of pattern strings to match against

    Returns:
        True if symbol name contains any pattern (case-insensitive)
    """
    name_lower = symbol.name_template.lower()
    return any(pattern.lower() in name_lower for pattern in patterns)


def _get_channel_count(symbols: list[SymbolNode]) -> int:
    """Determine the channel count from a list of symbols.

    Uses the most common channel count among symbols that have channels > 1.

    Args:
        symbols: List of symbol nodes

    Returns:
        Most common channel count, or 1 if no multi-channel symbols
    """
    channel_counts: dict[int, int] = {}
    for sym in symbols:
        if sym.channels > 1:
            channel_counts[sym.channels] = channel_counts.get(sym.channels, 0) + 1

    if not channel_counts:
        return 1

    # Return the most common channel count
    return max(channel_counts.keys(), key=lambda k: channel_counts[k])


def group_symbols_by_composite(
    terminal: TerminalType,
    composite_types: CompositeTypesConfig | None,
) -> GroupedSymbols:
    """Group primitive symbols into composite types based on terminal group.

    Args:
        terminal: Terminal type containing primitive symbol nodes
        composite_types: Composite types configuration

    Returns:
        GroupedSymbols with composite and ungrouped symbols
    """
    if not composite_types:
        return GroupedSymbols(
            composite_symbols=[],
            ungrouped_symbols=list(terminal.symbol_nodes),
        )

    # Find the mapping for this terminal type
    mapping = _find_mapping_for_terminal(terminal.group_type)

    if not mapping:
        return GroupedSymbols(
            composite_symbols=[],
            ungrouped_symbols=list(terminal.symbol_nodes),
        )

    # Get the composite type definition
    composite_type = composite_types.get_type(mapping.type_name)
    if not composite_type:
        return GroupedSymbols(
            composite_symbols=[],
            ungrouped_symbols=list(terminal.symbol_nodes),
        )

    # Group symbols by matching member patterns
    grouped_primitives: list[SymbolNode] = []
    ungrouped: list[SymbolNode] = []
    matched_members: set[str] = set()

    for symbol in terminal.symbol_nodes:
        matched = False
        for member_name, patterns in mapping.member_patterns.items():
            if _symbol_matches_member(symbol, patterns):
                grouped_primitives.append(symbol)
                matched_members.add(member_name)
                matched = True
                break
        if not matched:
            ungrouped.append(symbol)

    # Only create a composite if ALL member patterns were matched
    # This prevents partial matches on terminals with different structures
    # (e.g., oversampling terminals that have "Value" but not "Status")
    if matched_members != set(mapping.member_patterns.keys()):
        return GroupedSymbols(
            composite_symbols=[],
            ungrouped_symbols=list(terminal.symbol_nodes),
        )

    # If we grouped any symbols, create a composite symbol
    composite_symbols: list[CompositeSymbol] = []
    if grouped_primitives:
        # Determine channel count from grouped symbols
        channels = _get_channel_count(grouped_primitives)

        # Determine index group (use the most common one)
        index_groups = [s.index_group for s in grouped_primitives]
        index_group = max(set(index_groups), key=index_groups.count)

        # Determine access (Read-only if any are read-only)
        access = "Read-only"
        for sym in grouped_primitives:
            if sym.access and "write" in sym.access.lower():
                access = "Read/Write"
                break

        # Generate FastCS name from template
        fastcs_name = mapping.name_template.replace(" ", "").replace("{channel}", "")

        # Composite is selected if ALL its primitive symbols are selected
        all_primitives_selected = all(s.selected for s in grouped_primitives)

        composite_symbols.append(
            CompositeSymbol(
                name_template=mapping.name_template,
                type_name=mapping.type_name,
                index_group=index_group,
                channels=channels,
                access=access,
                fastcs_name=fastcs_name,
                composite_type=composite_type,
                primitive_symbols=grouped_primitives,
                selected=all_primitives_selected,
            )
        )

    return GroupedSymbols(
        composite_symbols=composite_symbols,
        ungrouped_symbols=ungrouped,
    )


def get_composite_view_data(
    terminal: TerminalType,
    composite_types: CompositeTypesConfig | None,
) -> tuple[list[CompositeSymbol], list[SymbolNode]]:
    """Get symbol data organized for composite view display.

    Args:
        terminal: Terminal type
        composite_types: Composite types configuration

    Returns:
        Tuple of (composite_symbols, ungrouped_symbols)
    """
    result = group_symbols_by_composite(terminal, composite_types)
    return result.composite_symbols, result.ungrouped_symbols
