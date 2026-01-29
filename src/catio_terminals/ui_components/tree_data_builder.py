"""Tree data builder functions for creating tree structures from terminal data."""

from typing import Any

from catio_terminals.models import CompositeType, SymbolNode, TerminalType
from catio_terminals.service_terminal import TerminalService
from catio_terminals.utils import to_snake_case


def build_symbol_tree_data(
    terminal_id: str,
    terminal: TerminalType,
    composite_types: dict[str, CompositeType] | None = None,
    active_indices: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Build symbol tree showing primitive symbols with checkboxes.

    Args:
        terminal_id: Terminal ID for generating unique node IDs
        terminal: Terminal instance containing symbol_nodes
        composite_types: Optional dict of composite types for bit field expansion
        active_indices: Optional set of symbol indices to include (for PDO groups)

    Returns:
        List of tree node dictionaries for ui.tree
    """
    symbol_tree_data: list[dict[str, Any]] = []

    for idx, symbol in enumerate(terminal.symbol_nodes):
        # Skip symbols not in the active PDO group
        if active_indices is not None and idx not in active_indices:
            continue
        symbol_tree_data.append(
            build_symbol_node(terminal_id, idx, symbol, composite_types)
        )

    return symbol_tree_data


def build_symbol_node(
    terminal_id: str,
    symbol_idx: int,
    symbol: SymbolNode,
    composite_types: dict[str, CompositeType] | None = None,
) -> dict[str, Any]:
    """Build a tree node for a primitive symbol.

    Args:
        terminal_id: Terminal ID for generating unique node IDs
        symbol_idx: Index of the symbol in terminal.symbol_nodes
        symbol: SymbolNode instance
        composite_types: Optional dict of composite types for bit field expansion

    Returns:
        Tree node dictionary for ui.tree
    """
    access = TerminalService.get_symbol_access(symbol.index_group)
    snake_name = to_snake_case(symbol.name_template)

    # Check if the symbol type is a composite type with bit fields
    composite_type = composite_types.get(symbol.type_name) if composite_types else None
    has_bit_fields = composite_type and composite_type.bit_fields

    # Build the type node - make it expandable if it has bit fields
    type_node: dict[str, Any] = {
        "id": f"{terminal_id}_sym{symbol_idx}_type",
        "label": f"Type: {symbol.type_name}",
        "icon": "code",
    }

    if has_bit_fields:
        # Add bit fields as children of the type node
        assert composite_type is not None  # guaranteed by has_bit_fields check
        bit_field_children = [
            {
                "id": f"{terminal_id}_sym{symbol_idx}_bit{bf.bit}",
                "label": f"Bit {bf.bit}: {bf.name}",
                "icon": "toggle_on",
            }
            for bf in sorted(composite_type.bit_fields, key=lambda b: b.bit)
        ]
        type_node["children"] = bit_field_children

    symbol_children = [
        {
            "id": f"{terminal_id}_sym{symbol_idx}_access",
            "label": f"Access: {access}",
            "icon": "lock" if access == "Read-only" else "edit",
        },
        type_node,
        {
            "id": f"{terminal_id}_sym{symbol_idx}_fastcs",
            "label": f"FastCS Name: {snake_name}",
            "icon": "label",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_channels",
            "label": f"Channels: {symbol.channels}",
            "icon": "numbers",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_size",
            "label": f"Size: {symbol.size} bytes",
            "icon": "straighten",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_index",
            "label": f"Index Group: 0x{symbol.index_group:04X}",
            "icon": "tag",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_tooltip",
            "label": f"Tooltip: {symbol.tooltip or '(none)'}",
            "icon": "info",
            "tooltip_idx": symbol_idx,
            "tooltip_value": symbol.tooltip or "",
        },
    ]

    return {
        "id": f"{terminal_id}_symbol_{symbol_idx}",
        "label": symbol.name_template,
        "icon": "dns",
        "children": symbol_children,
        "symbol_idx": symbol_idx,
        "selected": symbol.selected,
    }
