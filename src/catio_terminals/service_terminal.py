"""Terminal management service."""

import asyncio
import logging

from catio_terminals.beckhoff import BeckhoffClient, BeckhoffTerminalInfo
from catio_terminals.composite_symbols import convert_primitives_to_composites
from catio_terminals.models import (
    CompositeTypesConfig,
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
        composite_types: CompositeTypesConfig | None = None,
    ) -> TerminalType:
        """Add terminal from Beckhoff information.

        Args:
            config: Configuration to add terminal to
            terminal_info: BeckhoffTerminalInfo instance
            beckhoff_client: Beckhoff client for fetching XML
            composite_types: Composite types configuration for grouping primitives

        Returns:
            The added TerminalType
        """
        # Try to fetch XML, otherwise use default
        xml_content = await beckhoff_client.fetch_terminal_xml(
            terminal_info.terminal_id
        )

        if xml_content:
            try:
                terminal = beckhoff_client.parse_terminal_xml(
                    xml_content, terminal_info.terminal_id, terminal_info.group_type
                )
                # Yield control after parsing
                await asyncio.sleep(0)
            except ValueError:
                logger.error("Failed to parse XML, using default")
                terminal = beckhoff_client.create_default_terminal(
                    terminal_info.terminal_id,
                    terminal_info.description,
                    terminal_info.group_type,
                )
        else:
            terminal = beckhoff_client.create_default_terminal(
                terminal_info.terminal_id,
                terminal_info.description,
                terminal_info.group_type,
            )

        # Convert primitive symbols to composite symbols at load time
        terminal.symbol_nodes = convert_primitives_to_composites(
            terminal, composite_types
        )

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
