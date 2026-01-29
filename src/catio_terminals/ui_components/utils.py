"""Utility functions for UI components."""

from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp


def _mark_changed(app: "TerminalEditorApp", action) -> None:
    """Mark that changes have been made and execute the action.

    Args:
        app: Terminal editor application instance
        action: Function to execute
    """
    # Set the flag and run JavaScript BEFORE the action, which may clear UI elements
    app.has_unsaved_changes = True
    # Show the unsaved changes banner
    if app.unsaved_changes_banner:
        app.unsaved_changes_banner.visible = True
    try:
        ui.run_javascript("window.hasUnsavedChanges = true;")
    except RuntimeError:
        # Silently ignore if element context is invalid - the flag is already set
        pass
    action()
