"""Main NiceGUI application for terminal editor."""

import logging
from pathlib import Path

from nicegui import ui

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import TerminalConfig, TerminalType

logger = logging.getLogger(__name__)


class TerminalEditorApp:
    """Terminal editor application."""

    def __init__(self) -> None:
        """Initialize the terminal editor."""
        self.config: TerminalConfig | None = None
        self.current_file: Path | None = None
        self.beckhoff_client = BeckhoffClient()
        self.tree_data: dict[str, dict] = {}
        self.has_unsaved_changes = False
        self.details_container: ui.column | None = None
        self.tree_container: ui.column | None = None
        self.tree_widget: ui.tree | None = None
        self.last_added_terminal: str | None = None

    @staticmethod
    def to_pascal_case(name: str) -> str:
        """Convert symbol name to PascalCase for FastCS attribute.

        Args:
            name: Symbol name

        Returns:
            PascalCase version of the name
        """
        # Remove special characters and split by spaces, underscores,
        # and camelCase boundaries
        import re

        # Replace special characters with spaces
        name = re.sub(r"[^a-zA-Z0-9]+", " ", name)
        # Split on spaces and capitalize each word
        words = name.split()
        return "".join(word.capitalize() for word in words if word)

    @staticmethod
    def get_symbol_access(index_group: int) -> str:
        """Determine if symbol is read-only or read/write.

        Args:
            index_group: ADS index group

        Returns:
            'Read-only' or 'Read/Write'
        """
        # 0xF020 = TxPdo (inputs from terminal to controller) = Read-only
        # 0xF030 = RxPdo (outputs from controller to terminal) = Read/Write
        if index_group == 0xF020:
            return "Read-only"
        elif index_group == 0xF030:
            return "Read/Write"
        else:
            return "Unknown"

    async def show_file_selector(self) -> None:
        """Show file selector dialog."""

        with ui.dialog() as dialog, ui.card().classes("w-[800px] max-h-[600px]"):
            ui.label("Select Terminal YAML File").classes("text-lg font-bold mb-4")

            # Folder browser with local state
            current_dir = {"path": Path.cwd()}

            ui.label("Browse Folders:").classes("text-caption text-gray-600 mt-2")

            # Current directory display
            dir_label = ui.label(f"Current: {current_dir['path']}").classes(
                "text-sm text-blue-300 mb-2"
            )

            # Folder navigation
            folder_container = ui.column().classes(
                "w-full max-h-48 overflow-y-auto border border-gray-600 rounded p-2"
            )

            def update_folder_view():
                """Update the folder view with current directory contents."""
                folder_container.clear()
                dir_label.text = f"Current: {current_dir['path']}"

                with folder_container:
                    # Parent directory button
                    if current_dir["path"].parent != current_dir["path"]:
                        with ui.row().classes(
                            "w-full hover:bg-gray-700 cursor-pointer p-1"
                        ):
                            ui.icon("folder").classes("text-yellow-500")

                            def go_up():
                                current_dir["path"] = current_dir["path"].parent
                                update_folder_view()

                            ui.label("..").on("click", go_up)

                    # List directories and YAML files
                    try:
                        items = sorted(current_dir["path"].iterdir())
                        for item in items:
                            if item.is_dir():
                                with ui.row().classes(
                                    "w-full hover:bg-gray-700 cursor-pointer p-1"
                                ):
                                    ui.icon("folder").classes("text-yellow-500")

                                    def go_into(target=item):
                                        current_dir["path"] = target
                                        update_folder_view()

                                    ui.label(item.name).on("click", go_into)
                            elif item.suffix in [".yaml", ".yml"]:
                                with ui.row().classes(
                                    "w-full hover:bg-gray-700 cursor-pointer p-1"
                                ):
                                    ui.icon("description").classes("text-blue-400")

                                    def select_file(target=item):
                                        file_path.set_value(str(target))

                                    ui.label(item.name).on("click", select_file)
                    except PermissionError:
                        ui.label("Permission denied").classes("text-red-400")

            update_folder_view()

            def navigate_to_path():
                """Navigate to the path typed in the file_path input."""
                path_str = file_path.value.strip()
                if path_str:
                    try:
                        new_path = Path(path_str)
                        if new_path.is_dir():
                            current_dir["path"] = new_path
                            update_folder_view()
                        elif new_path.parent.is_dir():
                            # If it's a file path, navigate to its parent directory
                            current_dir["path"] = new_path.parent
                            update_folder_view()
                    except (ValueError, OSError):
                        # Invalid path, keep current directory
                        pass

            file_path = ui.input(
                label="File Path",
                placeholder="/path/to/terminals.yaml (press Enter to navigate)",
                validation={
                    "File must end with .yaml": lambda v: v.endswith(".yaml")
                    or v.endswith(".yml")
                },
            ).classes("w-full mt-4")

            file_path.on("keyup.enter", navigate_to_path)

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Create New",
                    on_click=lambda: self.create_new_file(dialog, file_path.value),
                ).props("flat color=secondary")
                ui.button(
                    "Open",
                    on_click=lambda: self.open_file(dialog, file_path.value),
                ).props("color=primary")

        dialog.open()

    async def create_new_file(self, dialog: ui.dialog, file_path: str) -> None:
        """Create a new YAML file.

        Args:
            dialog: Dialog to close
            file_path: Path to new file
        """
        if not file_path:
            ui.notify("Please specify a file path", type="warning")
            return

        path = Path(file_path)
        if path.exists():
            ui.notify("File already exists. Use Open instead.", type="warning")
            return

        self.config = TerminalConfig()
        self.current_file = path
        self.has_unsaved_changes = False
        dialog.close()
        await self.build_editor_ui()
        ui.notify(f"Created new file: {path.name}", type="positive")

    async def open_file(self, dialog: ui.dialog, file_path: str) -> None:
        """Open an existing YAML file.

        Args:
            dialog: Dialog to close
            file_path: Path to file
        """
        if not file_path:
            ui.notify("Please specify a file path", type="warning")
            return

        path = Path(file_path)
        if not path.exists():
            ui.notify("File does not exist. Use Create New instead.", type="warning")
            return

        try:
            self.config = TerminalConfig.from_yaml(path)
            self.current_file = path
            self.has_unsaved_changes = False
            dialog.close()
            await self.build_editor_ui()
            ui.notify(f"Opened: {path.name}", type="positive")
        except Exception as e:
            logger.exception("Failed to open file")
            ui.notify(f"Failed to open file: {e}", type="negative")

    async def build_editor_ui(self) -> None:
        """Build the main editor UI."""
        # Navigate to editor page
        ui.navigate.to("/editor")

    async def build_tree_view(self) -> None:
        """Build flat list view of terminal types."""
        if not self.config:
            return

        # Build flat list data structure (just terminal descriptions)
        self.tree_data = {}
        for terminal_id, terminal in self.config.terminal_types.items():
            self.tree_data[terminal_id] = {
                "id": terminal_id,
                "label": f"{terminal_id} - {terminal.description}",
                "icon": "memory",
            }

        # If tree_container exists, clear and rebuild
        if self.tree_container is not None:
            self.tree_container.clear()
            with self.tree_container:
                self.tree_widget = ui.tree(
                    list(self.tree_data.values()),
                    label_key="label",
                    on_select=lambda e: self.on_tree_select(e.value),
                ).classes("w-full overflow-y-auto")
                self.tree_widget.props("selected-color=blue-7")
                self.tree_widget.classes("text-white")

                # If there's a last added terminal, scroll to it and select it
                if self.last_added_terminal:
                    # Set the selected node
                    self.tree_widget.props(f"selected={self.last_added_terminal}")
                    # Scroll to the selected node using JavaScript
                    ui.run_javascript(f'''
                        const tree = document.querySelector('.q-tree');
                        const node = tree.querySelector(
                            '[data-id="{self.last_added_terminal}"]'
                        );
                        if (node) {{
                            node.scrollIntoView(
                                {{ behavior: 'smooth', block: 'center' }}
                            );
                        }}
                    ''')
                    self.last_added_terminal = None
        else:
            # Initial build
            self.tree_widget = ui.tree(
                list(self.tree_data.values()),
                label_key="label",
                on_select=lambda e: self.on_tree_select(e.value),
            ).classes("w-full overflow-y-auto")
            self.tree_widget.props("selected-color=blue-7")
            self.tree_widget.classes("text-white")

    def on_tree_select(self, node_id: str) -> None:
        """Handle tree node selection.

        Args:
            node_id: Selected node ID
        """
        if not self.config or not self.details_container:
            return

        self.details_container.clear()

        with self.details_container:
            # Terminal selected
            terminal = self.config.terminal_types.get(node_id)
            if terminal:
                self.show_terminal_details(node_id, terminal)

    def show_terminal_details(self, terminal_id: str, terminal: TerminalType) -> None:
        """Show terminal details.

        Args:
            terminal_id: Terminal ID
            terminal: Terminal instance
        """
        ui.label(f"Terminal: {terminal_id}").classes("text-h5 mb-4")

        with ui.card().classes("w-full mb-4"):
            ui.label("Description").classes("text-caption text-gray-600")
            ui.label(terminal.description).classes("mb-2")

            ui.separator()

            ui.label("Identity").classes("text-caption text-gray-600 mt-2")
            ui.label(f"Vendor ID: {terminal.identity.vendor_id}")
            ui.label(f"Product Code: 0x{terminal.identity.product_code:08X}")
            ui.label(f"Revision: 0x{terminal.identity.revision_number:08X}")

        with ui.row().classes("w-full justify-end mb-2"):
            ui.button(
                "Delete Terminal",
                icon="delete",
                on_click=lambda: self.delete_terminal(terminal_id),
            ).props("color=negative")

        ui.separator().classes("my-4")

        ui.label(f"Symbols ({len(terminal.symbol_nodes)})").classes("text-h6 mb-2")

        # Build symbol tree data
        symbol_tree_data = []
        for idx, symbol in enumerate(terminal.symbol_nodes):
            # Determine access type
            access = self.get_symbol_access(symbol.index_group)

            # Convert to PascalCase for FastCS
            pascal_name = self.to_pascal_case(symbol.name_template)

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

    def show_symbol_details(self, terminal_id: str, symbol_idx: int) -> None:
        """Show symbol details.

        Args:
            terminal_id: Terminal ID
            symbol_idx: Symbol index
        """
        if not self.config:
            return

        terminal = self.config.terminal_types[terminal_id]
        symbol = terminal.symbol_nodes[symbol_idx]

        ui.label(f"Symbol: {symbol.name_template}").classes("text-h5 mb-4")

        with ui.card().classes("w-full"):
            ui.input(
                label="Name Template",
                value=symbol.name_template,
                on_change=lambda e: self._mark_changed(
                    lambda: setattr(symbol, "name_template", e.value)
                ),
            ).classes("w-full")

            with ui.row().classes("w-full gap-2"):
                ui.number(
                    label="Index Group",
                    value=symbol.index_group,
                    format="0x%04X",
                    on_change=lambda e: self._mark_changed(
                        lambda: setattr(symbol, "index_group", int(e.value))
                    ),
                ).classes("flex-1")

                ui.number(
                    label="Size",
                    value=symbol.size,
                    on_change=lambda e: self._mark_changed(
                        lambda: setattr(symbol, "size", int(e.value))
                    ),
                ).classes("flex-1")

            with ui.row().classes("w-full gap-2"):
                ui.number(
                    label="ADS Type",
                    value=symbol.ads_type,
                    on_change=lambda e: self._mark_changed(
                        lambda: setattr(symbol, "ads_type", int(e.value))
                    ),
                ).classes("flex-1")

                ui.number(
                    label="Channels",
                    value=symbol.channels,
                    on_change=lambda e: self._mark_changed(
                        lambda: setattr(symbol, "channels", int(e.value))
                    ),
                ).classes("flex-1")

            ui.input(
                label="Type Name",
                value=symbol.type_name,
                on_change=lambda e: self._mark_changed(
                    lambda: setattr(symbol, "type_name", e.value)
                ),
            ).classes("w-full")

    def _mark_changed(self, action) -> None:
        """Mark that changes have been made and execute the action.

        Args:
            action: Function to execute
        """
        action()
        self.has_unsaved_changes = True
        ui.run_javascript("window.hasUnsavedChanges = true;")

    async def delete_terminal(self, terminal_id: str) -> None:
        """Delete a terminal type.

        Args:
            terminal_id: Terminal ID to delete
        """
        if not self.config:
            return

        with ui.dialog() as dialog, ui.card():
            ui.label(f"Delete terminal {terminal_id}?").classes("text-h6")
            ui.label("This action cannot be undone.").classes("text-caption")

            result = {"confirm": False}

            def confirm_delete():
                result["confirm"] = True
                dialog.close()

            def cancel_delete():
                result["confirm"] = False
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=cancel_delete).props("flat")
                ui.button("Delete", on_click=confirm_delete).props("color=negative")

        await dialog

        if result["confirm"]:
            self.config.remove_terminal(terminal_id)
            self.has_unsaved_changes = True
            await self.build_editor_ui()
            ui.notify(f"Deleted terminal: {terminal_id}", type="info")

    async def show_add_terminal_dialog(self) -> None:
        """Show dialog to add a new terminal."""

        with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
            ui.label("Add Terminal Type").classes("text-lg font-bold mb-4")

            ui.label("Search Beckhoff Terminals").classes("text-caption text-gray-600")
            search_input = ui.input(
                placeholder="Search terminals...",
            ).classes("w-full mb-2")

            # Results container
            results_container = ui.column().classes("w-full max-h-64 overflow-y-auto")

            def is_terminal_already_added(term) -> bool:
                """Check if terminal is already in config.

                Args:
                    term: BeckhoffTerminalInfo instance

                Returns:
                    True if terminal already exists
                """
                if not self.config:
                    return False

                # First check by terminal ID
                if term.terminal_id in self.config.terminal_types:
                    return True

                # Check if any existing terminal has same product code and revision
                # (using cached values from terminals_cache.json for speed)
                if term.product_code and term.revision_number:
                    for existing_terminal in self.config.terminal_types.values():
                        if (
                            existing_terminal.identity.product_code == term.product_code
                            and existing_terminal.identity.revision_number
                            == term.revision_number
                        ):
                            return True

                return False

            async def search_terminals() -> None:
                """Search for terminals."""
                results_container.clear()
                terminals = await self.beckhoff_client.search_terminals(
                    search_input.value
                )

                # Filter out terminals that are already added
                filtered_terminals = [
                    term for term in terminals if not is_terminal_already_added(term)
                ]

                with results_container:
                    if not filtered_terminals:
                        if terminals:
                            ui.label(
                                "All matching terminals are already added"
                            ).classes("text-gray-500")
                        else:
                            ui.label("No terminals found").classes("text-gray-500")
                    else:
                        for term in filtered_terminals:
                            with ui.card().classes("w-full hover:bg-gray-700"):
                                with ui.row().classes(
                                    "w-full items-center gap-2 flex-nowrap"
                                ):
                                    ui.label(
                                        f"{term.terminal_id} - {term.description}"
                                    ).classes(
                                        "font-bold text-white overflow-hidden "
                                        "text-ellipsis whitespace-nowrap flex-grow"
                                    )

                                    async def add_term(t=term):
                                        await self.add_terminal_from_beckhoff(t)
                                        # Refresh the search to update the filtered list
                                        await search_terminals()

                                    ui.button(
                                        "Add",
                                        on_click=add_term,
                                    ).props("color=primary").classes("flex-shrink-0")

            search_input.on("keyup.enter", search_terminals)
            with ui.row().classes("w-full justify-between mt-4"):
                ui.button("Done", on_click=dialog.close).props("color=positive")
                ui.button("Search", on_click=search_terminals).props("color=primary")

        dialog.open()

    async def add_terminal_from_beckhoff(self, terminal_info) -> None:
        """Add terminal from Beckhoff information.

        Args:
            terminal_info: BeckhoffTerminalInfo instance
        """
        if not self.config:
            return

        # Try to fetch XML, otherwise use default
        xml_content = await self.beckhoff_client.fetch_terminal_xml(
            terminal_info.terminal_id
        )

        if xml_content:
            try:
                terminal = self.beckhoff_client.parse_terminal_xml(
                    xml_content, terminal_info.terminal_id
                )
            except ValueError:
                logger.error("Failed to parse XML, using default")
                terminal = self.beckhoff_client.create_default_terminal(
                    terminal_info.terminal_id, terminal_info.description
                )
        else:
            terminal = self.beckhoff_client.create_default_terminal(
                terminal_info.terminal_id, terminal_info.description
            )

        self.config.add_terminal(terminal_info.terminal_id, terminal)
        self.has_unsaved_changes = True
        # Store the last added terminal for scrolling
        self.last_added_terminal = terminal_info.terminal_id
        # Rebuild the tree view without navigating (which would close the dialog)
        await self.build_tree_view()
        ui.notify(f"Added terminal: {terminal_info.terminal_id}", type="positive")

    async def add_manual_terminal(
        self, terminal_id: str, description: str, dialog: ui.dialog
    ) -> None:
        """Add terminal manually.

        Args:
            terminal_id: Terminal ID
            description: Terminal description
            dialog: Dialog to close
        """
        if not self.config:
            return

        if not terminal_id:
            ui.notify("Please enter a terminal ID", type="warning")
            return

        if terminal_id in self.config.terminal_types:
            ui.notify("Terminal ID already exists", type="warning")
            return

        terminal = self.beckhoff_client.create_default_terminal(
            terminal_id, description or f"Terminal {terminal_id}"
        )
        self.config.add_terminal(terminal_id, terminal)
        self.has_unsaved_changes = True
        dialog.close()
        await self.build_editor_ui()
        ui.notify(f"Added terminal: {terminal_id}", type="positive")

    async def save_file(self) -> None:
        """Save current configuration to file."""
        if not self.config or not self.current_file:
            ui.notify("No file loaded", type="warning")
            return

        try:
            self.config.to_yaml(self.current_file)
            self.has_unsaved_changes = False
            ui.run_javascript("window.hasUnsavedChanges = false;")
            ui.notify(f"Saved: {self.current_file.name}", type="positive")
        except Exception as e:
            logger.exception("Failed to save file")
            ui.notify(f"Failed to save: {e}", type="negative")

    async def fetch_terminal_database(self) -> None:
        """Fetch and parse Beckhoff terminal database with progress dialog."""
        import asyncio

        # Create dialog with progress UI
        with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
            ui.label("Fetching Terminal Database").classes("text-h6 mb-4")
            progress_label = ui.label("Initializing...").classes("mb-2")
            progress_bar = ui.linear_progress(value=0, show_value=False).props(
                "instant-feedback"
            )

        # Define update function that properly updates UI
        def update_progress(message: str, progress: float):
            """Update progress in the dialog."""
            progress_label.set_text(message)
            progress_bar.set_value(progress)

        # Open dialog before starting work
        dialog.open()

        # Small delay to ensure dialog is rendered
        await asyncio.sleep(0.1)

        try:
            # Fetch and parse (now with async sleeps to prevent blocking)
            terminals = await self.beckhoff_client.fetch_and_parse_xml(
                progress_callback=update_progress
            )

            if terminals:
                ui.notify(
                    f"Successfully fetched {len(terminals)} terminals!",
                    type="positive",
                )
            else:
                ui.notify("No terminals found", type="warning")

        except Exception as e:
            logger.exception("Failed to fetch terminal database")
            ui.notify(f"Error: {e}", type="negative")

        finally:
            dialog.close()

    async def close_editor(self) -> None:
        """Close the editor and return to file selector.

        Warns if there are unsaved changes.
        """
        if self.has_unsaved_changes:
            with ui.dialog() as dialog, ui.card():
                ui.label("Unsaved Changes").classes("text-h6")
                ui.label(
                    "You have unsaved changes. What would you like to do?"
                ).classes("text-caption mb-4")

                action_result = {"value": None}

                def submit_action(value):
                    action_result["value"] = value
                    dialog.close()

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=lambda: submit_action("cancel")).props(
                        "flat"
                    )
                    ui.button(
                        "Discard Changes", on_click=lambda: submit_action("discard")
                    ).props("color=negative")
                    ui.button(
                        "Save & Close", on_click=lambda: submit_action("save")
                    ).props("color=positive")

            await dialog

            action = action_result["value"]

            if action == "cancel" or action is None:
                return
            elif action == "save":
                # Save the file first
                await self.save_file()
                # If save failed, don't close
                if self.has_unsaved_changes:
                    return
            # If action == "discard" or save succeeded, continue to close

        # Reset state and navigate to file selector
        self.config = None
        self.current_file = None
        self.has_unsaved_changes = False
        ui.run_javascript("window.hasUnsavedChanges = false;")
        ui.navigate.to("/")


def main() -> None:
    """Main entry point for the application."""
    logging.basicConfig(level=logging.INFO)

    editor = TerminalEditorApp()

    @ui.page("/")
    async def index() -> None:
        """Index page - file selector."""
        ui.dark_mode().enable()
        await editor.show_file_selector()

    @ui.page("/editor")
    async def editor_page() -> None:
        """Editor page - main interface."""
        ui.dark_mode().enable()

        # Prevent page scrolling - make it fixed height
        ui.add_head_html("""
            <style>
                body, #app, .nicegui-content {
                    overflow: hidden !important;
                    height: 100vh;
                }
            </style>
        """)

        with ui.header().classes("items-center justify-between px-4"):
            with ui.column().classes("gap-0"):
                ui.label("Terminal Configuration Editor").classes("text-h5")
                if editor.current_file:
                    file_info = (
                        f"📄 {editor.current_file.name} - {editor.current_file.parent}"
                    )
                    ui.label(file_info).classes("text-sm text-blue-300")

            with ui.row().classes("gap-2"):
                # Prominent Save button
                ui.button(
                    "Save",
                    icon="save",
                    on_click=editor.save_file,
                ).props("color=positive")

                # Close button
                ui.button(
                    "Close",
                    icon="close",
                    on_click=editor.close_editor,
                ).props("color=negative")

                ui.button(
                    "Add Terminal",
                    icon="add",
                    on_click=editor.show_add_terminal_dialog,
                ).props("color=primary")

                ui.button(
                    "Fetch Terminal Database",
                    icon="download",
                    on_click=editor.fetch_terminal_database,
                ).props("color=secondary")

        # Unsaved changes indicator
        if editor.has_unsaved_changes:
            with ui.row().classes("w-full justify-center bg-orange-900 py-1"):
                ui.icon("warning").classes("text-orange-300")
                ui.label("You have unsaved changes").classes(
                    "text-sm text-orange-300 font-bold"
                )

        with ui.splitter(value=30).classes("w-full h-full") as splitter:
            with splitter.before:
                with ui.card().classes("w-full h-full flex flex-col"):
                    ui.label("Terminal Types").classes("text-h6 mb-2")
                    editor.tree_container = (
                        ui.column()
                        .classes("w-full overflow-y-auto")
                        .style("flex: 1; min-height: 0;")
                    )
                    with editor.tree_container:
                        await editor.build_tree_view()

            with splitter.after:
                with ui.card().classes("w-full h-full flex flex-col"):
                    ui.label("Details").classes("text-h6 mb-2")
                    editor.details_container = (
                        ui.column()
                        .classes("w-full overflow-y-auto")
                        .style("flex: 1; min-height: 0;")
                    )

        # Warn before leaving with unsaved changes
        ui.add_head_html("""
            <script>
                // Initialize the flag to false
                window.hasUnsavedChanges = false;

                window.addEventListener('beforeunload', (event) => {
                    if (window.hasUnsavedChanges === true) {
                        event.preventDefault();
                        event.returnValue = '';
                        return 'You have unsaved changes. Are you sure?';
                    }
                });
            </script>
        """)

    ui.run(
        title="Terminal Configuration Editor",
        favicon="🔧",
        dark=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
