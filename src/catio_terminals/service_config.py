"""Configuration service for managing terminal configuration state."""

from catio_terminals.models import TerminalConfig, TerminalType


class ConfigService:
    """Service for managing terminal configuration state."""

    @staticmethod
    def build_tree_data(config: TerminalConfig) -> dict[str, dict]:
        """Build tree data structure from configuration.

        Args:
            config: Terminal configuration

        Returns:
            Dictionary of tree nodes
        """
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
                icon = "settings_ethernet" if terminal.coe_objects else "memory"
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
