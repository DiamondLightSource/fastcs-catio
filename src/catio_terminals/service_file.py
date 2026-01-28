"""File operations service for terminal configuration files."""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import TerminalConfig

if TYPE_CHECKING:
    from catio_terminals.models import TerminalType

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file operations."""

    @staticmethod
    def open_file(file_path: Path) -> TerminalConfig:
        """Open and load a terminal configuration file.

        Args:
            file_path: Path to YAML file

        Returns:
            TerminalConfig instance

        Raises:
            Exception: If file cannot be opened or parsed
        """
        logger.info(f"Opening file: {file_path}")
        return TerminalConfig.from_yaml(file_path)

    @staticmethod
    async def merge_xml_data(
        config: TerminalConfig,
        beckhoff_client: BeckhoffClient,
        prefer_xml: bool = False,
    ) -> None:
        """Merge XML data with YAML config to show all available symbols/CoE.

        For each terminal in the config, fetches the XML definition and merges
        all symbols and CoE objects, marking those in YAML as selected=True
        and those only in XML as selected=False.

        Also merges composite types from XML into the config.

        Args:
            config: Configuration to enhance with XML data
            beckhoff_client: Beckhoff client for fetching XML
            prefer_xml: If True, use XML symbol data instead of YAML when both exist
        """
        logger.info("Merging XML data with YAML configuration")

        for terminal_id, terminal in config.terminal_types.items():
            success = await FileService.merge_xml_for_terminal(
                terminal_id,
                terminal,
                beckhoff_client,
                config,  # Pass config for composite type merging
                prefer_xml=prefer_xml,
            )
            if not success:
                # If merge fails, mark all existing YAML items as selected
                for sym in terminal.symbol_nodes:
                    sym.selected = True
                for coe in terminal.coe_objects:
                    coe.selected = True
            # Yield control after each terminal
            await asyncio.sleep(0)

    @staticmethod
    async def merge_xml_for_terminal(
        terminal_id: str,
        terminal: "TerminalType",
        beckhoff_client: BeckhoffClient,
        config: TerminalConfig | None = None,
        prefer_xml: bool = False,
    ) -> bool:
        """Merge XML data for a single terminal.

        Fetches the XML definition for one terminal and merges primitive symbols
        and CoE objects, marking those in YAML as selected=True and XML-only
        as selected=False.

        Also merges composite types into the config if provided.

        Args:
            terminal_id: Terminal ID (e.g., "EL3004")
            terminal: Terminal instance to merge into
            beckhoff_client: Beckhoff client for fetching XML
            config: Optional config to merge composite types into
            prefer_xml: If True, use XML symbol data instead of YAML when both exist

        Returns:
            True if merge succeeded, False otherwise
        """
        logger.debug(f"Loading XML for terminal: {terminal_id}")

        # Fetch XML for this terminal
        xml_content = await beckhoff_client.fetch_terminal_xml(terminal_id)
        if not xml_content:
            logger.warning(f"No XML found for {terminal_id}")
            return False

        try:
            # Parse XML to get full terminal definition (primitive symbols)
            xml_terminal, composite_types = beckhoff_client.parse_terminal_xml(
                xml_content, terminal_id, terminal.group_type
            )

            # Merge composite types into the config
            if config is not None and composite_types:
                for type_name, comp_type in composite_types.items():
                    if type_name not in config.composite_types:
                        config.composite_types[type_name] = comp_type

            # Merge symbols: Create lookup of YAML symbols by name template
            yaml_symbol_map = {sym.name_template: sym for sym in terminal.symbol_nodes}

            # Determine if this is a new terminal (no YAML symbols)
            # New terminals should have all symbols selected by default
            is_new_terminal = len(yaml_symbol_map) == 0

            # Merge PDO groups from XML
            if xml_terminal.pdo_groups:
                terminal.pdo_groups = xml_terminal.pdo_groups
                # Set selected group to default if not already set
                if not terminal.selected_pdo_group:
                    terminal.selected_pdo_group = xml_terminal.selected_pdo_group

            # Build merged symbol list from XML primitive symbols
            merged_symbols = []
            xml_symbol_map = {}

            # Get active symbol indices based on PDO groups
            active_indices = (
                xml_terminal.get_active_symbol_indices()
                if xml_terminal.has_dynamic_pdos
                else set(range(len(xml_terminal.symbol_nodes)))
            )

            # Add all XML symbols (primitive symbols directly from XML)
            for idx, xml_sym in enumerate(xml_terminal.symbol_nodes):
                xml_symbol_map[xml_sym.name_template] = xml_sym
                if xml_sym.name_template in yaml_symbol_map:
                    if prefer_xml:
                        # Use XML version with selected=True
                        xml_sym.selected = True
                        merged_symbols.append(xml_sym)
                    else:
                        # Use YAML version with selected=True
                        yaml_sym = yaml_symbol_map[xml_sym.name_template]
                        yaml_sym.selected = True
                        merged_symbols.append(yaml_sym)
                else:
                    # Symbol only in XML
                    # For new terminals with dynamic PDOs: only select symbols
                    # in the default group
                    if is_new_terminal and xml_terminal.has_dynamic_pdos:
                        xml_sym.selected = idx in active_indices
                    else:
                        # For new terminals without dynamic PDOs: select all
                        # For existing terminals: not selected
                        xml_sym.selected = is_new_terminal
                    merged_symbols.append(xml_sym)

            # Warn about YAML-only symbols not in XML (these are dropped)
            for yaml_name in yaml_symbol_map:
                if yaml_name not in xml_symbol_map:
                    logger.warning(
                        f"Dropping symbol '{yaml_name}' from {terminal_id}: "
                        "not found in XML"
                    )

            terminal.symbol_nodes = merged_symbols

            # Merge CoE objects
            yaml_coe_map = {coe.index: coe for coe in terminal.coe_objects}
            # CoE objects default unselected even for new terminals (too many)
            merged_coe = []
            xml_coe_map = {}

            for xml_coe in xml_terminal.coe_objects:
                xml_coe_map[xml_coe.index] = xml_coe
                if xml_coe.index in yaml_coe_map:
                    yaml_coe = yaml_coe_map[xml_coe.index]
                    yaml_coe.selected = True
                    merged_coe.append(yaml_coe)
                else:
                    xml_coe.selected = False
                    merged_coe.append(xml_coe)

            # Warn about YAML-only CoE objects not in XML
            for yaml_idx, yaml_coe in yaml_coe_map.items():
                if yaml_idx not in xml_coe_map:
                    logger.warning(
                        f"Dropping CoE object 0x{yaml_idx:04X} '{yaml_coe.name}' "
                        f"from {terminal_id}: not found in XML"
                    )

            terminal.coe_objects = merged_coe

            pdo_groups_info = (
                f", {len(terminal.pdo_groups)} PDO groups"
                if terminal.has_dynamic_pdos
                else ""
            )
            logger.info(
                f"Merged {terminal_id}: {len(merged_symbols)} symbols, "
                f"{len(merged_coe)} CoE objects{pdo_groups_info}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to merge XML for {terminal_id}: {e}")
            return False

    @staticmethod
    def save_file(config: TerminalConfig, file_path: Path) -> None:
        """Save terminal configuration to file.

        Args:
            config: Configuration to save
            file_path: Path to save to

        Raises:
            Exception: If file cannot be saved
        """
        logger.info(f"Saving to: {file_path}")
        config.to_yaml(file_path)

    @staticmethod
    def create_file(file_path: Path) -> TerminalConfig:
        """Create a new empty terminal configuration file.

        Args:
            file_path: Path for new file

        Returns:
            New empty TerminalConfig instance

        Raises:
            Exception: If file cannot be created
        """
        logger.info(f"Creating new file: {file_path}")
        config = TerminalConfig()
        config.to_yaml(file_path)
        return config
