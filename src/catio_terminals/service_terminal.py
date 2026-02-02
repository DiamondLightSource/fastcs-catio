"""Terminal management service."""

import logging

from catio_terminals.beckhoff import BeckhoffClient, BeckhoffTerminalInfo
from catio_terminals.models import (
    Identity,
    TerminalConfig,
    TerminalType,
)

logger = logging.getLogger(__name__)


class TerminalService:
    """Service for managing terminals."""

    @staticmethod
    def get_symbol_access(index_group: int) -> str:
        """Determine if symbol is read-only or read/write.

        Args:
            index_group: ADS index group

        Returns:
            'Read-only' or 'Read/Write'
        """
        # 0xF020 = TxPdo (inputs from terminal to controller) = Read-only
        # 0xF030 = RxPdo (outputs from controller to terminal) = Read/Write
        if index_group == 0xF020:
            return "Read-only"
        elif index_group == 0xF030:
            return "Read/Write"
        else:
            return "Unknown"

    @staticmethod
    def is_terminal_already_added(
        config: TerminalConfig, terminal_info: BeckhoffTerminalInfo
    ) -> bool:
        """Check if terminal is already in config.

        Args:
            config: Terminal configuration
            terminal_info: Terminal information to check

        Returns:
            True if terminal already exists
        """
        # First check by terminal ID
        if terminal_info.terminal_id in config.terminal_types:
            return True

        # Check if any existing terminal has same product code and revision
        # (using cached values from terminals_cache.json for speed)
        if terminal_info.product_code and terminal_info.revision_number:
            for existing_terminal in config.terminal_types.values():
                if (
                    existing_terminal.identity.product_code
                    == terminal_info.product_code
                    and existing_terminal.identity.revision_number
                    == terminal_info.revision_number
                ):
                    return True

        return False

    @staticmethod
    async def add_terminal_from_beckhoff(
        config: TerminalConfig,
        terminal_info: BeckhoffTerminalInfo,
        beckhoff_client: BeckhoffClient,
    ) -> TerminalType:
        """Add terminal from Beckhoff information with lazy loading.

        Creates a minimal terminal with no symbols initially. Symbols and CoE objects
        are loaded on-demand when the terminal is first viewed or accessed.

        Args:
            config: Configuration to add terminal to
            terminal_info: BeckhoffTerminalInfo instance
            beckhoff_client: Beckhoff client (unused in lazy load mode)

        Returns:
            The added TerminalType
        """
        # Create minimal terminal with no symbols - XML will be loaded on-demand
        terminal = TerminalType(
            description=terminal_info.description,
            identity=Identity(
                vendor_id=2,  # Beckhoff
                product_code=terminal_info.product_code or 0,
                revision_number=terminal_info.revision_number or 0x00100000,
            ),
            symbol_nodes=[],  # Empty - will be populated from XML on first view
            group_type=terminal_info.group_type,
        )
        logger.info(f"Created minimal terminal {terminal_info.terminal_id} (lazy load)")

        config.add_terminal(terminal_info.terminal_id, terminal)
        return terminal

    @staticmethod
    def delete_terminal(config: TerminalConfig, terminal_id: str) -> None:
        """Delete a terminal from configuration.

        Args:
            config: Configuration to delete from
            terminal_id: Terminal ID to delete
        """
        config.remove_terminal(terminal_id)
