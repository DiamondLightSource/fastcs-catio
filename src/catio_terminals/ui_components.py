"""UI component builders for the terminal editor application."""

from typing import TYPE_CHECKING, Any

from nicegui import ui

from catio_terminals.models import CompositeTypesConfig, SymbolNode, TerminalType
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


def _build_merged_symbol_tree_data(
    terminal_id: str,
    terminal: TerminalType,
    composite_types: CompositeTypesConfig | None,
) -> list[dict[str, Any]]:
    """Build symbol tree with both composite and primitive symbols.

    Symbols with a composite type_name are rendered with member details.
    Primitive symbols are rendered with their basic properties.

    Args:
        terminal_id: Terminal ID for generating unique node IDs
        terminal: Terminal instance containing symbol_nodes
        composite_types: Composite types configuration for looking up members

    Returns:
        List of tree node dictionaries for ui.tree
    """
    symbol_tree_data: list[dict[str, Any]] = []

    for idx, symbol in enumerate(terminal.symbol_nodes):
        # Check if this symbol has a composite type
        composite_type = None
        if composite_types is not None:
            composite_type = composite_types.get_type(symbol.type_name)

        if composite_type is not None:
            # Build composite symbol node with member details
            symbol_tree_data.append(
                _build_composite_symbol_node(terminal_id, idx, symbol, composite_type)
            )
        else:
            # Build primitive symbol node
            symbol_tree_data.append(
                _build_primitive_symbol_node(terminal_id, idx, symbol)
            )

    return symbol_tree_data


def _build_primitive_symbol_node(
    terminal_id: str,
    symbol_idx: int,
    symbol: SymbolNode,
) -> dict[str, Any]:
    """Build a tree node for a primitive symbol.

    Args:
        terminal_id: Terminal ID for generating unique node IDs
        symbol_idx: Index of the symbol in terminal.symbol_nodes
        symbol: SymbolNode instance

    Returns:
        Tree node dictionary for ui.tree
    """
    access = TerminalService.get_symbol_access(symbol.index_group)
    pascal_name = to_pascal_case(symbol.name_template)

    symbol_children = [
        {
            "id": f"{terminal_id}_sym{symbol_idx}_access",
            "label": f"Access: {access}",
            "icon": "lock" if access == "Read-only" else "edit",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_type",
            "label": f"Type: {symbol.type_name}",
            "icon": "code",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_fastcs",
            "label": f"FastCS Name: {pascal_name}",
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
    ]

    return {
        "id": f"{terminal_id}_symbol_{symbol_idx}",
        "label": symbol.name_template,
        "icon": "data_object",
        "children": symbol_children,
        "symbol_idx": symbol_idx,
        "selected": symbol.selected,
    }


def _build_composite_symbol_node(
    terminal_id: str,
    symbol_idx: int,
    symbol: SymbolNode,
    composite_type,
) -> dict[str, Any]:
    """Build a tree node for a composite symbol.

    Args:
        terminal_id: Terminal ID for generating unique node IDs
        symbol_idx: Index of the symbol in terminal.symbol_nodes
        symbol: SymbolNode instance with composite type_name
        composite_type: CompositeType definition from composite_types.yaml

    Returns:
        Tree node dictionary for ui.tree
    """
    from catio_terminals.models import CompositeType

    # Handle case where composite_type is None
    if not isinstance(composite_type, CompositeType):
        return _build_primitive_symbol_node(terminal_id, symbol_idx, symbol)

    # Build member children
    member_children: list[dict[str, Any]] = []
    for member_idx, member in enumerate(composite_type.members):
        member_access = "Read-only" if member.access == "read-only" else "Read/Write"
        member_children.append(
            {
                "id": f"{terminal_id}_sym{symbol_idx}_member{member_idx}",
                "label": f"{member.name} ({member.type_name})",
                "icon": "lock" if member.access == "read-only" else "edit",
                "children": [
                    {
                        "id": f"{terminal_id}_sym{symbol_idx}_m{member_idx}_offset",
                        "label": f"Offset: {member.offset} bytes",
                        "icon": "straighten",
                    },
                    {
                        "id": f"{terminal_id}_sym{symbol_idx}_m{member_idx}_size",
                        "label": f"Size: {member.size} bytes",
                        "icon": "straighten",
                    },
                    {
                        "id": f"{terminal_id}_sym{symbol_idx}_m{member_idx}_access",
                        "label": f"Access: {member_access}",
                        "icon": "lock" if member.access == "read-only" else "edit",
                    },
                    {
                        "id": f"{terminal_id}_sym{symbol_idx}_m{member_idx}_fastcs",
                        "label": f"FastCS Attr: {member.fastcs_attr}",
                        "icon": "label",
                    },
                ],
            }
        )

    access = symbol.access or TerminalService.get_symbol_access(symbol.index_group)
    fastcs_name = symbol.fastcs_name or to_pascal_case(symbol.name_template)

    # Build composite type properties
    type_info_children: list[dict[str, Any]] = [
        {
            "id": f"{terminal_id}_sym{symbol_idx}_type",
            "label": f"Type: {symbol.type_name}",
            "icon": "category",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_size",
            "label": f"Total Size: {composite_type.size} bytes",
            "icon": "straighten",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_access",
            "label": f"Access: {access}",
            "icon": "lock" if access == "Read-only" else "edit",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_fastcs",
            "label": f"FastCS Name: {fastcs_name}",
            "icon": "label",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_channels",
            "label": f"Channels: {symbol.channels}",
            "icon": "numbers",
        },
        {
            "id": f"{terminal_id}_sym{symbol_idx}_index",
            "label": f"Index Group: 0x{symbol.index_group:04X}",
            "icon": "tag",
        },
    ]

    # Create container node for members
    members_node = {
        "id": f"{terminal_id}_sym{symbol_idx}_members",
        "label": f"Members ({len(composite_type.members)})",
        "icon": "list",
        "children": member_children,
    }

    return {
        "id": f"{terminal_id}_symbol_{symbol_idx}",
        "label": f"{symbol.name_template} (Composite)",
        "icon": "view_module",
        "children": type_info_children + [members_node],
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
                        app.composite_types,
                    )
                    app.merged_terminals.add(node_id)
                    # Re-render the details
                    _on_tree_select(app, node_id)

                ui.timer(0.01, load_and_show, once=True)
            else:
                show_terminal_details(app, node_id, terminal)


def _reset_details_pane(app: "TerminalEditorApp") -> None:
    """Reset details pane to blank state.

    Args:
        app: Terminal editor application instance
    """
    app.selected_terminal_id = None

    # Reset header
    if app.details_header_label:
        app.details_header_label.text = "Details"
    if app.details_product_link:
        app.details_product_link.visible = False
    if app.delete_terminal_button:
        app.delete_terminal_button.visible = False

    # Clear details container
    if app.details_container:
        app.details_container.clear()
        with app.details_container:
            ui.label("No terminal selected").classes("text-gray-500")


def show_terminal_details(
    app: "TerminalEditorApp", terminal_id: str, terminal: TerminalType
) -> None:
    """Show terminal details.

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID
        terminal: Terminal instance
    """

    # Get the URL from cached terminals
    product_url = None
    cached_terminals = app.beckhoff_client.get_cached_terminals()
    if cached_terminals:
        for cached_terminal in cached_terminals:
            if cached_terminal.terminal_id.lower() == terminal_id.lower():
                product_url = cached_terminal.url
                break

    # Update header label and link
    if app.details_header_label:
        app.details_header_label.text = f"Terminal: {terminal_id}"
    if app.details_product_link:
        if product_url:
            app.details_product_link.text = "Product Information"
            app.details_product_link._props["href"] = product_url  # noqa: SLF001
            app.details_product_link.visible = True
        else:
            app.details_product_link.visible = False
    if app.delete_terminal_button:
        app.delete_terminal_button.visible = True

    with ui.card().props("flat").classes("w-full mb-4"):
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

    ui.separator().classes("my-4")

    # Symbols section with Select All button
    total_symbols = len(terminal.symbol_nodes)

    with ui.row().classes("items-center w-full justify-between mb-2"):
        ui.label(f"Symbols ({total_symbols})").classes("text-h6")

        with ui.row().classes("gap-2"):

            def toggle_all_symbols():
                all_selected = all(s.selected for s in terminal.symbol_nodes)
                new_value = not all_selected

                for symbol in terminal.symbol_nodes:
                    symbol.selected = new_value

                _mark_changed(app, lambda: _on_tree_select(app, terminal_id))

            # Determine button label based on current state
            all_symbols_selected = (
                all(s.selected for s in terminal.symbol_nodes)
                if terminal.symbol_nodes
                else True
            )
            symbol_btn_label = "Deselect All" if all_symbols_selected else "Select All"
            ui.button(
                symbol_btn_label,
                icon="check_box" if all_symbols_selected else "check_box_outline_blank",
                on_click=toggle_all_symbols,
            ).props("flat dense")

    # Build symbol tree data (handles both composite and primitive symbols)
    symbol_tree_data = _build_merged_symbol_tree_data(
        terminal_id, terminal, app.composite_types
    )

    if symbol_tree_data:
        with ui.card().props("flat").classes("w-full"):
            tree = (
                ui.tree(
                    symbol_tree_data,
                    label_key="label",
                    node_key="id",
                )
                .classes("w-full")
                .props("selected-color=blue-7")
            )

            def make_symbol_toggle_handler(symbol_idx: int):
                """Handler for toggling a symbol.

                Works for both primitives and composites.
                """

                def toggle(e):
                    new_value = (
                        e.args
                        if isinstance(e.args, bool)
                        else e.args[0]
                        if e.args
                        else False
                    )
                    terminal.symbol_nodes[symbol_idx].selected = new_value
                    _mark_changed(app, lambda: None)

                return toggle

            # Add custom slot to include checkbox for selectable items
            tree.add_slot(
                "default-header",
                r"""
                <div class="row items-center">
                    <q-checkbox
                        v-if="props.node.symbol_idx !== undefined"
                        :model-value="props.node.selected"
                        @click.stop="() => {}"
                        @update:model-value="(val) => {
                            props.node.selected = val;
                            $parent.$emit(
                                'toggle-symbol-' + props.node.symbol_idx, val
                            );
                        }"
                        dense
                        class="q-mr-xs"
                    />
                    <q-icon
                        :name="props.node.icon || 'folder'"
                        size="xs"
                        class="q-mr-xs"
                    />
                    <span>{{ props.node.label }}</span>
                </div>
                """,
            )

            # Connect event handlers for all symbols
            for node in symbol_tree_data:
                if "symbol_idx" in node:
                    idx = node["symbol_idx"]
                    tree.on(f"toggle-symbol-{idx}", make_symbol_toggle_handler(idx))

    # Display Runtime Symbols section
    _show_runtime_symbols(app, terminal_id, terminal)

    # Display CoE Objects if available
    if terminal.coe_objects:
        ui.separator().classes("my-4")

        # CoE Objects section with Select All button
        with ui.row().classes("items-center w-full justify-between mb-2"):
            ui.label(f"CoE Objects ({len(terminal.coe_objects)})").classes("text-h6")

            def toggle_all_coe():
                all_selected = all(c.selected for c in terminal.coe_objects)
                new_value = not all_selected
                for coe in terminal.coe_objects:
                    coe.selected = new_value
                _mark_changed(app, lambda: _on_tree_select(app, terminal_id))

            # Determine button label based on current state
            all_coe_selected = all(c.selected for c in terminal.coe_objects)
            coe_btn_label = "Deselect All" if all_coe_selected else "Select All"
            ui.button(
                coe_btn_label,
                icon="check_box" if all_coe_selected else "check_box_outline_blank",
                on_click=toggle_all_coe,
            ).props("flat dense")

        # Build CoE tree data with checkboxes
        coe_tree_data: list[dict[str, Any]] = []
        for idx, coe_obj in enumerate(terminal.coe_objects):
            # Map access flags to readable text
            access_map = {
                "ro": "Read-only",
                "rw": "Read/Write",
                "wo": "Write-only",
            }
            access_text = access_map.get(coe_obj.access, coe_obj.access.upper())

            # Build CoE object properties as children
            coe_children: list[dict[str, Any]] = [
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
            with ui.card().props("flat").classes("w-full"):
                tree = (
                    ui.tree(
                        coe_tree_data,
                        label_key="label",
                        node_key="id",
                    )
                    .classes("w-full")
                    .props("selected-color=blue-7")
                )

                def make_coe_toggle_handler(coe_idx: int):
                    def toggle(e):
                        # e.args contains the new boolean value
                        new_value = (
                            e.args
                            if isinstance(e.args, bool)
                            else e.args[0]
                            if e.args
                            else False
                        )
                        terminal.coe_objects[coe_idx].selected = new_value
                        _mark_changed(app, lambda: None)

                    return toggle

                # Add custom slot to include checkbox for root items
                tree.add_slot(
                    "default-header",
                    r"""
                    <div class="row items-center">
                        <q-checkbox
                            v-if="props.node.coe_idx !== undefined"
                            :model-value="props.node.selected"
                            @click.stop="() => {}"
                            @update:model-value="(val) => {
                                props.node.selected = val;
                                $parent.$emit(
                                    'toggle-coe-' + props.node.coe_idx,
                                    val
                                );
                            }"
                            dense
                            class="q-mr-xs"
                        />
                        <q-icon
                            :name="props.node.icon || 'folder'"
                            size="xs"
                            class="q-mr-xs"
                        />
                        <span>{{ props.node.label }}</span>
                    </div>
                    """,
                )

                # Connect event handlers for each CoE object
                for node in coe_tree_data:
                    idx = int(node["coe_idx"])
                    tree.on(f"toggle-coe-{idx}", make_coe_toggle_handler(idx))


def _show_runtime_symbols(
    app: "TerminalEditorApp", terminal_id: str, terminal: TerminalType
) -> None:
    """Show runtime symbols applicable to this terminal.

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID
        terminal: Terminal instance
    """
    if not app.runtime_symbols:
        return

    # Get runtime symbols applicable to this terminal
    runtime_symbols = app.runtime_symbols.get_symbols_for_terminal(
        terminal_id, terminal.group_type
    )

    if not runtime_symbols:
        return

    ui.separator().classes("my-4")

    # Runtime Symbols section header
    with ui.row().classes("items-center w-full justify-between mb-2"):
        ui.label(f"Runtime Symbols ({len(runtime_symbols)})").classes("text-h6")
        ui.label("Read-only - added by EtherCAT master").classes(
            "text-caption text-grey"
        )

    # Build runtime symbol tree data (read-only, no checkboxes)
    runtime_tree_data = []
    for idx, symbol in enumerate(runtime_symbols):
        # Determine access type
        access = TerminalService.get_symbol_access(symbol.index_group)

        # Build symbol properties as children
        symbol_children = [
            {
                "id": f"{terminal_id}_runtime{idx}_access",
                "label": f"Access: {access}",
                "icon": "lock" if access == "Read-only" else "edit",
            },
            {
                "id": f"{terminal_id}_runtime{idx}_type",
                "label": f"Type: {symbol.type_name}",
                "icon": "code",
            },
            {
                "id": f"{terminal_id}_runtime{idx}_fastcs",
                "label": f"FastCS Name: {symbol.fastcs_name or symbol.name_template}",
                "icon": "label",
            },
            {
                "id": f"{terminal_id}_runtime{idx}_size",
                "label": f"Size: {symbol.size} bytes",
                "icon": "straighten",
            },
            {
                "id": f"{terminal_id}_runtime{idx}_index",
                "label": f"Index Group: 0x{symbol.index_group:04X}",
                "icon": "tag",
            },
        ]

        runtime_tree_data.append(
            {
                "id": f"{terminal_id}_runtime_{idx}",
                "label": symbol.name_template,
                "icon": "monitor_heart",  # Diagnostic icon
                "children": symbol_children,
            }
        )

    with ui.card().props("flat").classes("w-full bg-blue-grey-9"):
        ui.tree(
            runtime_tree_data,
            label_key="label",
            node_key="id",
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
    # Set the flag and run JavaScript BEFORE the action, which may clear UI elements
    app.has_unsaved_changes = True
    try:
        ui.run_javascript("window.hasUnsavedChanges = true;")
    except RuntimeError:
        # Silently ignore if element context is invalid - the flag is already set
        pass
    action()
