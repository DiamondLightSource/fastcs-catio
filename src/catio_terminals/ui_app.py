"""Main NiceGUI application for terminal editor."""

from __future__ import annotations

import logging
from pathlib import Path

from nicegui import app, ui

from catio_terminals import ui_components, ui_dialogs
from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import (
    CompositeTypesConfig,
    RuntimeSymbolsConfig,
    TerminalConfig,
)
from catio_terminals.service_file import FileService

logger = logging.getLogger(__name__)

# Path to runtime symbols YAML file
RUNTIME_SYMBOLS_PATH = Path(__file__).parent / "config" / "runtime_symbols.yaml"

# Path to composite types YAML file
COMPOSITE_TYPES_PATH = Path(__file__).parent / "config" / "composite_types.yaml"

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
        self.selected_terminal_id: str | None = None
        self.bulk_add_count: int = 0
        self.runtime_symbols: RuntimeSymbolsConfig | None = None
        self.composite_types: CompositeTypesConfig | None = None
        self.merged_terminals: set[str] = set()  # Track terminals with XML merged
        self.filtered_terminal_ids: list[str] = []  # Track currently filtered terminals
        self.details_header_label: ui.label | None = None  # Header label for details
        self.details_product_link: ui.link | None = None  # Product info link
        self.delete_terminal_button: ui.button | None = None  # Delete terminal button
        self._load_runtime_symbols()
        self._load_composite_types()

    def _load_runtime_symbols(self) -> None:
        """Load runtime symbols configuration."""
        if RUNTIME_SYMBOLS_PATH.exists():
            try:
                self.runtime_symbols = RuntimeSymbolsConfig.from_yaml(
                    RUNTIME_SYMBOLS_PATH
                )
                logger.info(
                    f"Loaded {len(self.runtime_symbols.runtime_symbols)} "
                    "runtime symbols"
                )
            except Exception as e:
                logger.warning(f"Failed to load runtime symbols: {e}")
                self.runtime_symbols = None
        else:
            logger.warning(f"Runtime symbols file not found: {RUNTIME_SYMBOLS_PATH}")
            self.runtime_symbols = None

    def _load_composite_types(self) -> None:
        """Load composite types configuration."""
        if COMPOSITE_TYPES_PATH.exists():
            try:
                self.composite_types = CompositeTypesConfig.from_yaml(
                    COMPOSITE_TYPES_PATH
                )
                logger.info(
                    f"Loaded {len(self.composite_types.composite_types)} "
                    "composite types"
                )
            except Exception as e:
                logger.warning(f"Failed to load composite types: {e}")
                self.composite_types = None
        else:
            logger.warning(f"Composite types file not found: {COMPOSITE_TYPES_PATH}")
            self.composite_types = None

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

    def shutdown(self) -> None:
        """Shutdown the application server."""
        app.shutdown()


def run(file_path: Path | None = None) -> None:
    """Run the terminal editor application.

    Args:
        file_path: Optional path to YAML file to open directly
    """
    # Store pending file path for deferred loading on editor page
    pending_file: dict[str, Path | None] = {"path": file_path}

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

        # If file_path provided, go directly to editor (loading happens there)
        if pending_file["path"] is not None:
            ui.navigate.to("/editor")
            return

        ui.label("CATio Terminal Editor").classes("text-h3 mb-4")
        # Show file selector
        await ui_dialogs.show_file_selector(editor)

    @ui.page("/editor")
    async def editor_page() -> None:
        """Editor page."""
        ui.dark_mode().enable()

        editor = get_editor()

        # Check if we need to load a pending file from CLI
        if pending_file["path"] is not None and editor.config is None:
            file_to_load = pending_file["path"]
            pending_file["path"] = None  # Clear so we don't reload on refresh

            # Show loading UI while file loads
            with ui.column().classes("w-full h-screen items-center justify-center"):
                ui.label(f"Loading {file_to_load.name}...").classes("text-h5")
                ui.spinner(size="xl")

            # Load file in background then refresh page
            async def load_and_refresh() -> None:
                await ui_dialogs.load_file_async(editor, file_to_load)
                # Refresh page to show editor
                ui.navigate.reload()

            ui.timer(0.1, load_and_refresh, once=True)
            return

        # If no config loaded, redirect to index
        if editor.config is None:
            ui.navigate.to("/")
            return

        # Add custom CSS
        ui.add_head_html(
            """
        <style>
            body, #app {
                overflow: hidden !important;
                height: 100vh;
            }
            .main-container {
                height: calc(100vh - 60px);
                display: flex;
                flex-direction: column;
            }
        </style>
        """
        )

        with ui.header():
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label("CATio Terminal Editor").classes("text-h6")
                    if editor.current_file:
                        ui.label(f"{editor.current_file}").classes(
                            "text-xs text-gray-200"
                        )

                with ui.row().classes("gap-2"):
                    ui.button(
                        "Save",
                        icon="save",
                        on_click=lambda: ui_dialogs.show_save_confirmation_dialog(
                            editor
                        ),
                    )

                    ui.button(
                        "Save As",
                        icon="save_as",
                        on_click=lambda: ui_dialogs.show_save_as_dialog(editor),
                    )

                    ui.button(
                        "Open",
                        icon="folder_open",
                        on_click=lambda: ui_dialogs.show_close_editor_dialog(editor),
                    )

                    ui.button(
                        "Exit",
                        icon="exit_to_app",
                        on_click=lambda: ui_dialogs.show_exit_dialog(editor),
                    ).props("color=negative")

                    ui.button(
                        "Add Terminal",
                        icon="add",
                        on_click=lambda: ui_dialogs.show_add_terminal_dialog(editor),
                    ).props("color=primary")

                    ui.button(
                        "Fetch Terminal Database",
                        icon="download",
                        on_click=lambda: ui_dialogs.show_fetch_database_dialog(editor),
                    ).props("color=secondary")

        with ui.column().classes("main-container w-full"):
            # Unsaved changes indicator
            if editor.has_unsaved_changes:
                with ui.row().classes(
                    "w-full justify-center bg-orange-900 py-1 flex-shrink-0"
                ):
                    ui.icon("warning").classes("text-orange-300")
                    ui.label("You have unsaved changes").classes(
                        "text-sm text-orange-300 font-bold"
                    )

            with (
                ui.splitter(value=30)
                .classes("w-full")
                .style("flex: 1; min-height: 0") as splitter
            ):
                with splitter.before:
                    with ui.card().classes("w-full h-full flex flex-col"):
                        # Header with count
                        terminal_count = (
                            len(editor.config.terminal_types) if editor.config else 0
                        )
                        with ui.row().classes(
                            "w-full items-center justify-between mb-2"
                        ):
                            terminal_count_label = ui.label(
                                f"Terminal Types ({terminal_count})"
                            ).classes("text-h6")

                            async def delete_filtered():
                                await ui_dialogs.show_delete_filtered_terminals_dialog(
                                    editor, editor.filtered_terminal_ids
                                )

                            delete_all_button = (
                                ui.button(
                                    icon="delete_sweep",
                                    on_click=delete_filtered,
                                )
                                .props("flat dense color=negative")
                                .tooltip("Delete All Terminals")
                            )

                        # Search filter
                        search_input = (
                            ui.input(
                                placeholder="Filter terminals...",
                            )
                            .classes("w-full mb-2")
                            .props("dense clearable")
                        )

                        def filter_tree(e):
                            search_term = e.args.lower() if e.args else ""
                            if editor.tree_widget and editor.tree_data:
                                if search_term:
                                    filtered = [
                                        node
                                        for node in editor.tree_data.values()
                                        if search_term in node["label"].lower()
                                    ]
                                else:
                                    filtered = list(editor.tree_data.values())
                                editor.tree_widget._props["nodes"] = filtered  # noqa: SLF001
                                editor.tree_widget.update()
                                # Update filtered terminal IDs
                                editor.filtered_terminal_ids = [
                                    node["id"] for node in filtered
                                ]
                                # Update count label and delete button tooltip
                                filtered_count = len(filtered)
                                terminal_count_label.text = (
                                    f"Terminal Types ({filtered_count})"
                                )
                                if search_term:
                                    plural = "s" if filtered_count != 1 else ""
                                    delete_all_button.tooltip(
                                        f"Delete {filtered_count} "
                                        f"Filtered Terminal{plural}"
                                    )
                                else:
                                    delete_all_button.tooltip("Delete All Terminals")

                        search_input.on("update:model-value", filter_tree)

                        editor.tree_container = (
                            ui.column()
                            .classes("w-full overflow-y-auto pr-2 pb-4")
                            .style("flex: 1; min-height: 0;")
                        )
                        assert editor.tree_container is not None
                        with editor.tree_container:
                            await editor.build_tree_view()

                with splitter.after:
                    with ui.card().classes("w-full h-full flex flex-col"):
                        with ui.row().classes(
                            "w-full items-center justify-between mb-2"
                        ):
                            with ui.row().classes("items-center gap-2"):
                                editor.details_header_label = ui.label(
                                    "Details"
                                ).classes("text-h6")
                                editor.details_product_link = (
                                    ui.link("", target="")
                                    .props("target=_blank")
                                    .classes("text-blue-400")
                                )
                                editor.details_product_link.visible = False

                            async def delete_terminal():
                                if editor.selected_terminal_id:
                                    await ui_dialogs.show_delete_terminal_dialog(
                                        editor, editor.selected_terminal_id
                                    )

                            delete_terminal_button = ui.button(
                                "Delete Terminal",
                                icon="delete",
                                on_click=delete_terminal,
                            ).props("flat dense color=negative")
                            delete_terminal_button.visible = False
                            editor.delete_terminal_button = delete_terminal_button
                        editor.details_container = (
                            ui.column()
                            .classes("w-full overflow-y-auto pr-2 pb-4")
                            .style("flex: 1; min-height: 0;")
                        )
                        assert editor.details_container is not None
                        with editor.details_container:
                            ui.label("Select a terminal to view details").classes(
                                "text-gray-500"
                            )

    ui.run(title="CATio Terminal Editor", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    run()
