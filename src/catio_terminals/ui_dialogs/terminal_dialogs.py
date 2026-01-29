"""Terminal addition dialog functions."""

import asyncio
import logging
from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.service_terminal import TerminalService

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)

# Human-readable group type mapping
# TODO I figure this should be parsed from the XML
GROUP_TYPE_LABELS = {
    "All": "All",
    "DigIn": "Digital Input",
    "DigOut": "Digital Output",
    "AnaIn": "Analog Input",
    "AnaInFast": "Analog Input (Fast)",
    "AnaOut": "Analog Output",
    "AnaOutFast": "Analog Output (Fast)",
    "PowerSupply": "Power Supply",
    "CpBk": "Bus Couplers",
    "System": "System",
    "SystemBk": "System (Bus)",
    "Communication": "Communication",
    "Measuring": "Measuring",
    "Multifunction": "Multifunction",
    "Safety": "Safety",
    "SafetyTerminals": "Safety Terminals",
    "SafetyCoupler": "Safety Couplers",
    "SafetyFieldbusBoxes": "Safety Fieldbus Boxes",
    "FieldbusBoxEP1xxx": "Fieldbus Box EP1xxx",
    "FieldbusBoxEP2xxx": "Fieldbus Box EP2xxx",
    "FieldbusBoxEP3xxx": "Fieldbus Box EP3xxx",
    "FieldbusBoxEP4xxx": "Fieldbus Box EP4xxx",
    "FieldbusBoxEP5xxx": "Fieldbus Box EP5xxx",
    "FieldbusBoxEP6xxx": "Fieldbus Box EP6xxx",
    "FieldbusBoxEP7xxx": "Fieldbus Box EP7xxx",
    "FieldbusBoxEP8xxx": "Fieldbus Box EP8xxx",
    "FieldbusBoxEPP1xxx": "Fieldbus Box EPP1xxx",
    "FieldbusBoxEPP2xxx": "Fieldbus Box EPP2xxx",
    "FieldbusBoxEPP3xxx": "Fieldbus Box EPP3xxx",
    "FieldbusBoxEPP4xxx": "Fieldbus Box EPP4xxx",
    "FieldbusBoxEPP5xxx": "Fieldbus Box EPP5xxx",
    "FieldbusBoxEPP6xxx": "Fieldbus Box EPP6xxx",
    "FieldbusBoxEPP7xxx": "Fieldbus Box EPP7xxx",
    "FieldbusBoxEPX1xxx": "Fieldbus Box EPX1xxx",
    "EJ_Coupler": "EJ Couplers",
    "EKM": "EKM",
    "ELM": "ELM",
    "DriveAxisTerminals": "Drive Axis Terminals",
    "Other": "Other",
}


async def show_add_terminal_dialog(app: "TerminalEditorApp") -> None:
    """Show dialog to add a new terminal.

    Args:
        app: Terminal editor application instance
    """
    # Determine initial group type based on selected terminal
    initial_group_type = "All"
    if app.selected_terminal_id and app.config:
        selected_terminal = app.config.terminal_types.get(app.selected_terminal_id)
        if selected_terminal and selected_terminal.group_type:
            # Only use the group type if it's in our labels dictionary
            if selected_terminal.group_type in GROUP_TYPE_LABELS:
                initial_group_type = selected_terminal.group_type

    with ui.dialog() as dialog, ui.card().classes("w-[600px]"):
        ui.label("Add Terminal Type").classes("text-lg font-bold mb-4")

        # Filter and search on same row
        with ui.row().classes("w-full gap-2 items-end mb-2"):
            with ui.column().classes("flex-none w-48"):
                ui.label("Filter by Type").classes("text-caption text-gray-600")
                group_filter = ui.select(
                    options=GROUP_TYPE_LABELS,
                    value=initial_group_type,
                )

            with ui.column().classes("flex-1"):
                ui.label("Search Terminals").classes("text-caption text-gray-600")
                search_input = ui.input(
                    placeholder="Search terminals...",
                ).classes("w-full")

        # Status line showing counts
        status_label = ui.label("").classes("text-sm text-gray-400 mb-2")

        # Results container
        results_container = ui.column().classes("w-full max-h-64 overflow-y-auto")

        # Track filtered terminals for "Add All" functionality
        filtered_terminals_list: list = []

        async def search_terminals() -> None:
            """Search for terminals."""
            nonlocal filtered_terminals_list
            if not app.config:
                return

            results_container.clear()
            terminals = await app.beckhoff_client.search_terminals(search_input.value)

            # Filter by group type if not "All"
            selected_group = group_filter.value
            if selected_group and selected_group != "All":
                terminals = [
                    term for term in terminals if term.group_type == selected_group
                ]

            # Check which terminals are already added
            available_terminals = [
                term
                for term in terminals
                if not TerminalService.is_terminal_already_added(app.config, term)
            ]

            # Update tracked list for "Add All" button (only available ones)
            filtered_terminals_list = available_terminals.copy()

            # Update status label
            total_matching = len(terminals)
            already_added_count = total_matching - len(available_terminals)
            available_count = len(available_terminals)
            status_label.text = (
                f"Showing {total_matching} terminal(s) "
                f"({already_added_count} already added, {available_count} available)"
            )

            # Update Add All button visibility
            add_all_btn.visible = available_count > 0

            with results_container:
                if not terminals:
                    ui.label("No terminals found").classes("text-gray-500")
                else:
                    for term in terminals:
                        is_already_added = TerminalService.is_terminal_already_added(
                            app.config, term
                        )
                        # Use cleaned description, matching Terminal Types list format
                        description = (
                            term.description.replace("\n", " ").strip()
                            if term.description
                            else term.terminal_id
                        )
                        # Show group type label
                        group_label = GROUP_TYPE_LABELS.get(
                            term.group_type, term.group_type
                        )
                        row_classes = "w-full items-center gap-2 p-2 rounded"
                        if is_already_added:
                            row_classes += " opacity-60"
                        else:
                            row_classes += " hover:bg-gray-700"
                        with ui.row().classes(row_classes).style("min-width: 0"):
                            with ui.column().classes("flex-1").style("min-width: 0"):
                                ui.label(f"{term.terminal_id} - {description}").classes(
                                    "overflow-hidden text-ellipsis whitespace-nowrap"
                                )
                                label_text = f"Type: {group_label}"
                                if is_already_added:
                                    label_text += " (already added)"
                                ui.label(label_text).classes("text-xs text-gray-400")
                            add_btn = ui.button(
                                "Add",
                                on_click=lambda t=term: _add_terminal_and_refresh(
                                    app, t, search_terminals
                                ),
                            ).props("color=primary")
                            if is_already_added:
                                add_btn.disable()

        # Trigger search when group filter changes or search input changes
        group_filter.on("update:model-value", search_terminals)
        search_input.on("keydown.enter", search_terminals)
        search_input.on("keyup", search_terminals)

        async def add_all_terminals() -> None:
            """Add all filtered terminals."""
            if not filtered_terminals_list:
                ui.notify("No terminals to add", type="warning")
                return

            count = len(filtered_terminals_list)

            # Track bulk add count for notification later
            app.bulk_add_count = count

            # Create progress dialog
            with ui.dialog() as progress_dialog, ui.card():
                ui.label(f"Adding {count} terminals...").classes("text-lg mb-4")
                progress_label = ui.label("0 of 0").classes(
                    "text-sm text-gray-400 mb-2"
                )
                progress_bar = ui.linear_progress(value=0, show_value=False).props(
                    "instant-feedback"
                )

            progress_dialog.open()

            try:
                # Add terminals with progress updates
                for idx, terminal_info in enumerate(filtered_terminals_list, 1):
                    # Yield before starting to keep connection alive
                    await asyncio.sleep(0.001)

                    await _add_terminal_from_beckhoff(
                        app, terminal_info, notify=False, rebuild_tree=False
                    )

                    # Update progress (safely check if elements still exist)
                    try:
                        progress_value = idx / count
                        progress_bar.value = progress_value
                        progress_label.text = f"{idx} of {count}"
                    except (RuntimeError, AttributeError):
                        pass  # Dialog was closed, continue without updates

                    # Yield after each terminal to keep connection alive
                    await asyncio.sleep(0.001)
            finally:
                # Ensure dialog is closed
                try:
                    progress_dialog.close()
                except (RuntimeError, AttributeError):
                    pass

            # Rebuild tree view and refresh search
            try:
                # Force tree rebuild outside dialog context
                await app.build_tree_view()
                await search_terminals()
            except (RuntimeError, AttributeError):
                pass  # Dialog context lost, ignore

        with ui.row().classes("w-full justify-between gap-2 mt-4"):
            add_all_btn = ui.button(
                "Add All",
                on_click=add_all_terminals,
            ).props("color=primary")
            ui.button("Close", on_click=dialog.close).props("flat")

    async def on_dialog_close() -> None:
        """Rebuild tree when dialog closes."""
        if app.has_unsaved_changes:
            await app.build_tree_view()
            # Show notification if terminals were added in bulk
            if hasattr(app, "bulk_add_count") and app.bulk_add_count > 0:
                ui.notify(f"Added {app.bulk_add_count} terminal(s)", type="positive")
                app.bulk_add_count = 0

    dialog.on("close", on_dialog_close)
    dialog.open()
    # Show filtered results immediately
    await search_terminals()


async def _add_terminal_and_refresh(
    app: "TerminalEditorApp", terminal_info, refresh_callback
) -> None:
    """Add terminal and refresh the search results.

    Args:
        app: Terminal editor application instance
        terminal_info: BeckhoffTerminalInfo instance
        refresh_callback: Function to refresh search results
    """
    await _add_terminal_from_beckhoff(app, terminal_info)
    await refresh_callback()


async def _add_terminal_from_beckhoff(
    app: "TerminalEditorApp",
    terminal_info,
    notify: bool = True,
    rebuild_tree: bool = True,
) -> None:
    """Add terminal from Beckhoff information.

    Args:
        app: Terminal editor application instance
        terminal_info: BeckhoffTerminalInfo instance
        notify: Whether to show notification (default True)
        rebuild_tree: Whether to rebuild tree view (default True)
    """
    if not app.config:
        return

    # Use TerminalService to handle the logic with lazy loading
    await TerminalService.add_terminal_from_beckhoff(
        app.config,
        terminal_info,
        app.beckhoff_client,
    )

    app.has_unsaved_changes = True
    # Store the last added terminal for scrolling
    app.last_added_terminal = terminal_info.terminal_id
    # Don't mark as merged - let lazy loading handle XML merge when terminal is viewed
    # Rebuild the tree view without navigating (which would close the dialog)
    if rebuild_tree:
        await app.build_tree_view()
    if notify:
        ui.notify(f"Added terminal: {terminal_info.terminal_id}", type="positive")


async def _add_manual_terminal(
    app: "TerminalEditorApp",
    terminal_id: str,
    description: str,
    dialog: ui.dialog,
) -> None:
    """Add terminal manually.

    Args:
        app: Terminal editor application instance
        terminal_id: Terminal ID
        description: Terminal description
        dialog: Dialog to close
    """
    if not app.config:
        return

    if not terminal_id:
        ui.notify("Please enter a terminal ID", type="warning")
        return

    if terminal_id in app.config.terminal_types:
        ui.notify("Terminal ID already exists", type="warning")
        return

    terminal = app.beckhoff_client.create_default_terminal(
        terminal_id, description or f"Terminal {terminal_id}"
    )
    app.config.add_terminal(terminal_id, terminal)
    app.has_unsaved_changes = True
    dialog.close()
    await app.build_editor_ui()
    ui.notify(f"Added terminal: {terminal_id}", type="positive")
