"""File-related dialog functions."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.service_file import FileService

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)


def _import_show_exit_dialog():
    """Lazy import to avoid circular dependency."""
    from catio_terminals.ui_dialogs.confirmation_dialogs import show_exit_dialog

    return show_exit_dialog


async def show_file_selector(app: "TerminalEditorApp") -> None:
    """Show simple file path input dialog.

    Args:
        app: Terminal editor application instance
    """
    with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
        ui.label("Select Terminal YAML File").classes("text-lg font-bold mb-4")

        ui.label("Enter or paste the file path:").classes(
            "text-caption text-gray-400 mb-2"
        )

        # Simple file path input with autocomplete
        file_path = (
            ui.input(
                label="File Path",
                placeholder=f"{Path.cwd()}/terminals.yaml",
                autocomplete=[
                    str(p)
                    for p in Path.cwd().rglob("*.yaml")
                    if not any(part.startswith(".") for part in p.parts)
                ][:50],  # Limit to 50 files for performance
            )
            .classes("w-full")
            .props("clearable")
        )

        # Set initial value to cwd
        file_path.value = str(Path.cwd()) + "/"

        # Handle Enter key to trigger Open
        file_path.on("keydown.enter", lambda: _open_file(app, dialog, file_path.value))

        async def cancel_and_exit():
            dialog.close()
            show_exit_dialog_fn = _import_show_exit_dialog()
            await show_exit_dialog_fn(app)

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=cancel_and_exit).props("flat")
            ui.button(
                "Create New",
                icon="note_add",
                on_click=lambda: _create_new_file(app, dialog, file_path.value),
            ).props("flat color=secondary")
            ui.button(
                "Open",
                icon="folder_open",
                on_click=lambda: _open_file(app, dialog, file_path.value),
            ).props("color=primary")

    dialog.open()


async def _create_new_file(
    app: "TerminalEditorApp", dialog: ui.dialog, file_path: str
) -> None:
    """Create a new YAML file.

    Args:
        app: Terminal editor application instance
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

    app.config = FileService.create_file(path)
    app.current_file = path
    app.has_unsaved_changes = False
    dialog.close()
    await app.build_editor_ui()
    ui.notify(f"Created new file: {path.name}", type="positive")


async def load_file_async(app: "TerminalEditorApp", path: Path) -> bool:
    """Load a YAML file asynchronously without UI notifications.

    Args:
        app: Terminal editor application instance
        path: Path to file

    Returns:
        True if file loaded successfully, False otherwise
    """
    if not path.exists():
        logger.error(f"File does not exist: {path}")
        return False

    try:
        app.config = FileService.open_file(path)
        app.current_file = path
        app.has_unsaved_changes = False
        app.merged_terminals.clear()  # Reset merged tracking for new file

        # Mark all YAML symbols as selected (they're in the file)
        for terminal in app.config.terminal_types.values():
            for sym in terminal.symbol_nodes:
                sym.selected = True
            for coe in terminal.coe_objects:
                coe.selected = True

        logger.info(f"Successfully loaded {path.name}")
        return True
    except Exception:
        logger.exception(f"Failed to open file: {path}")
        return False


async def open_file_from_cli(app: "TerminalEditorApp", file_path: str) -> None:
    """Open an existing YAML file from CLI.

    Args:
        app: Terminal editor application instance
        file_path: Path to file
    """
    await load_file_async(app, Path(file_path))
    ui.navigate.to("/editor")


async def _open_file(
    app: "TerminalEditorApp", dialog: ui.dialog | None, file_path: str
) -> None:
    """Open an existing YAML file.

    Args:
        app: Terminal editor application instance
        dialog: Dialog to close (None if called from CLI)
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
        app.config = FileService.open_file(path)
        app.current_file = path
        app.has_unsaved_changes = False
        app.merged_terminals.clear()  # Reset merged tracking for new file

        # Mark all YAML symbols as selected (they're in the file)
        for terminal in app.config.terminal_types.values():
            for sym in terminal.symbol_nodes:
                sym.selected = True
            for coe in terminal.coe_objects:
                coe.selected = True

        if dialog is not None:
            dialog.close()
        await app.build_editor_ui()
        ui.notify(f"Opened: {path.name}", type="positive")
    except Exception as e:
        logger.exception("Failed to open file")
        ui.notify(f"Failed to open file: {e}", type="negative")


async def show_save_as_dialog(app: "TerminalEditorApp") -> None:
    """Show save as dialog to save configuration to a new file.

    Args:
        app: Terminal editor application instance
    """
    if not app.config:
        ui.notify("No file loaded", type="warning")
        return

    # Default path
    default_path = str(Path.cwd() / "terminals.yaml")
    if app.current_file:
        default_path = str(app.current_file)

    with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
        ui.label("Save As").classes("text-h6 mb-4")

        ui.label("Enter the file path:").classes("text-caption text-gray-400 mb-2")

        file_path = (
            ui.input(
                label="File Path",
                value=default_path,
            )
            .classes("w-full")
            .props("clearable")
        )

        result: dict[str, str | None] = {"path": None}

        def confirm_save():
            path_str = file_path.value.strip()
            if path_str:
                # Ensure .yaml extension
                if not path_str.endswith((".yaml", ".yml")):
                    path_str += ".yaml"
                result["path"] = path_str
            dialog.close()

        # Handle Enter key to trigger Save
        file_path.on("keydown.enter", lambda: confirm_save())

        def cancel_save():
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=cancel_save).props("flat")
            ui.button("Save", icon="save", on_click=confirm_save).props("color=primary")

    await dialog

    if result["path"]:
        try:
            new_path = Path(result["path"])
            FileService.save_file(app.config, new_path)
            app.current_file = new_path
            app.has_unsaved_changes = False
            ui.run_javascript("window.hasUnsavedChanges = false;")
            ui.notify(f"Saved as: {new_path.name}", type="positive")
            # Refresh to update header with new filename
            ui.navigate.reload()
        except Exception as e:
            logger.exception("Failed to save file")
            ui.notify(f"Failed to save: {e}", type="negative")
