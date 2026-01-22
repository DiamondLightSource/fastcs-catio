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

    async def show_file_selector(self) -> None:
        """Show file selector dialog."""

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Select Terminal YAML File").classes("text-lg font-bold mb-4")

            with ui.row().classes("w-full gap-2"):
                file_path = ui.input(
                    label="File Path",
                    placeholder="/path/to/terminals.yaml",
                    validation={
                        "File must end with .yaml": lambda v: v.endswith(".yaml")
                        or v.endswith(".yml")
                    },
                ).classes("flex-grow")

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

        # Add context menu for terminals
        tree.props("selected-color=primary")

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
                on_change=lambda e: setattr(symbol, "name_template", e.value),
            ).classes("w-full")

            with ui.row().classes("w-full gap-2"):
                ui.number(
                    label="Index Group",
                    value=symbol.index_group,
                    format="0x%04X",
                    on_change=lambda e: setattr(symbol, "index_group", int(e.value)),
                ).classes("flex-1")

                ui.number(
                    label="Size",
                    value=symbol.size,
                    on_change=lambda e: setattr(symbol, "size", int(e.value)),
                ).classes("flex-1")

            with ui.row().classes("w-full gap-2"):
                ui.number(
                    label="ADS Type",
                    value=symbol.ads_type,
                    on_change=lambda e: setattr(symbol, "ads_type", int(e.value)),
                ).classes("flex-1")

                ui.number(
                    label="Channels",
                    value=symbol.channels,
                    on_change=lambda e: setattr(symbol, "channels", int(e.value)),
                ).classes("flex-1")

            ui.input(
                label="Type Name",
                value=symbol.type_name,
                on_change=lambda e: setattr(symbol, "type_name", e.value),
            ).classes("w-full")

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
                            with ui.card().classes(
                                "w-full cursor-pointer hover:bg-gray-100"
                            ):
                                ui.label(f"{term.terminal_id} - {term.name}").classes(
                                    "font-bold"
                                )
                                ui.label(term.description).classes("text-caption")

                                def add_term(t=term):
                                    return self.add_terminal_from_beckhoff(t, dialog)

                                ui.button(
                                    "Add",
                                    on_click=add_term,
                                ).props("flat color=primary")

            search_input.on("keyup.enter", search_terminals)
            ui.button("Search", on_click=search_terminals).props("color=primary")

            ui.separator().classes("my-4")

            ui.label("Or Create Manually").classes("text-caption text-gray-600")
            manual_id = ui.input(label="Terminal ID (e.g., EL4004)").classes("w-full")
            manual_desc = ui.input(label="Description").classes("w-full")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button(
                    "Create Manually",
                    on_click=lambda: self.add_manual_terminal(
                        manual_id.value, manual_desc.value, dialog
                    ),
                ).props("color=secondary")

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
            ui.notify(f"Saved: {self.current_file.name}", type="positive")
        except Exception as e:
            logger.exception("Failed to save file")
            ui.notify(f"Failed to save: {e}", type="negative")


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

        with ui.header().classes("items-center justify-between"):
            ui.label("Terminal Configuration Editor").classes("text-h5")
            with ui.row():
                ui.button(
                    "Save",
                    icon="save",
                    on_click=editor.save_file,
                ).props("flat")
                ui.button(
                    "Add Terminal",
                    icon="add",
                    on_click=editor.show_add_terminal_dialog,
                ).props("color=primary")

        if editor.current_file:
            ui.label(f"File: {editor.current_file}").classes(
                "text-caption text-gray-600 px-4"
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

    ui.run(
        title="Terminal Configuration Editor",
        favicon="🔧",
        dark=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
