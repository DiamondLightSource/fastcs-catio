"""Beckhoff terminal client - simplified facade over XML cache and parser modules."""

import logging
import re
from pathlib import Path

from catio_terminals.models import TerminalType
from catio_terminals.xml_cache import BeckhoffTerminalInfo, XmlCache
from catio_terminals.xml_parser import (
    create_default_terminal,
    parse_terminal_catalog,
    parse_terminal_details,
)

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["BeckhoffClient", "BeckhoffTerminalInfo"]


class BeckhoffClient:
    """Client for fetching and parsing Beckhoff terminal information.

    This is a simplified facade that delegates to:
    - XmlCache: for downloading and caching XML files
    - xml_parser: for parsing terminal data from XML
    """

    BASE_URL = "https://www.beckhoff.com"

    def __init__(self, max_terminals: int = 0) -> None:
        """Initialize Beckhoff client.

        Args:
            max_terminals: Maximum terminals to fetch (0 = unlimited)
        """
        self.max_terminals = max_terminals
        self._cache = XmlCache()

    # Expose cache paths for backwards compatibility
    @property
    def cache_dir(self) -> Path:
        """Cache directory path."""
        return self._cache.cache_dir

    @property
    def xml_extract_dir(self) -> Path:
        """XML extraction directory path."""
        return self._cache.xml_dir

    @property
    def terminals_cache_file(self) -> Path:
        """Terminals cache file path."""
        return self._cache.terminals_file

    def get_cached_terminals(self) -> list[BeckhoffTerminalInfo] | None:
        """Get terminals from cache if available."""
        return self._cache.load_terminals()

    async def fetch_and_parse_xml(
        self, progress_callback=None
    ) -> list[BeckhoffTerminalInfo]:
        """Fetch XML files and parse all terminals with progress updates.

        Args:
            progress_callback: Optional callback(message: str, progress: float)

        Returns:
            List of all terminals found
        """
        import asyncio

        try:
            # Step 1: Download XML files
            if progress_callback:
                progress_callback("Downloading XML files...", 0.1)

            if not self._cache.download_and_extract():
                return []

            # Step 2: Parse XML files
            if progress_callback:
                progress_callback("Parsing XML files...", 0.2)

            xml_files = self._cache.get_xml_files()
            logger.info(f"Found {len(xml_files)} XML files to parse")

            # Wrap progress callback to add offset and yield control
            async def async_progress(msg: str, prog: float):
                await asyncio.sleep(0.01)  # Yield control
                if progress_callback:
                    adjusted = 0.2 + (0.7 * prog)
                    progress_callback(msg, adjusted)

            # Parse with yielding for async
            terminals = []
            seen_ids: set[str] = set()
            total_files = len(xml_files)

            for idx, xml_file in enumerate(xml_files):
                await asyncio.sleep(0.01)  # Yield control

                if idx % 5 == 0 and progress_callback:
                    progress = 0.2 + (0.7 * idx / total_files)
                    progress_callback(
                        f"Parsing file {idx + 1}/{total_files}...", progress
                    )

                batch = parse_terminal_catalog(
                    [xml_file],
                    max_terminals=0,  # No limit per file
                )

                for terminal in batch:
                    if terminal.terminal_id not in seen_ids:
                        seen_ids.add(terminal.terminal_id)
                        terminals.append(terminal)

                        if (
                            self.max_terminals > 0
                            and len(terminals) >= self.max_terminals
                        ):
                            break

                if self.max_terminals > 0 and len(terminals) >= self.max_terminals:
                    logger.info(f"Reached max_terminals limit of {self.max_terminals}")
                    break

            # Step 3: Save to cache
            if progress_callback:
                progress_callback("Saving to cache...", 0.95)

            self._cache.save_terminals(terminals)

            if progress_callback:
                progress_callback(f"Done! Found {len(terminals)} terminals", 1.0)

            logger.info(f"Fetched and parsed {len(terminals)} terminals")
            return terminals

        except Exception as e:
            logger.error(f"Failed to fetch and parse XML: {e}", exc_info=True)
            if progress_callback:
                progress_callback(f"Error: {e}", 0.0)
            return []

    async def search_terminals(self, query: str = "") -> list[BeckhoffTerminalInfo]:
        """Search for Beckhoff terminals using cached data.

        Args:
            query: Search query string

        Returns:
            List of matching terminal information
        """
        logger.info(f"Searching for terminals: {query}")

        terminals = self.get_cached_terminals()

        if not terminals:
            logger.warning("No cached terminals found, using fallback data")
            terminals = self._get_fallback_terminals()

        if query:
            query_lower = query.lower()
            terminals = [
                t
                for t in terminals
                if query_lower in t.terminal_id.lower()
                or query_lower in t.name.lower()
                or query_lower in t.description.lower()
            ]

        logger.info(f"Found {len(terminals)} matching terminals")
        return terminals

    def _get_fallback_terminals(self) -> list[BeckhoffTerminalInfo]:
        """Get hardcoded fallback terminals when cache is empty."""
        return [
            BeckhoffTerminalInfo(
                terminal_id="EL1008",
                name="8-channel Digital Input 24V DC",
                description="8-channel digital input terminal 24V DC, 3ms",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el1008/",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL2008",
                name="8-channel Digital Output 24V DC",
                description="8-channel digital output terminal 24V DC, 0.5A",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el2008/",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL3064",
                name="4-channel Analog Input 0..10V",
                description="4-channel analog input terminal 0..10V, 12-bit",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el3064/",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL4004",
                name="4-channel Analog Output 0..10V",
                description="4-channel analog output terminal 0..10V, 12-bit",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el4004/",
            ),
        ]

    async def fetch_terminal_xml(self, terminal_id: str) -> str | None:
        """Fetch XML description for a terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL4004")

        Returns:
            XML content as string, or None if not found
        """
        logger.info(f"Fetching XML for terminal: {terminal_id}")

        # Try cached terminals first
        terminals = self.get_cached_terminals()
        if terminals:
            for terminal in terminals:
                if terminal.terminal_id == terminal_id and terminal.xml_file:
                    xml_path = Path(terminal.xml_file)
                    if xml_path.exists():
                        try:
                            content = xml_path.read_text(
                                encoding="utf-8", errors="ignore"
                            )
                            logger.info(
                                f"Found XML for {terminal_id} in {xml_path.name}"
                            )
                            return content
                        except Exception as e:
                            logger.error(f"Error reading cached XML: {e}")
                    break

        # Fallback: search all files
        if not self._cache.download_and_extract():
            logger.error("Could not download XML files")
            return None

        logger.debug(f"Terminal {terminal_id} not in cache, searching files...")
        for xml_file in self._cache.get_xml_files():
            try:
                content = xml_file.read_text(encoding="utf-8", errors="ignore")
                if re.search(rf"\b{terminal_id}\b", content, re.IGNORECASE):
                    logger.info(f"Found XML for {terminal_id} in {xml_file.name}")
                    return content
            except Exception as e:
                logger.debug(f"Error reading {xml_file.name}: {e}")

        logger.warning(f"No XML file found for terminal {terminal_id}")
        return None

    def parse_terminal_xml(
        self,
        xml_content: str,
        terminal_id: str,
        group_type: str | None = None,
    ) -> TerminalType:
        """Parse terminal XML and create TerminalType.

        Args:
            xml_content: XML content string
            terminal_id: Terminal ID
            group_type: Optional terminal group type

        Returns:
            TerminalType instance
        """
        result = parse_terminal_details(xml_content, terminal_id, group_type)
        if result is None:
            return create_default_terminal(
                terminal_id, f"Terminal {terminal_id}", group_type
            )
        # Unpack tuple - parse_terminal_details returns (TerminalType, composite_types)
        terminal, _composite_types = result
        return terminal

    def create_default_terminal(
        self,
        terminal_id: str,
        description: str,
        group_type: str | None = None,
    ) -> TerminalType:
        """Create a default terminal type with placeholder values."""
        return create_default_terminal(terminal_id, description, group_type)

    def close(self) -> None:
        """Close the HTTP client."""
        self._cache.close()
