"""Details pane component for displaying terminal and symbol information."""

from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp


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
