"""Database-related dialog functions."""

import asyncio
import logging
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)


async def show_fetch_database_dialog(app: "TerminalEditorApp") -> None:
    """Show fetch terminal database progress dialog.

    Args:
        app: Terminal editor application instance
    """
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
        # Fetch and parse the XML asynchronously with progress updates
        await app.beckhoff_client.fetch_and_parse_xml(update_progress)
        ui.notify("Terminal database updated successfully", type="positive")
    except Exception as e:
        logger.exception("Failed to fetch terminal database")
        ui.notify(f"Failed to fetch database: {e}", type="negative")
    finally:
        dialog.close()
