"""Utilities for fetching and parsing Beckhoff terminal information."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

from catio_terminals.models import Identity, SymbolNode, TerminalType

logger = logging.getLogger(__name__)


@dataclass
class BeckhoffTerminalInfo:
    """Information about a Beckhoff terminal from the website."""

    terminal_id: str
    name: str
    description: str
    url: str


class BeckhoffClient:
    """Client for fetching Beckhoff terminal information."""

    BASE_URL = "https://www.beckhoff.com"
    SEARCH_API = f"{BASE_URL}/en-us/products/i-o/ethercat-terminals/"
    XML_DOWNLOAD_URL = "https://download.beckhoff.com/download/configuration-files/io/ethercat/xml-device-description/Beckhoff_EtherCAT_XML.zip"

    def __init__(self) -> None:
        """Initialize Beckhoff client."""
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
            },
        )
        self.cache_dir = Path.home() / ".cache" / "catio_terminals"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.xml_cache_file = self.cache_dir / "Beckhoff_EtherCAT_XML.zip"
        self.xml_extract_dir = self.cache_dir / "beckhoff_xml"
        self.terminals_cache_file = self.cache_dir / "terminals_cache.json"
        self.xml_map_cache_file = self.cache_dir / "xml_map_cache.json"
        self._cached_terminals: list[BeckhoffTerminalInfo] | None = None
        self._xml_file_map: dict[str, str] | None = None

    def get_cached_terminals(self) -> list[BeckhoffTerminalInfo] | None:
        """Get terminals from cache if available.

        Returns:
            List of cached terminals or None if cache doesn't exist
        """
        if self._cached_terminals:
            return self._cached_terminals

        if self.terminals_cache_file.exists():
            try:
                import json

                with self.terminals_cache_file.open("r") as f:
                    data = json.load(f)

                self._cached_terminals = [BeckhoffTerminalInfo(**item) for item in data]
                logger.info(
                    f"Loaded {len(self._cached_terminals)} terminals from cache"
                )
                return self._cached_terminals
            except Exception as e:
                logger.error(f"Failed to load terminals cache: {e}")
                return None

        return None

    def _save_terminals_cache(self, terminals: list[BeckhoffTerminalInfo]) -> None:
        """Save terminals to cache.

        Args:
            terminals: List of terminals to cache
        """
        try:
            import json
            from dataclasses import asdict

            with self.terminals_cache_file.open("w") as f:
                json.dump([asdict(t) for t in terminals], f, indent=2)

            self._cached_terminals = terminals
            logger.info(f"Saved {len(terminals)} terminals to cache")
        except Exception as e:
            logger.error(f"Failed to save terminals cache: {e}")

    def _download_xml_files(self) -> bool:
        """Download and extract Beckhoff XML files if not cached.

        Returns:
            True if files are available, False otherwise
        """
        import zipfile

        # Check if already extracted
        if self.xml_extract_dir.exists() and list(self.xml_extract_dir.glob("*.xml")):
            logger.debug("XML files already cached")
            return True

        try:
            # Download ZIP file if not cached
            if not self.xml_cache_file.exists():
                logger.info(
                    f"Downloading Beckhoff XML files from {self.XML_DOWNLOAD_URL}"
                )
                response = self.client.get(self.XML_DOWNLOAD_URL)
                response.raise_for_status()

                with self.xml_cache_file.open("wb") as f:
                    f.write(response.content)
                logger.info(f"Downloaded {len(response.content)} bytes")

            # Extract ZIP file
            logger.info(f"Extracting XML files to {self.xml_extract_dir}")
            self.xml_extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(self.xml_cache_file, "r") as zip_ref:
                zip_ref.extractall(self.xml_extract_dir)

            logger.info("XML files extracted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download/extract XML files: {e}", exc_info=True)
            return False

    def _parse_xml_files(self, query: str = "") -> list[BeckhoffTerminalInfo]:
        """Parse Beckhoff XML files to extract terminal information.

        Args:
            query: Search query string

        Returns:
            List of terminal information
        """
        terminals = []
        seen_ids = set()

        try:
            # Find all XML files in the extracted directory
            xml_files = list(self.xml_extract_dir.rglob("*.xml"))
            logger.debug(f"Found {len(xml_files)} XML files")

            for xml_file in xml_files:
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    # Look for Device elements in the ESI XML structure
                    # ESI files use various namespaces, so we'll search broadly
                    for device in root.iter():
                        if device.tag.endswith("Device") or device.tag.endswith(
                            "Devices"
                        ):
                            # Extract Type (terminal ID)
                            type_elem = device.find(".//*[@ProductCode]/..")
                            if type_elem is None:
                                continue

                            # Try to get the terminal ID from the Type element
                            terminal_id = None
                            for child in device.iter():
                                if "Type" in child.tag:
                                    type_text = child.text
                                    if type_text and type_text.startswith(
                                        ("EL", "EK", "EP", "ES", "EJ")
                                    ):
                                        terminal_id = type_text.strip()
                                        break

                            # Also check for ProductCode and use filename as fallback
                            if not terminal_id:
                                # Try to extract from filename
                                filename = xml_file.stem
                                import re

                                match = re.search(
                                    r"(E[LKPSJ]\d{4})", filename, re.IGNORECASE
                                )
                                if match:
                                    terminal_id = match.group(1).upper()

                            if not terminal_id or terminal_id in seen_ids:
                                continue

                            seen_ids.add(terminal_id)

                            # Extract name/description
                            name = terminal_id
                            description = f"Terminal {terminal_id}"

                            for child in device.iter():
                                if "Name" in child.tag and child.text:
                                    name = child.text.strip()
                                if "Info" in child.tag or "Description" in child.tag:
                                    if child.text:
                                        description = child.text.strip()

                            terminals.append(
                                BeckhoffTerminalInfo(
                                    terminal_id=terminal_id,
                                    name=name,
                                    description=description,
                                    url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/{terminal_id.lower()}/",
                                )
                            )

                except Exception as e:
                    logger.debug(f"Failed to parse {xml_file.name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse XML files: {e}", exc_info=True)

        # Filter by query if provided
        if query:
            query_lower = query.lower()
            terminals = [
                t
                for t in terminals
                if query_lower in t.terminal_id.lower()
                or query_lower in t.name.lower()
                or query_lower in t.description.lower()
            ]

        return terminals

    async def fetch_and_parse_xml(
        self, progress_callback=None
    ) -> list[BeckhoffTerminalInfo]:
        """Fetch XML files and parse all terminals with progress updates.

        Args:
            progress_callback: Optional callback function(message: str, progress: float)
                              where progress is 0.0 to 1.0

        Returns:
            List of all terminals found
        """
        import asyncio

        terminals = []
        seen_ids = set()

        try:
            # Step 1: Download XML files
            if progress_callback:
                progress_callback("Downloading XML files...", 0.1)

            if not self._download_xml_files():
                return []

            # Step 2: Parse XML files
            if progress_callback:
                progress_callback("Parsing XML files...", 0.2)

            xml_files = list(self.xml_extract_dir.rglob("*.xml"))
            logger.info(f"Found {len(xml_files)} XML files to parse")
            total_files = len(xml_files)

            for idx, xml_file in enumerate(xml_files):
                # Yield control frequently to prevent blocking and keep websocket alive
                if idx % 3 == 0:
                    await asyncio.sleep(0.01)

                if idx % 5 == 0 and progress_callback:
                    progress = 0.2 + (0.7 * idx / total_files)
                    progress_callback(
                        f"Parsing file {idx + 1}/{total_files}...", progress
                    )

                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    for device in root.iter():
                        if device.tag.endswith("Device") or device.tag.endswith(
                            "Devices"
                        ):
                            type_elem = device.find(".//*[@ProductCode]/..")
                            if type_elem is None:
                                continue

                            terminal_id = None
                            for child in device.iter():
                                if "Type" in child.tag:
                                    type_text = child.text
                                    if type_text and type_text.startswith(
                                        ("EL", "EK", "EP", "ES", "EJ")
                                    ):
                                        terminal_id = type_text.strip()
                                        break

                            if not terminal_id:
                                filename = xml_file.stem
                                import re

                                match = re.search(
                                    r"(E[LKPSJ]\d{4})", filename, re.IGNORECASE
                                )
                                if match:
                                    terminal_id = match.group(1).upper()

                            if not terminal_id or terminal_id in seen_ids:
                                continue

                            seen_ids.add(terminal_id)

                            name = terminal_id
                            description = f"Terminal {terminal_id}"

                            for child in device.iter():
                                if "Name" in child.tag and child.text:
                                    name = child.text.strip()
                                if "Info" in child.tag or "Description" in child.tag:
                                    if child.text:
                                        description = child.text.strip()

                            terminals.append(
                                BeckhoffTerminalInfo(
                                    terminal_id=terminal_id,
                                    name=name,
                                    description=description,
                                    url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/{terminal_id.lower()}/",
                                )
                            )

                except Exception as e:
                    logger.debug(f"Failed to parse {xml_file.name}: {e}")
                    continue

            # Step 3: Save to cache
            if progress_callback:
                progress_callback("Saving to cache...", 0.95)

            self._save_terminals_cache(terminals)

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
            List of terminal information
        """
        logger.info(f"Searching for terminals: {query}")

        # Try to get cached terminals first
        terminals = self.get_cached_terminals()

        if not terminals:
            logger.warning("No cached terminals found, using fallback data")
            # Fallback to hardcoded common terminals
            terminals = [
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

        # Filter by query if provided
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

    def _load_xml_map(self) -> dict[str, str]:
        """Load or build a map of terminal IDs to XML file paths.

        Returns:
            Dictionary mapping terminal IDs to XML file paths
        """
        if self._xml_file_map:
            return self._xml_file_map

        # Try to load from cache
        if self.xml_map_cache_file.exists():
            try:
                import json

                with self.xml_map_cache_file.open("r") as f:
                    self._xml_file_map = json.load(f)
                logger.debug(f"Loaded XML map with {len(self._xml_file_map)} entries")
                return self._xml_file_map
            except Exception as e:
                logger.debug(f"Failed to load XML map cache: {e}")

        # Build the map by scanning XML files
        import json
        import re

        self._xml_file_map = {}
        logger.info("Building XML file map...")

        for xml_file in self.xml_extract_dir.rglob("*.xml"):
            try:
                # Extract terminal IDs from filename or content
                terminal_ids = re.findall(
                    r"\b(E[LKPSJ]\d{4})\b", xml_file.name, re.IGNORECASE
                )
                for terminal_id in terminal_ids:
                    self._xml_file_map[terminal_id.upper()] = str(xml_file)
            except Exception as e:
                logger.debug(f"Error processing {xml_file.name}: {e}")

        # Save to cache
        try:
            with self.xml_map_cache_file.open("w") as f:
                json.dump(self._xml_file_map, f, indent=2)
            logger.info(f"Saved XML map with {len(self._xml_file_map)} entries")
        except Exception as e:
            logger.debug(f"Failed to save XML map cache: {e}")

        return self._xml_file_map

    async def fetch_terminal_xml(self, terminal_id: str) -> str | None:
        """Fetch XML description for a terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL4004")

        Returns:
            XML content as string, or None if not found
        """
        logger.info(f"Fetching XML for terminal: {terminal_id}")

        # Ensure XML files are downloaded
        if not self._download_xml_files():
            logger.error("Could not download XML files")
            return None

        # Load XML map
        xml_map = self._load_xml_map()

        # Check if we have a direct mapping
        if terminal_id.upper() in xml_map:
            xml_file_path = Path(xml_map[terminal_id.upper()])
            try:
                with xml_file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    logger.info(f"Found XML for {terminal_id} in {xml_file_path.name}")
                    return content
            except Exception as e:
                logger.error(f"Error reading cached XML file: {e}")

        # Fallback: search all files (shouldn't happen often)
        import re

        logger.debug(f"Terminal {terminal_id} not in map, searching files...")
        for xml_file in self.xml_extract_dir.rglob("*.xml"):
            try:
                with xml_file.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if re.search(rf"\b{terminal_id}\b", content, re.IGNORECASE):
                        logger.info(f"Found XML for {terminal_id} in {xml_file.name}")
                        # Update the map for next time
                        xml_map[terminal_id.upper()] = str(xml_file)
                        return content
            except Exception as e:
                logger.debug(f"Error reading {xml_file.name}: {e}")
                continue

        logger.warning(f"No XML file found for terminal {terminal_id}")
        return None

    def parse_terminal_xml(self, xml_content: str, terminal_id: str) -> TerminalType:
        """Parse terminal XML and create TerminalType.

        Args:
            xml_content: XML content string
            terminal_id: Terminal ID

        Returns:
            TerminalType instance

        Raises:
            ValueError: If XML parsing fails
        """
        try:
            root = ET.fromstring(xml_content)
            # Parse XML structure - this is a simplified example
            # Real ESI XML files have a complex structure

            description = root.findtext(
                ".//Description", default=f"Terminal {terminal_id}"
            )

            # Extract identity information
            vendor_id = int(root.findtext(".//VendorId", default="2"))
            product_code = int(root.findtext(".//ProductCode", default="0"), 0)
            revision = int(root.findtext(".//RevisionNo", default="0"), 0)

            identity = Identity(
                vendor_id=vendor_id,
                product_code=product_code,
                revision_number=revision,
            )

            # Extract symbol nodes - simplified
            symbol_nodes = []
            for symbol in root.findall(".//Symbol"):
                name = symbol.findtext("Name", "")
                index_group = int(symbol.findtext("IndexGroup", "0"), 0)
                size = int(symbol.findtext("Size", "0"))
                ads_type = int(symbol.findtext("DataType", "0"))

                symbol_nodes.append(
                    SymbolNode(
                        name_template=name,
                        index_group=index_group,
                        size=size,
                        ads_type=ads_type,
                        type_name=symbol.findtext("TypeName", "UNKNOWN"),
                        channels=1,
                    )
                )

            return TerminalType(
                description=description,
                identity=identity,
                symbol_nodes=symbol_nodes,
            )

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"Invalid XML content: {e}") from e

    def create_default_terminal(
        self, terminal_id: str, description: str
    ) -> TerminalType:
        """Create a default terminal type with placeholder values.

        Args:
            terminal_id: Terminal ID
            description: Terminal description

        Returns:
            TerminalType instance with default values
        """
        # Parse terminal ID to estimate channel count
        # E.g., EL4004 = 4 channels, EL1008 = 8 channels
        try:
            channel_count = int(terminal_id[-1])
        except (ValueError, IndexError):
            channel_count = 1

        # Determine symbol name based on terminal type
        if terminal_id.startswith("EL1"):  # Digital input
            symbol_name = "DI Input Channel {channel}"
            type_name = "DI Input Channel 1_TYPE"
        elif terminal_id.startswith("EL2"):  # Digital output
            symbol_name = "DO Output Channel {channel}"
            type_name = "DO Output Channel 1_TYPE"
        elif terminal_id.startswith("EL3"):  # Analog input
            symbol_name = "AI Input Channel {channel}"
            type_name = "AI Input Channel 1_TYPE"
        elif terminal_id.startswith("EL4"):  # Analog output
            symbol_name = "AO Output Channel {channel}"
            type_name = "AO Output Channel 1_TYPE"
        else:
            symbol_name = "Channel {channel}"
            type_name = "Channel 1_TYPE"

        return TerminalType(
            description=description,
            identity=Identity(
                vendor_id=2,  # Beckhoff vendor ID
                product_code=0x0,
                revision_number=0x00100000,
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template=symbol_name,
                    index_group=0xF030,
                    size=2,
                    ads_type=65,
                    type_name=type_name,
                    channels=channel_count,
                ),
                SymbolNode(
                    name_template="WcState^WcState",
                    index_group=0xF021,
                    size=0,
                    ads_type=33,
                    type_name="BIT",
                    channels=1,
                ),
            ],
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
