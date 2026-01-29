"""Tree view component for displaying terminal structure."""

from typing import TYPE_CHECKING, Any

from nicegui import ui

from catio_terminals.models import CompositeType, SymbolNode, TerminalType
from catio_terminals.service_config import ConfigService
from catio_terminals.service_terminal import TerminalService
from catio_terminals.utils import to_snake_case

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp


def _import_show_terminal_details():
    """Lazy import to avoid circular dependency."""
    from catio_terminals.ui_components.terminal_details import show_terminal_details

    return show_terminal_details


async def build_tree_view(app: "TerminalEditorApp") -> None:
    """Build flat list view of terminal types.

    Args:
        app: Terminal editor application instance
    """
    if not app.config:
        return

    # Build flat list data structure using ConfigService
    app.tree_data = ConfigService.build_tree_data(app.config, app.beckhoff_client)

    # Initialize filtered terminal IDs with all terminals
    app.filtered_terminal_ids = list(app.tree_data.keys())

    # Determine which terminal to select
    terminal_to_select = None
    if app.last_added_terminal:
        # If we just added a terminal, select it
        terminal_to_select = app.last_added_terminal
        app.last_added_terminal = None
    elif app.selected_terminal_id and app.selected_terminal_id in app.tree_data:
        # If a terminal is selected and still exists, keep it selected
        terminal_to_select = app.selected_terminal_id
    elif app.tree_data:
        # If no terminal is selected or deleted, select the first one
        first_terminal = next(iter(app.tree_data.keys()), None)
        if first_terminal:
            terminal_to_select = first_terminal
            app.selected_terminal_id = first_terminal

    # If tree_container exists, clear and rebuild
    if app.tree_container is not None:
        app.tree_container.clear()
        with app.tree_container:
            app.tree_widget = ui.tree(
                list(app.tree_data.values()),
                label_key="label",
                on_select=lambda e: _on_tree_select(app, e.value),
            ).classes("w-full overflow-y-auto")
            assert app.tree_widget is not None
            app.tree_widget.props("selected-color=blue-7")
            app.tree_widget.classes("text-white")

            # Select the determined terminal
            if terminal_to_select:
                assert app.tree_widget is not None
                app.tree_widget.props(f"selected={terminal_to_select}")
                # Scroll to the selected node using JavaScript
                ui.run_javascript(
                    f"""
                    const tree = document.querySelector('.q-tree');
                    const node = tree.querySelector(
                        '[data-id="{terminal_to_select}"]'
                    );
                    if (node) {{
                        node.scrollIntoView(
                            {{ behavior: 'smooth', block: 'center' }}
                        );
                    }}
                """
                )
                # Trigger the selection to show details (deferred to let UI initialize)
                ui.timer(
                    0.01, lambda: _on_tree_select(app, terminal_to_select), once=True
                )
    else:
        # Initial build
        app.tree_widget = ui.tree(
            list(app.tree_data.values()),
            label_key="label",
            on_select=lambda e: _on_tree_select(app, e.value),
        ).classes("w-full overflow-y-auto")
        assert app.tree_widget is not None
        app.tree_widget.props("selected-color=blue-7")
        app.tree_widget.classes("text-white")

        # Select the determined terminal on initial build
        if terminal_to_select:
            assert app.tree_widget is not None
            app.tree_widget.props(f"selected={terminal_to_select}")
            # Trigger the selection to show details (deferred to let UI initialize)
            ui.timer(0.01, lambda: _on_tree_select(app, terminal_to_select), once=True)


def _build_symbol_tree_data(
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
            _build_symbol_node(terminal_id, idx, symbol, composite_types)
        )

    return symbol_tree_data


def _build_symbol_node(
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
        "icon": "data_object",
        "children": symbol_children,
        "symbol_idx": symbol_idx,
        "selected": symbol.selected,
    }


def _on_tree_select(app: "TerminalEditorApp", node_id: str) -> None:
    """Handle tree node selection.

    Args:
        app: Terminal editor application instance
        node_id: Selected node ID
    """
    if not app.config or not app.details_container:
        return

    # Track selected terminal
    app.selected_terminal_id = node_id

    app.details_container.clear()

    with app.details_container:
        # Terminal selected
        terminal = ConfigService.get_terminal(app.config, node_id)
        if terminal:
            # Check if we need to lazy-load XML data for this terminal
            if node_id not in app.merged_terminals:
                # Show loading indicator and load XML
                ui.label(f"Loading {node_id}...").classes("text-gray-400")
                ui.spinner(size="sm")

                async def load_and_show():
                    from catio_terminals.service_file import FileService

                    await FileService.merge_xml_for_terminal(
                        node_id,
                        terminal,
                        app.beckhoff_client,
                    )
                    app.merged_terminals.add(node_id)
                    # Re-render the details
                    _on_tree_select(app, node_id)

                ui.timer(0.01, load_and_show, once=True)
            else:
                show_terminal_details_fn = _import_show_terminal_details()
                show_terminal_details_fn(app, node_id, terminal)
