"""Dialog functions for the terminal editor application."""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from nicegui import ui

from catio_terminals.service_file import FileService
from catio_terminals.service_terminal import TerminalService

if TYPE_CHECKING:
    from catio_terminals.ui_app import TerminalEditorApp

logger = logging.getLogger(__name__)

# Human-readable group type mapping
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
            await show_exit_dialog(app)

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
        app.selected_terminal_id = None
        app.has_unsaved_changes = True
        await app.build_editor_ui()
        ui.notify(
            f"Deleted {terminal_count} terminal{'s' if terminal_count != 1 else ''}",
            type="info",
        )


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

            # Separate terminals into already added and available
            already_added = [
                term
                for term in terminals
                if TerminalService.is_terminal_already_added(app.config, term)
            ]
            filtered_terminals = [
                term
                for term in terminals
                if not TerminalService.is_terminal_already_added(app.config, term)
            ]

            # Update tracked list for "Add All" button
            filtered_terminals_list = filtered_terminals.copy()

            # Update status label
            total_matching = len(terminals)
            already_added_count = len(already_added)
            available_count = len(filtered_terminals)
            status_label.text = (
                f"Showing {available_count} available terminal(s) "
                f"({already_added_count} already added, {total_matching} total matches)"
            )

            # Update Add All button visibility
            add_all_btn.visible = available_count > 0

            with results_container:
                if not filtered_terminals:
                    if terminals:
                        ui.label("All matching terminals are already added").classes(
                            "text-gray-500"
                        )
                    else:
                        ui.label("No terminals found").classes("text-gray-500")
                else:
                    for term in filtered_terminals:
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
                        with (
                            ui.row()
                            .classes(
                                "w-full items-center gap-2 p-2 hover:bg-gray-700"
                                " rounded"
                            )
                            .style("min-width: 0")
                        ):
                            with ui.column().classes("flex-1").style("min-width: 0"):
                                ui.label(f"{term.terminal_id} - {description}").classes(
                                    "overflow-hidden text-ellipsis whitespace-nowrap"
                                )
                                ui.label(f"Type: {group_label}").classes(
                                    "text-xs text-gray-400"
                                )
                            ui.button(
                                "Add",
                                on_click=lambda t=term: _add_terminal_and_refresh(
                                    app, t, search_terminals
                                ),
                            ).props("color=primary")

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

    # Use TerminalService to handle the logic with lazy loading enabled
    await TerminalService.add_terminal_from_beckhoff(
        app.config,
        terminal_info,
        app.beckhoff_client,
        lazy_load=True,
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
