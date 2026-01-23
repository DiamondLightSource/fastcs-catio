"""UI component builders for the terminal editor application."""

from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.models import TerminalType
from catio_terminals.service_config import ConfigService
from catio_terminals.service_terminal import TerminalService

if TYPE_CHECKING:
    from catio_terminals.app import TerminalEditorApp


async def build_tree_view(app: "TerminalEditorApp") -> None:
    """Build flat list view of terminal types.

    Args:
        app: Terminal editor application instance
    """
    if not app.config:
        return

    # Build flat list data structure using ConfigService
    app.tree_data = ConfigService.build_tree_data(app.config)

    # Determine which terminal to select
    terminal_to_select = None
    if app.last_added_terminal:
        # If we just added a terminal, select it
        terminal_to_select = app.last_added_terminal
        app.last_added_terminal = None
    elif app.tree_data and not app.selected_terminal_id:
        # If no terminal is selected and we have terminals, select the first one
        first_terminal = next(iter(app.tree_data.keys()), None)
        if first_terminal:
            terminal_to_select = first_terminal

    # If tree_container exists, clear and rebuild
    if app.tree_container is not None:
        app.tree_container.clear()
        with app.tree_container:
            app.tree_widget = ui.tree(
                list(app.tree_data.values()),
                label_key="label",
                on_select=lambda e: _on_tree_select(app, e.value),
            ).classes("w-full overflow-y-auto")
            app.tree_widget.props("selected-color=blue-7")
            app.tree_widget.classes("text-white")

            # Select the determined terminal
            if terminal_to_select:
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
        app.tree_widget.props("selected-color=blue-7")
        app.tree_widget.classes("text-white")

        # Select the determined terminal on initial build
        if terminal_to_select:
            app.tree_widget.props(f"selected={terminal_to_select}")
            # Trigger the selection to show details (deferred to let UI initialize)
            ui.timer(0.01, lambda: _on_tree_select(app, terminal_to_select), once=True)


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
            show_terminal_details(app, node_id, terminal)


def show_terminal_details(
    app: "TerminalEditorApp", terminal_id: str, terminal: TerminalType
) -> None:
    """Show terminal details.

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID
        terminal: Terminal instance
    """
    from catio_terminals import ui_dialogs

    ui.label(f"Terminal: {terminal_id}").classes("text-h5 mb-4")

    with ui.card().classes("w-full mb-4"):
        ui.label("Description").classes("text-caption text-gray-600")
        ui.label(terminal.description).classes("mb-2")

        ui.separator()

        ui.label("Identity").classes("text-caption text-gray-600 mt-2")
        ui.label(f"Vendor ID: {terminal.identity.vendor_id}")
        ui.label(f"Product Code: 0x{terminal.identity.product_code:08X}")
        ui.label(f"Revision: 0x{terminal.identity.revision_number:08X}")
        if terminal.group_type:
            from catio_terminals.ui_dialogs import GROUP_TYPE_LABELS

            group_label = GROUP_TYPE_LABELS.get(
                terminal.group_type, terminal.group_type
            )
            ui.label(f"Group Type: {group_label}")

    with ui.row().classes("w-full justify-end mb-2"):
        ui.button(
            "Delete Terminal",
            icon="delete",
            on_click=lambda: ui_dialogs.show_delete_terminal_dialog(app, terminal_id),
        ).props("color=negative")

    ui.separator().classes("my-4")

    ui.label(f"Symbols ({len(terminal.symbol_nodes)})").classes("text-h6 mb-2")

    # Build symbol tree data
    symbol_tree_data = []
    for idx, symbol in enumerate(terminal.symbol_nodes):
        # Determine access type
        access = TerminalService.get_symbol_access(symbol.index_group)

        # Convert to PascalCase for FastCS
        pascal_name = TerminalService.to_pascal_case(symbol.name_template)

        # Build symbol properties as children
        symbol_children = [
            {
                "id": f"{terminal_id}_sym{idx}_access",
                "label": f"Access: {access}",
                "icon": "lock" if access == "Read-only" else "edit",
            },
            {
                "id": f"{terminal_id}_sym{idx}_type",
                "label": f"Type: {symbol.type_name}",
                "icon": "code",
            },
            {
                "id": f"{terminal_id}_sym{idx}_fastcs",
                "label": f"FastCS Name: {pascal_name}",
                "icon": "label",
            },
            {
                "id": f"{terminal_id}_sym{idx}_channels",
                "label": f"Channels: {symbol.channels}",
                "icon": "numbers",
            },
            {
                "id": f"{terminal_id}_sym{idx}_size",
                "label": f"Size: {symbol.size} bytes",
                "icon": "straighten",
            },
            {
                "id": f"{terminal_id}_sym{idx}_index",
                "label": f"Index Group: 0x{symbol.index_group:04X}",
                "icon": "tag",
            },
        ]

        symbol_tree_data.append(
            {
                "id": f"{terminal_id}_symbol_{idx}",
                "label": symbol.name_template,
                "icon": "data_object",
                "children": symbol_children,
            }
        )

    if symbol_tree_data:
        with ui.card().classes("w-full"):
            ui.tree(
                symbol_tree_data,
                label_key="label",
            ).classes("w-full").props("selected-color=blue-7")


def show_symbol_details(
    app: "TerminalEditorApp", terminal_id: str, symbol_idx: int
) -> None:
    """Show symbol details (currently unused, for future editing).

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID
        symbol_idx: Symbol index
    """
    if not app.config:
        return

    terminal = app.config.terminal_types[terminal_id]
    symbol = terminal.symbol_nodes[symbol_idx]

    ui.label(f"Symbol: {symbol.name_template}").classes("text-h5 mb-4")

    with ui.card().classes("w-full"):
        ui.input(
            label="Name Template",
            value=symbol.name_template,
            on_change=lambda e: _mark_changed(
                app, lambda: setattr(symbol, "name_template", e.value)
            ),
        ).classes("w-full")

        with ui.row().classes("w-full gap-2"):
            ui.number(
                label="Index Group",
                value=symbol.index_group,
                format="0x%04X",
                on_change=lambda e: _mark_changed(
                    app, lambda: setattr(symbol, "index_group", int(e.value))
                ),
            ).classes("flex-1")

            ui.number(
                label="Size",
                value=symbol.size,
                on_change=lambda e: _mark_changed(
                    app, lambda: setattr(symbol, "size", int(e.value))
                ),
            ).classes("flex-1")

        with ui.row().classes("w-full gap-2"):
            ui.number(
                label="ADS Type",
                value=symbol.ads_type,
                on_change=lambda e: _mark_changed(
                    app, lambda: setattr(symbol, "ads_type", int(e.value))
                ),
            ).classes("flex-1")

            ui.number(
                label="Channels",
                value=symbol.channels,
                on_change=lambda e: _mark_changed(
                    app, lambda: setattr(symbol, "channels", int(e.value))
                ),
            ).classes("flex-1")

        ui.input(
            label="Type Name",
            value=symbol.type_name,
            on_change=lambda e: _mark_changed(
                app, lambda: setattr(symbol, "type_name", e.value)
            ),
        ).classes("w-full")


def _mark_changed(app: "TerminalEditorApp", action) -> None:
    """Mark that changes have been made and execute the action.

    Args:
        app: Terminal editor application instance
        action: Function to execute
    """
    action()
    app.has_unsaved_changes = True
    ui.run_javascript("window.hasUnsavedChanges = true;")
