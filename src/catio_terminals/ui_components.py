"""UI component builders for the terminal editor application."""

from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.models import TerminalType
from catio_terminals.service_config import ConfigService
from catio_terminals.service_terminal import TerminalService
from catio_terminals.utils import to_pascal_case

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp


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

    # Get the URL from cached terminals
    product_url = None
    cached_terminals = app.beckhoff_client.get_cached_terminals()
    if cached_terminals:
        for cached_terminal in cached_terminals:
            if cached_terminal.terminal_id.lower() == terminal_id.lower():
                product_url = cached_terminal.url
                break

    # Display terminal name with product information link
    with ui.row().classes("items-center mb-4 gap-4"):
        ui.label(f"Terminal: {terminal_id}").classes("text-h5")
        if product_url:
            ui.link("Product Information", target=product_url).props(
                "target=_blank"
            ).classes("text-blue-400")

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

    # Build symbol tree data with checkboxes
    symbol_tree_data = []
    for idx, symbol in enumerate(terminal.symbol_nodes):
        # Determine access type
        access = TerminalService.get_symbol_access(symbol.index_group)

        # Convert to PascalCase for FastCS
        pascal_name = to_pascal_case(symbol.name_template)

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
                "symbol_idx": idx,
                "selected": symbol.selected,
            }
        )

    if symbol_tree_data:
        with ui.card().classes("w-full"):

            def make_symbol_toggle_handler(symbol_idx: int):
                def toggle(e):
                    terminal.symbol_nodes[symbol_idx].selected = e.args
                    _mark_changed(app, lambda: None)

                return toggle

            tree = ui.tree(
                symbol_tree_data,
                label_key="label",
            ).classes("w-full").props("selected-color=blue-7")

            # Add custom slot to include checkbox for root items
            tree.add_slot(
                "default-header",
                r"""
                <div class="row items-center">
                    <q-checkbox 
                        v-if="props.node.symbol_idx !== undefined"
                        :model-value="props.node.selected"
                        @update:model-value="(val) => $parent.$emit('toggle-symbol-' + props.node.symbol_idx, val)"
                        @click.stop
                        dense
                        class="q-mr-xs"
                    />
                    <q-icon :name="props.node.icon || 'folder'" size="xs" class="q-mr-xs"/>
                    <span>{{ props.node.label }}</span>
                </div>
                """,
            )

            # Connect event handlers for each symbol
            for node in symbol_tree_data:
                idx = node["symbol_idx"]
                tree.on(f"toggle-symbol-{idx}", make_symbol_toggle_handler(idx))

    # Display CoE Objects if available
    if terminal.coe_objects:
        ui.separator().classes("my-4")
        ui.label(f"CoE Objects ({len(terminal.coe_objects)})").classes("text-h6 mb-2")

        # Build CoE tree data with checkboxes
        coe_tree_data = []
        for idx, coe_obj in enumerate(terminal.coe_objects):
            # Map access flags to readable text
            access_map = {
                "ro": "Read-only",
                "rw": "Read/Write",
                "wo": "Write-only",
            }
            access_text = access_map.get(coe_obj.access, coe_obj.access.upper())

            # Build CoE object properties as children
            coe_children = [
                {
                    "id": f"{terminal_id}_coe{idx}_index",
                    "label": f"Index: 0x{coe_obj.index:04X}",
                    "icon": "tag",
                },
                {
                    "id": f"{terminal_id}_coe{idx}_type",
                    "label": f"Type: {coe_obj.type_name}",
                    "icon": "code",
                },
                {
                    "id": f"{terminal_id}_coe{idx}_size",
                    "label": f"Size: {coe_obj.bit_size} bits",
                    "icon": "straighten",
                },
                {
                    "id": f"{terminal_id}_coe{idx}_access",
                    "label": f"Access: {access_text}",
                    "icon": "lock" if coe_obj.access == "ro" else "edit",
                },
            ]

            # Add subindices container if present
            if coe_obj.subindices:
                subindices_children = []
                for sub_idx, subindex in enumerate(coe_obj.subindices):
                    # Build subindex details with subindex number first
                    subindex_details = [
                        {
                            "id": f"{terminal_id}_coe{idx}_sub{sub_idx}_num",
                            "label": f"SubIndex: 0x{subindex.subindex:02X}",
                            "icon": "tag",
                        }
                    ]

                    if subindex.type_name:
                        subindex_details.append(
                            {
                                "id": f"{terminal_id}_coe{idx}_sub{sub_idx}_type",
                                "label": f"Type: {subindex.type_name}",
                                "icon": "code",
                            }
                        )

                    if subindex.bit_size is not None:
                        subindex_details.append(
                            {
                                "id": f"{terminal_id}_coe{idx}_sub{sub_idx}_size",
                                "label": f"Size: {subindex.bit_size} bits",
                                "icon": "straighten",
                            }
                        )

                    if subindex.access:
                        # Map access flags to readable text
                        access_map = {
                            "ro": "Read-only",
                            "rw": "Read/Write",
                            "wo": "Write-only",
                        }
                        sub_access_text = access_map.get(
                            subindex.access, subindex.access.upper()
                        )
                        subindex_details.append(
                            {
                                "id": f"{terminal_id}_coe{idx}_sub{sub_idx}_access",
                                "label": f"Access: {sub_access_text}",
                                "icon": ("lock" if subindex.access == "ro" else "edit"),
                            }
                        )

                    if subindex.default_data:
                        subindex_details.append(
                            {
                                "id": f"{terminal_id}_coe{idx}_sub{sub_idx}_default",
                                "label": f"Default: {subindex.default_data}",
                                "icon": "data_object",
                            }
                        )

                    subindices_children.append(
                        {
                            "id": f"{terminal_id}_coe{idx}_subindex_{sub_idx}",
                            "label": subindex.name,
                            "icon": "subdirectory_arrow_right",
                            "children": subindex_details,
                        }
                    )

                # Add the Subindices container node
                coe_children.append(
                    {
                        "id": f"{terminal_id}_coe{idx}_subindices",
                        "label": f"Subindices ({len(coe_obj.subindices)})",
                        "icon": "list",
                        "children": subindices_children,
                    }
                )

            coe_tree_data.append(
                {
                    "id": f"{terminal_id}_coe_{idx}",
                    "label": coe_obj.name,
                    "icon": "settings",
                    "children": coe_children,
                    "coe_idx": idx,
                    "selected": coe_obj.selected,
                }
            )

        if coe_tree_data:
            with ui.card().classes("w-full"):

                def make_coe_toggle_handler(coe_idx: int):
                    def toggle(e):
                        terminal.coe_objects[coe_idx].selected = e.args
                        _mark_changed(app, lambda: None)

                    return toggle

                tree = ui.tree(
                    coe_tree_data,
                    label_key="label",
                ).classes("w-full").props("selected-color=blue-7")

                # Add custom slot to include checkbox for root items
                tree.add_slot(
                    "default-header",
                    r"""
                    <div class="row items-center">
                        <q-checkbox 
                            v-if="props.node.coe_idx !== undefined"
                            :model-value="props.node.selected"
                            @update:model-value="(val) => $parent.$emit('toggle-coe-' + props.node.coe_idx, val)"
                            @click.stop
                            dense
                            class="q-mr-xs"
                        />
                        <q-icon :name="props.node.icon || 'folder'" size="xs" class="q-mr-xs"/>
                        <span>{{ props.node.label }}</span>
                    </div>
                    """,
                )

                # Connect event handlers for each CoE object
                for node in coe_tree_data:
                    idx = node["coe_idx"]
                    tree.on(f"toggle-coe-{idx}", make_coe_toggle_handler(idx))


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
