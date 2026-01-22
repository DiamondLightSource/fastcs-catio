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
        """Build tree view of terminal types."""
        if not self.config:
            return

        # Build tree data structure
        self.tree_data = {}
        for terminal_id, terminal in self.config.terminal_types.items():
            symbol_children = []
            for idx, symbol in enumerate(terminal.symbol_nodes):
                label = f"{symbol.name_template} (channels: {symbol.channels})"
                symbol_children.append(
                    {
                        "id": f"{terminal_id}_symbol_{idx}",
                        "label": label,
                        "icon": "data_object",
                        "terminal_id": terminal_id,
                        "symbol_idx": idx,
                    }
                )

            self.tree_data[terminal_id] = {
                "id": terminal_id,
                "label": f"{terminal_id} - {terminal.description}",
                "icon": "memory",
                "children": symbol_children,
            }

        tree = ui.tree(
            list(self.tree_data.values()),
            label_key="label",
            on_select=lambda e: self.on_tree_select(e.value),
        ).classes("w-full")

        # Better contrast for selected items
        tree.props("selected-color=blue-7")
        tree.classes("text-white")

    def on_tree_select(self, node_id: str) -> None:
        """Handle tree node selection.

        Args:
            node_id: Selected node ID
        """
        if not self.config:
            return

        self.details_container.clear()

        with self.details_container:
            # Check if it's a terminal or symbol
            if "_symbol_" in node_id:
                # Symbol selected
                terminal_id, _, symbol_idx = node_id.split("_symbol_")
                symbol_idx = int(symbol_idx)
                terminal = self.config.terminal_types.get(terminal_id)
                if terminal and symbol_idx < len(terminal.symbol_nodes):
                    self.show_symbol_details(terminal_id, symbol_idx)
            else:
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

        ui.label(f"Symbols ({len(terminal.symbol_nodes)})").classes("text-h6 mb-2")

        with ui.row().classes("w-full justify-end mb-2"):
            ui.button(
                "Delete Terminal",
                icon="delete",
                on_click=lambda: self.delete_terminal(terminal_id),
            ).props("color=negative")

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

        result = await ui.dialog().props("persistent")

        with result, ui.card():
            ui.label(f"Delete terminal {terminal_id}?").classes("text-h6")
            ui.label("This action cannot be undone.").classes("text-caption")

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=lambda: result.submit(False)).props("flat")
                ui.button("Delete", on_click=lambda: result.submit(True)).props(
                    "color=negative"
                )

        if await result:
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

            async def search_terminals() -> None:
                """Search for terminals."""
                results_container.clear()
                terminals = await self.beckhoff_client.search_terminals(
                    search_input.value
                )

                with results_container:
                    if not terminals:
                        ui.label("No terminals found").classes("text-gray-500")
                    else:
                        for term in terminals:
                            with ui.card().classes("w-full hover:bg-gray-700"):
                                with ui.row().classes(
                                    "w-full items-center justify-between"
                                ):
                                    with ui.column().classes("flex-grow"):
                                        ui.label(
                                            f"{term.terminal_id} - {term.name}"
                                        ).classes("font-bold text-white")
                                        ui.label(term.description).classes(
                                            "text-caption text-gray-300"
                                        )

                                    def add_term(t=term):
                                        return self.add_terminal_from_beckhoff(
                                            t, dialog
                                        )

                                    ui.button(
                                        "Add",
                                        on_click=add_term,
                                    ).props("color=primary")

            search_input.on("keyup.enter", search_terminals)
            with ui.row().classes("w-full justify-between mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Search", on_click=search_terminals).props("color=primary")

        dialog.open()

    async def add_terminal_from_beckhoff(
        self, terminal_info, dialog: ui.dialog
    ) -> None:
        """Add terminal from Beckhoff information.

        Args:
            terminal_info: BeckhoffTerminalInfo instance
            dialog: Dialog to close
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
        dialog.close()
        await self.build_editor_ui()
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

        # Unsaved changes indicator
        if editor.has_unsaved_changes:
            with ui.row().classes("w-full justify-center bg-orange-900 py-1"):
                ui.icon("warning").classes("text-orange-300")
                ui.label("You have unsaved changes").classes(
                    "text-sm text-orange-300 font-bold"
                )

        with ui.splitter(value=30).classes("w-full h-full") as splitter:
            with splitter.before:
                with ui.card().classes("w-full h-full"):
                    ui.label("Terminal Types").classes("text-h6 mb-2")
                    await editor.build_tree_view()

            with splitter.after:
                with ui.card().classes("w-full h-full"):
                    ui.label("Details").classes("text-h6 mb-2")
                    editor.details_container = ui.column().classes("w-full")

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
