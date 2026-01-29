"""Terminal deletion dialog functions."""

import logging
from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.service_terminal import TerminalService

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)


async def show_delete_terminal_dialog(
    app: "TerminalEditorApp", terminal_id: str
) -> None:
    """Show delete terminal confirmation dialog.

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID to delete
    """
    if not app.config:
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
        # Find a terminal to select after deletion
        terminal_ids = list(app.config.terminal_types.keys())
        next_terminal_to_select = None

        if len(terminal_ids) > 1:
            # Try to select the next terminal in the list
            try:
                current_index = terminal_ids.index(terminal_id)
                # Select the next one if available, otherwise the previous one
                if current_index < len(terminal_ids) - 1:
                    next_terminal_to_select = terminal_ids[current_index + 1]
                elif current_index > 0:
                    next_terminal_to_select = terminal_ids[current_index - 1]
            except ValueError:
                # Terminal not found in list, select first one
                next_terminal_to_select = terminal_ids[0]

        TerminalService.delete_terminal(app.config, terminal_id)

        # Remove from merged tracking so XML will reload if re-added
        app.merged_terminals.discard(terminal_id)

        # Update selected terminal to the next one
        app.selected_terminal_id = next_terminal_to_select

        app.has_unsaved_changes = True
        await app.build_editor_ui()
        ui.notify(f"Deleted terminal: {terminal_id}", type="info")


async def show_delete_all_terminals_dialog(app: "TerminalEditorApp") -> None:
    """Show delete all terminals confirmation dialog.

    Args:
        app: Terminal editor application instance
    """
    if not app.config or not app.config.terminal_types:
        ui.notify("No terminals to delete", type="warning")
        return

    terminal_count = len(app.config.terminal_types)

    with ui.dialog() as dialog, ui.card():
        ui.label("Delete All Terminals?").classes("text-h6")
        ui.label(
            f"This will delete all {terminal_count} terminals. "
            "This action cannot be undone."
        ).classes("text-caption")

        result = {"confirm": False}

        def confirm_delete():
            result["confirm"] = True
            dialog.close()

        def cancel_delete():
            result["confirm"] = False
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=cancel_delete).props("flat")
            ui.button("Delete All", on_click=confirm_delete).props("color=negative")

    await dialog

    if result["confirm"]:
        app.config.terminal_types.clear()
        app.merged_terminals.clear()  # Reset merged tracking
        app.selected_terminal_id = None
        app.has_unsaved_changes = True
        await app.build_editor_ui()
        ui.notify(f"Deleted {terminal_count} terminals", type="info")


async def show_delete_filtered_terminals_dialog(
    app: "TerminalEditorApp", terminal_ids: list[str]
) -> None:
    """Show delete filtered terminals confirmation dialog.

    Args:
        app: Terminal editor application instance
        terminal_ids: List of terminal IDs to delete
    """
    if not app.config or not terminal_ids:
        ui.notify("No terminals to delete", type="warning")
        return

    terminal_count = len(terminal_ids)
    is_all = terminal_count == len(app.config.terminal_types)
    action_text = "all" if is_all else "filtered"
    plural = "s" if terminal_count != 1 else ""

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Delete {terminal_count} Terminal{plural}?").classes("text-h6")
        ui.label(
            f"This will delete {terminal_count} {action_text} "
            f"terminal{plural}. This action cannot be undone."
        ).classes("text-caption")

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
        for terminal_id in terminal_ids:
            app.config.terminal_types.pop(terminal_id, None)
            app.merged_terminals.discard(terminal_id)  # Reset merged tracking
        app.selected_terminal_id = None
        app.has_unsaved_changes = True
        await app.build_editor_ui()
        ui.notify(
            f"Deleted {terminal_count} terminal{'s' if terminal_count != 1 else ''}",
            type="info",
        )
