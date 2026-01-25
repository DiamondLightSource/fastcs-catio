#!/usr/bin/env python3
"""Script to clean up terminal YAML files by syncing with Beckhoff XML.

This script:
1. Creates a backup of the original file as xxx.original.yaml
2. Loads the YAML file
3. Merges with XML data (dropping non-XML symbols)
4. Selects all symbols from XML
5. Saves the cleaned file back

Usage:
    uv run python scripts/cleanup_yaml.py <yaml_file>
    uv run python scripts/cleanup_yaml.py --all  # Process all non-analog files
"""

import argparse
import asyncio
import logging
import shutil
from pathlib import Path

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.service_file import FileService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def cleanup_yaml_file(yaml_path: Path, beckhoff_client: BeckhoffClient) -> bool:
    """Clean up a single YAML file.

    Args:
        yaml_path: Path to YAML file
        beckhoff_client: Beckhoff client for fetching XML

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Processing: {yaml_path.name}")

    # Create backup if it doesn't exist
    backup_path = yaml_path.with_suffix(".original.yaml")
    if not backup_path.exists():
        shutil.copy(yaml_path, backup_path)
        logger.info(f"  Created backup: {backup_path.name}")
    else:
        logger.info(f"  Backup already exists: {backup_path.name}")

    # Load the YAML file
    config = FileService.open_file(yaml_path)
    logger.info(f"  Loaded {len(config.terminal_types)} terminals")

    # Merge with XML data (this drops non-XML symbols)
    await FileService.merge_xml_data(config, beckhoff_client)

    # Select ALL symbols from XML, but no CoE objects
    for terminal_id, terminal in config.terminal_types.items():
        selected_count = 0
        for symbol in terminal.symbol_nodes:
            symbol.selected = True
            selected_count += 1
        for coe in terminal.coe_objects:
            coe.selected = False
        logger.info(f"  {terminal_id}: selected {selected_count} symbols, 0 CoE")

    # Save the cleaned file
    config.to_yaml(yaml_path)
    logger.info(f"  Saved: {yaml_path.name}")

    return True


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Clean up terminal YAML files")
    parser.add_argument("file", nargs="?", help="YAML file to clean up")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all non-analog YAML files in terminals directory",
    )
    args = parser.parse_args()

    # Initialize Beckhoff client
    beckhoff_client = BeckhoffClient()

    # Ensure XML cache is available
    if not beckhoff_client.get_cached_terminals():
        logger.error(
            "No terminal cache found. Run 'catio-terminals --update-cache' first."
        )
        return

    if args.all:
        # Process all non-analog files
        terminals_dir = Path("src/fastcs_catio/terminals")
        files_to_process = terminals_dir.glob("*.yaml")

        for yaml_path in files_to_process:
            if yaml_path.exists():
                if "original" in yaml_path.name:
                    logger.info(f"Skipping backup file: {yaml_path.name}")
                    continue
                await cleanup_yaml_file(yaml_path, beckhoff_client)
            else:
                logger.warning(f"File not found: {yaml_path}")

    elif args.file:
        yaml_path = Path(args.file)
        if not yaml_path.exists():
            logger.error(f"File not found: {yaml_path}")
            return
        await cleanup_yaml_file(yaml_path, beckhoff_client)

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
