"""File operations service for terminal configuration files."""

import asyncio
import logging
from pathlib import Path

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import TerminalConfig

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
        config: TerminalConfig, beckhoff_client: BeckhoffClient
    ) -> None:
        """Merge XML data with YAML config to show all available symbols/CoE.

        For each terminal in the config, fetches the XML definition and merges
        all symbols and CoE objects, marking those in YAML as selected=True
        and those only in XML as selected=False.

        Args:
            config: Configuration to enhance with XML data
            beckhoff_client: Beckhoff client for fetching XML
        """
        logger.info("Merging XML data with YAML configuration")

        for terminal_id, terminal in config.terminal_types.items():
            logger.debug(f"Processing terminal: {terminal_id}")

            # Fetch XML for this terminal
            xml_content = await beckhoff_client.fetch_terminal_xml(terminal_id)
            if not xml_content:
                logger.warning(f"No XML found for {terminal_id}, skipping merge")
                continue

            try:
                # Parse XML to get full terminal definition
                xml_terminal = beckhoff_client.parse_terminal_xml(
                    xml_content, terminal_id, terminal.group_type
                )

                # Yield control after parsing
                await asyncio.sleep(0)

                # Merge symbols: Create lookup of YAML symbols by name template
                yaml_symbol_map = {
                    sym.name_template: sym for sym in terminal.symbol_nodes
                }

                # Build merged symbol list
                merged_symbols = []
                xml_symbol_map = {}

                # Add all XML symbols
                for xml_sym in xml_terminal.symbol_nodes:
                    xml_symbol_map[xml_sym.name_template] = xml_sym
                    if xml_sym.name_template in yaml_symbol_map:
                        # Symbol exists in YAML - use YAML version with selected=True
                        yaml_sym = yaml_symbol_map[xml_sym.name_template]
                        yaml_sym.selected = True
                        merged_symbols.append(yaml_sym)
                    else:
                        # Symbol only in XML - mark as not selected
                        xml_sym.selected = False
                        merged_symbols.append(xml_sym)

                # Add any YAML-only symbols not in XML (shouldn't happen but be safe)
                for yaml_name, yaml_sym in yaml_symbol_map.items():
                    if yaml_name not in xml_symbol_map:
                        yaml_sym.selected = True
                        merged_symbols.append(yaml_sym)

                terminal.symbol_nodes = merged_symbols

                # Merge CoE objects: Create lookup of YAML CoE by index
                yaml_coe_map = {coe.index: coe for coe in terminal.coe_objects}

                # Build merged CoE list
                merged_coe = []
                xml_coe_map = {}

                # Add all XML CoE objects
                for xml_coe in xml_terminal.coe_objects:
                    xml_coe_map[xml_coe.index] = xml_coe
                    if xml_coe.index in yaml_coe_map:
                        # CoE exists in YAML - use YAML version with selected=True
                        yaml_coe = yaml_coe_map[xml_coe.index]
                        yaml_coe.selected = True
                        merged_coe.append(yaml_coe)
                    else:
                        # CoE only in XML - mark as not selected
                        xml_coe.selected = False
                        merged_coe.append(xml_coe)

                # Add any YAML-only CoE not in XML (shouldn't happen but be safe)
                for yaml_idx, yaml_coe in yaml_coe_map.items():
                    if yaml_idx not in xml_coe_map:
                        yaml_coe.selected = True
                        merged_coe.append(yaml_coe)

                terminal.coe_objects = merged_coe

                logger.info(
                    f"Merged {terminal_id}: {len(merged_symbols)} symbols, "
                    f"{len(merged_coe)} CoE objects"
                )

            except Exception as e:
                logger.error(f"Failed to merge XML for {terminal_id}: {e}")
                # If merge fails, mark all existing YAML items as selected
                for sym in terminal.symbol_nodes:
                    sym.selected = True
                for coe in terminal.coe_objects:
                    coe.selected = True

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
