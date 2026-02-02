"""Dialog functions for the terminal editor application."""

# Re-export all dialog functions and constants
from catio_terminals.ui_dialogs.confirmation_dialogs import (
    show_close_editor_dialog,
    show_exit_dialog,
    show_save_confirmation_dialog,
)
from catio_terminals.ui_dialogs.database_dialogs import show_fetch_database_dialog
from catio_terminals.ui_dialogs.delete_dialogs import (
    show_delete_all_terminals_dialog,
    show_delete_filtered_terminals_dialog,
    show_delete_terminal_dialog,
)
from catio_terminals.ui_dialogs.file_dialogs import (
    load_file_async,
    open_file_from_cli,
    show_file_selector,
    show_save_as_dialog,
)
from catio_terminals.ui_dialogs.terminal_dialogs import (
    GROUP_TYPE_LABELS,
    show_add_terminal_dialog,
)

__all__ = [
    # File dialogs
    "show_file_selector",
    "load_file_async",
    "open_file_from_cli",
    "show_save_as_dialog",
    # Delete dialogs
    "show_delete_terminal_dialog",
    "show_delete_all_terminals_dialog",
    "show_delete_filtered_terminals_dialog",
    # Terminal dialogs
    "show_add_terminal_dialog",
    "GROUP_TYPE_LABELS",
    # Database dialogs
    "show_fetch_database_dialog",
    # Confirmation dialogs
    "show_save_confirmation_dialog",
    "show_close_editor_dialog",
    "show_exit_dialog",
]
