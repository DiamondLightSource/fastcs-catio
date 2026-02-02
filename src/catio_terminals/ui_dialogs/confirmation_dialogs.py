"""Confirmation and exit dialog functions."""

import logging
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)


async def show_save_confirmation_dialog(app: "TerminalEditorApp") -> None:
    """Show save confirmation dialog.

    Args:
        app: Terminal editor application instance
    """
    if not app.config or not app.current_file:
        ui.notify("No file loaded", type="warning")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label("Save Configuration").classes("text-h6")
        ui.label(f"Save changes to {app.current_file.name}?").classes("text-caption")

        result = {"confirm": False}

        def confirm_save():
            result["confirm"] = True
            dialog.close()

        def cancel_save():
            result["confirm"] = False
            dialog.close()

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancel", on_click=cancel_save).props("flat")
            ui.button("Save", on_click=confirm_save).props("color=primary")

    await dialog

    if result["confirm"]:
        await app.save_file()


async def show_close_editor_dialog(app: "TerminalEditorApp") -> None:
    """Show close editor confirmation dialog if there are unsaved changes.

    Args:
        app: Terminal editor application instance
    """
    if app.has_unsaved_changes:
        with ui.dialog() as dialog, ui.card():
            ui.label("Unsaved Changes").classes("text-h6")
            ui.label("You have unsaved changes. What would you like to do?").classes(
                "text-caption"
            )

            result = {"action": "cancel"}

            def save_and_close():
                result["action"] = "save"
                dialog.close()

            def discard_and_close():
                result["action"] = "discard"
                dialog.close()

            def exit_app():
                result["action"] = "exit"
                dialog.close()

            def cancel_close():
                result["action"] = "cancel"
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=cancel_close).props("flat")
                ui.button("Discard Changes", on_click=discard_and_close).props(
                    "flat color=negative"
                )
                ui.button("Save & Close", on_click=save_and_close).props(
                    "color=primary"
                )
                ui.button("Exit", on_click=exit_app).props("flat color=warning")

        await dialog

        if result["action"] == "save":
            await app.save_file()
            app.config = None
            app.current_file = None
            app.has_unsaved_changes = False
            ui.navigate.to("/")
        elif result["action"] == "discard":
            app.config = None
            app.current_file = None
            app.has_unsaved_changes = False
            ui.navigate.to("/")
        elif result["action"] == "exit":
            # Try multiple methods to close the browser tab
            ui.run_javascript(
                """
                window.open('', '_self').close();
                window.close();
                setTimeout(() => {
                    window.location.href = 'about:blank';
                }, 100);
                """
            )
            app.shutdown()
    else:
        app.config = None
        app.current_file = None
        ui.navigate.to("/")


async def show_exit_dialog(app: "TerminalEditorApp") -> None:
    """Show exit confirmation dialog.

    Args:
        app: Terminal editor application instance
    """
    if app.has_unsaved_changes:
        with ui.dialog() as dialog, ui.card():
            ui.label("Exit Application").classes("text-h6")
            ui.label("You have unsaved changes. What would you like to do?").classes(
                "text-caption"
            )

            result: dict[str, str] = {"action": "cancel"}

            def save_and_exit():
                result["action"] = "save"
                dialog.close()

            def discard_and_exit():
                result["action"] = "discard"
                dialog.close()

            def cancel_exit():
                result["action"] = "cancel"
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=cancel_exit).props("flat")
                ui.button("Discard", on_click=discard_and_exit).props("color=negative")
                ui.button("Save & Exit", on_click=save_and_exit).props("color=primary")

        await dialog

        if result["action"] == "save":
            await app.save_file()
            _do_exit(app)
        elif result["action"] == "discard":
            _do_exit(app)
        # If cancel, do nothing
    else:
        _do_exit(app)


def _do_exit(app: "TerminalEditorApp") -> None:
    """Perform the actual exit."""
    ui.run_javascript(
        """
        window.open('', '_self').close();
        window.close();
        setTimeout(() => {
            window.location.href = 'about:blank';
        }, 100);
        """
    )
    app.shutdown()
