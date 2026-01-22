"""Configuration service for managing terminal configuration state."""

from typing import TYPE_CHECKING

from catio_terminals.models import TerminalConfig, TerminalType

if TYPE_CHECKING:
    from catio_terminals.beckhoff import BeckhoffClient


class ConfigService:
    """Service for managing terminal configuration state."""

    @staticmethod
    def build_tree_data(
        config: TerminalConfig, beckhoff_client: "BeckhoffClient | None" = None
    ) -> dict[str, dict]:
        """Build tree data structure from configuration.

        Args:
            config: Terminal configuration
            beckhoff_client: Optional Beckhoff client to check has_coe from cache

        Returns:
            Dictionary of tree nodes
        """
        # Build lookup map for has_coe from cached terminals
        has_coe_map: dict[str, bool] = {}
        if beckhoff_client is not None:
            cached_terminals = beckhoff_client.get_cached_terminals()
            if cached_terminals:
                has_coe_map = {t.terminal_id: t.has_coe for t in cached_terminals}

        tree_data: dict[str, dict] = {}
        if config.terminal_types:
            for terminal_id, terminal in sorted(config.terminal_types.items()):
                # Use cleaned description, fall back to terminal_id
                description = (
                    terminal.description.replace("\n", " ").strip()
                    if terminal.description
                    else terminal_id
                )
                # Use different icon for terminals with CoE objects
                # Check cache first, fall back to checking actual CoE objects
                has_coe = has_coe_map.get(terminal_id, len(terminal.coe_objects) > 0)
                icon = "settings_ethernet" if has_coe else "memory"
                tree_data[terminal_id] = {
                    "id": terminal_id,
                    "label": f"{terminal_id} - {description}",
                    "icon": icon,
                }
        return tree_data

    @staticmethod
    def get_terminal(config: TerminalConfig, terminal_id: str) -> TerminalType | None:
        """Get terminal by ID.

        Args:
            config: Terminal configuration
            terminal_id: Terminal ID

        Returns:
            Terminal or None if not found
        """
        if config.terminal_types:
            return config.terminal_types.get(terminal_id)
        return None
