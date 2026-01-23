"""Main NiceGUI application for terminal editor."""

from __future__ import annotations

import logging
from pathlib import Path

from nicegui import app, ui

from catio_terminals import dialogs, ui_components
from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.file_service import FileService
from catio_terminals.models import TerminalConfig

logger = logging.getLogger(__name__)

# Global editor instance
_editor_instance: TerminalEditorApp | None = None


def get_editor() -> TerminalEditorApp:
    """Get or create the global editor instance.

    Returns:
        The global editor instance
    """
    global _editor_instance
    if _editor_instance is None:
        _editor_instance = TerminalEditorApp()
    return _editor_instance


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

    async def build_editor_ui(self) -> None:
        """Build the main editor UI."""
        ui.navigate.to("/editor")

    async def build_tree_view(self) -> None:
        """Build flat list view of terminal types."""
        await ui_components.build_tree_view(self)

    async def save_file(self) -> None:
        """Save current configuration to file."""
        if not self.config or not self.current_file:
            ui.notify("No file loaded", type="warning")
            return

        try:
            FileService.save_file(self.config, self.current_file)
            self.has_unsaved_changes = False
            ui.run_javascript("window.hasUnsavedChanges = false;")
            ui.notify(f"Saved: {self.current_file.name}", type="positive")
        except Exception as e:
            logger.exception("Failed to save file")
            ui.notify(f"Failed to save: {e}", type="negative")


def run() -> None:
    """Run the terminal editor application."""
    # Configure leave site confirmation for unsaved changes
    app.on_connect(
        lambda: ui.run_javascript(
            """
        window.hasUnsavedChanges = false;
        window.addEventListener('beforeunload', (event) => {
            if (window.hasUnsavedChanges) {
                event.preventDefault();
                event.returnValue = '';
            }
        });
    """
        )
    )

    @ui.page("/")
    async def index() -> None:
        """Landing page."""
        ui.dark_mode().enable()

        editor = get_editor()

        ui.label("CATio Terminal Editor").classes("text-h3 mb-4")
        ui.button(
            "Open Terminal Configuration",
            icon="folder_open",
            on_click=lambda: dialogs.show_file_selector(editor),
        ).props("size=lg")

    @ui.page("/editor")
    async def editor_page() -> None:
        """Editor page."""
        ui.dark_mode().enable()

        editor = get_editor()

        # Add custom CSS
        ui.add_head_html(
            """
        <style>
            body, #app {
                overflow: hidden !important;
                height: 100vh;
            }
        </style>
        """
        )

        with ui.header().classes("items-center justify-between"):
            ui.label("CATio Terminal Editor").classes("text-h6")

            if editor.current_file:
                ui.label(f"File: {editor.current_file.name}").classes(
                    "text-sm text-gray-400"
                )

            with ui.row():
                ui.button(
                    "Save",
                    icon="save",
                    on_click=editor.save_file,
                ).props("flat")

                ui.button(
                    "Close",
                    icon="close",
                    on_click=lambda: dialogs.show_close_editor_dialog(editor),
                ).props("color=negative")

                ui.button(
                    "Add Terminal",
                    icon="add",
                    on_click=lambda: dialogs.show_add_terminal_dialog(editor),
                ).props("color=primary")

                ui.button(
                    "Fetch Terminal Database",
                    icon="download",
                    on_click=lambda: dialogs.show_fetch_database_dialog(editor),
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
                    with editor.details_container:
                        ui.label("Select a terminal to view details").classes(
                            "text-gray-500"
                        )

    ui.run(title="CATio Terminal Editor", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    run()
