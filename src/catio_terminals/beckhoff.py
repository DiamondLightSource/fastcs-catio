"""Utilities for fetching and parsing Beckhoff terminal information."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

from catio_terminals.models import Identity, SymbolNode, TerminalType
from catio_terminals.utils import to_pascal_case

logger = logging.getLogger(__name__)


@dataclass
class BeckhoffTerminalInfo:
    """Information about a Beckhoff terminal from the website."""

    terminal_id: str
    name: str
    description: str
    url: str
    xml_file: str | None = None
    product_code: int = 0
    revision_number: int = 0
    group_type: str = "Other"


class BeckhoffClient:
    """Client for fetching Beckhoff terminal information."""

    BASE_URL = "https://www.beckhoff.com"
    SEARCH_API = f"{BASE_URL}/en-us/products/i-o/ethercat-terminals/"
    XML_DOWNLOAD_URL = "https://download.beckhoff.com/download/configuration-files/io/ethercat/xml-device-description/Beckhoff_EtherCAT_XML.zip"
    MAX_TERMINALS = 0  # Set to 0 to fetch all terminals

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
        self._cached_terminals: list[BeckhoffTerminalInfo] | None = None

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

                # Handle both old list format and new dict format
                if isinstance(data, dict):
                    self._cached_terminals = [
                        BeckhoffTerminalInfo(**item) for item in data.values()
                    ]
                else:
                    # Old format - list of items
                    self._cached_terminals = [
                        BeckhoffTerminalInfo(**item) for item in data
                    ]

                logger.info(
                    f"Loaded {len(self._cached_terminals)} terminals from cache"
                )
                return self._cached_terminals
            except Exception as e:
                logger.error(f"Failed to load terminals cache: {e}")
                return None

        return None

    def _save_terminals_cache(self, terminals: list[BeckhoffTerminalInfo]) -> None:
        """Save terminals to cache as dictionary keyed by terminal_id.

        Args:
            terminals: List of terminals to cache
        """
        try:
            import json
            from dataclasses import asdict

            # Convert list to dictionary keyed by terminal_id
            terminals_dict = {t.terminal_id: asdict(t) for t in terminals}

            with self.terminals_cache_file.open("w") as f:
                json.dump(terminals_dict, f, indent=2)

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

    def _generate_terminal_url(self, terminal_id: str, group_type: str) -> str:
        """Generate Beckhoff website URL based on terminal ID and group type.

        Args:
            terminal_id: Terminal ID (e.g., "EL3318")
            group_type: Terminal group type (e.g., "AnaIn")

        Returns:
            Full URL to the terminal's webpage
        """
        # Map group types to URL categories
        category_map = {
            "DigIn": "el-ed1xxx-digital-input",
            "DigOut": "el-ed2xxx-digital-output",
            "AnaIn": "el-ed3xxx-analog-input",
            "AnaOut": "el-ed4xxx-analog-output",
            "Measuring": "el5xxx-position-measurement",
            "Communication": "el6xxx-communication",
            "Motor": "el7xxx-servo-drive",
            "PowerSupply": "el9xxx-power-supply",
        }

        # Get category from group type, default to generic path
        category = category_map.get(group_type, "ethercat-terminals")

        # Generate URL
        base_path = f"{self.BASE_URL}/en-gb/products/i-o/ethercat-terminals"
        return f"{base_path}/{category}/{terminal_id.lower()}.html"

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

                    # Extract GroupType from the file (usually defined at the top)
                    group_type = "Other"
                    for group in root.iter():
                        if "GroupType" in group.tag or group.tag.endswith("Type"):
                            if group.text and group.text.strip():
                                potential_type = group.text.strip()
                                # Only use if it looks like a group type
                                terminal_prefixes = ("EL", "EK", "EP", "ES", "EJ")
                                if not potential_type.startswith(terminal_prefixes):
                                    group_type = potential_type
                                    break

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
                                    url=self._generate_terminal_url(
                                        terminal_id, group_type
                                    ),
                                    xml_file=str(xml_file),
                                    group_type=group_type,
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
                # Yield control every file to prevent blocking and keep websocket alive
                await asyncio.sleep(0.01)

                if idx % 5 == 0 and progress_callback:
                    progress = 0.2 + (0.7 * idx / total_files)
                    progress_callback(
                        f"Parsing file {idx + 1}/{total_files}...", progress
                    )

                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    # Extract GroupType from the file
                    group_type = "Other"
                    for group in root.iter():
                        if "GroupType" in group.tag:
                            if group.text and group.text.strip():
                                group_type = group.text.strip()
                                break

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

                            # Extract product code and revision from Type element
                            type_elem = device.find("Type")
                            product_code = 0
                            revision_number = 0
                            if type_elem is not None:
                                product_code_str = (
                                    type_elem.get("ProductCode") or "0"
                                ).replace("#x", "0x")
                                revision_str = (
                                    type_elem.get("RevisionNo") or "0"
                                ).replace("#x", "0x")
                                product_code = int(product_code_str, 0)
                                revision_number = int(revision_str, 0)

                            # Extract name and description
                            name = terminal_id
                            description = f"Terminal {terminal_id}"

                            for child in device.iter():
                                if "Name" in child.tag and child.text:
                                    # Use English name if available
                                    if child.get("LcId") == "1033":
                                        name = child.text.strip()
                                        # Extract description after terminal ID
                                        # for clean display
                                        desc_text = child.text.strip()
                                        if desc_text.startswith(terminal_id):
                                            desc_text = desc_text[
                                                len(terminal_id) :
                                            ].strip()
                                        description = (
                                            desc_text if desc_text else child.text
                                        )
                                        break
                                    elif not name or name == terminal_id:
                                        name = child.text.strip()

                            terminals.append(
                                BeckhoffTerminalInfo(
                                    terminal_id=terminal_id,
                                    name=name,
                                    description=description,
                                    url=self._generate_terminal_url(
                                        terminal_id, group_type
                                    ),
                                    xml_file=str(xml_file),
                                    product_code=product_code,
                                    revision_number=revision_number,
                                    group_type=group_type,
                                )
                            )

                            # Check if we've reached the limit
                            if (
                                self.MAX_TERMINALS > 0
                                and len(terminals) >= self.MAX_TERMINALS
                            ):
                                logger.info(
                                    f"Reached MAX_TERMINALS limit of "
                                    f"{self.MAX_TERMINALS}"
                                )
                                break

                except Exception as e:
                    logger.debug(f"Failed to parse {xml_file.name}: {e}")
                    continue

                # Break outer loop if we've reached the limit
                if self.MAX_TERMINALS > 0 and len(terminals) >= self.MAX_TERMINALS:
                    break

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

    async def fetch_terminal_xml(self, terminal_id: str) -> str | None:
        """Fetch XML description for a terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL4004")

        Returns:
            XML content as string, or None if not found
        """
        logger.info(f"Fetching XML for terminal: {terminal_id}")

        # Try to get from cached terminals first
        terminals = self.get_cached_terminals()
        if terminals:
            for terminal in terminals:
                if terminal.terminal_id == terminal_id and terminal.xml_file:
                    xml_file_path = Path(terminal.xml_file)
                    if xml_file_path.exists():
                        try:
                            with xml_file_path.open(
                                "r", encoding="utf-8", errors="ignore"
                            ) as f:
                                content = f.read()
                                logger.info(
                                    f"Found XML for {terminal_id} in "
                                    "{xml_file_path.name}"
                                )
                                return content
                        except Exception as e:
                            logger.error(f"Error reading cached XML file: {e}")
                    break

        # Fallback: ensure XML files are downloaded and search all files
        logger.debug(f"Terminal {terminal_id} not in cache, searching files...")
        if not self._download_xml_files():
            logger.error("Could not download XML files")
            return None
        import re

        logger.debug(f"Terminal {terminal_id} not in map, searching files...")
        for xml_file in self.xml_extract_dir.rglob("*.xml"):
            try:
                with xml_file.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if re.search(rf"\b{terminal_id}\b", content, re.IGNORECASE):
                        logger.info(f"Found XML for {terminal_id} in {xml_file.name}")
                        return content
            except Exception as e:
                logger.debug(f"Error reading {xml_file.name}: {e}")
                continue

        logger.warning(f"No XML file found for terminal {terminal_id}")
        return None

    def parse_terminal_xml(
        self, xml_content: str, terminal_id: str, group_type: str | None = None
    ) -> TerminalType:
        """Parse terminal XML and create TerminalType.

        Args:
            xml_content: XML content string
            terminal_id: Terminal ID
            group_type: Optional terminal group type

        Returns:
            TerminalType instance

        Raises:
            ValueError: If XML parsing fails
        """
        try:
            root = ET.fromstring(xml_content)

            # Find the device matching the terminal_id
            device = None
            for dev in root.findall(".//Device"):
                type_elem = dev.find("Type")
                if type_elem is not None and type_elem.text == terminal_id:
                    device = dev
                    break

            if device is None:
                logger.warning(f"Device {terminal_id} not found in XML")
                return self.create_default_terminal(
                    terminal_id, f"Terminal {terminal_id}"
                )

            # Extract Type element attributes for identity
            type_elem = device.find("Type")
            if type_elem is None:
                logger.warning(f"Type element not found for {terminal_id}")
                return self.create_default_terminal(
                    terminal_id, f"Terminal {terminal_id}"
                )

            # Handle Beckhoff's #x prefix for hex values
            product_code_str = (type_elem.get("ProductCode") or "0").replace("#x", "0x")
            revision_str = (type_elem.get("RevisionNo") or "0").replace("#x", "0x")
            product_code = int(product_code_str, 0)
            revision = int(revision_str, 0)

            # Extract name/description (prefer English LcId=1033)
            description = f"Terminal {terminal_id}"
            for name_elem in device.findall("Name"):
                if name_elem.get("LcId") == "1033":
                    if name_elem.text:
                        # Extract description after terminal ID
                        # e.g., "EL3004 4Ch. Ana. Input +/-10V" ->
                        #     "4Ch. Ana. Input +/-10V"
                        desc_text = name_elem.text.strip()
                        if desc_text.startswith(terminal_id):
                            desc_text = desc_text[len(terminal_id) :].strip()
                        description = desc_text if desc_text else name_elem.text
                    break
                elif name_elem.text:
                    description = name_elem.text

            # Extract vendor ID (should be 2 for Beckhoff)
            vendor_elem = root.find(".//Vendor/Id")
            vendor_id = (
                int(vendor_elem.text or "2")
                if vendor_elem is not None and vendor_elem.text
                else 2
            )

            identity = Identity(
                vendor_id=vendor_id,
                product_code=product_code,
                revision_number=revision,
            )

            # Extract symbol nodes from TxPdo and RxPdo
            symbol_nodes = []

            # Process TxPdo (inputs from terminal to controller)
            for pdo in device.findall(".//TxPdo"):
                for entry in pdo.findall("Entry"):
                    name = entry.findtext("Name", "")
                    if not name:  # Skip padding entries
                        continue

                    # Handle Beckhoff's #x prefix for hex values
                    index_str = entry.findtext("Index", "0").replace("#x", "0x")
                    index = int(index_str, 0)
                    _sub_index = int(entry.findtext("SubIndex") or "0")
                    bit_len = int(entry.findtext("BitLen", "0"))
                    data_type = entry.findtext("DataType", "UNKNOWN")

                    # Calculate index_group from index (upper 16 bits)
                    index_group = (index >> 16) & 0xFFFF
                    if index_group == 0:
                        index_group = 0xF020  # Default TxPdo index group

                    # Calculate access and fastcs_name
                    access = "Read-only" if index_group == 0xF020 else "Read/Write"
                    fastcs_name = to_pascal_case(name)

                    symbol_nodes.append(
                        SymbolNode(
                            name_template=name,
                            index_group=index_group,
                            size=(bit_len + 7) // 8,  # Convert bits to bytes
                            ads_type=self._get_ads_type(data_type),
                            type_name=data_type,
                            channels=1,
                            access=access,
                            fastcs_name=fastcs_name,
                        )
                    )

            # Process RxPdo (outputs from controller to terminal)
            for pdo in device.findall(".//RxPdo"):
                for entry in pdo.findall("Entry"):
                    name = entry.findtext("Name", "")
                    if not name:  # Skip padding entries
                        continue

                    # Handle Beckhoff's #x prefix for hex values
                    index_str = entry.findtext("Index", "0").replace("#x", "0x")
                    index = int(index_str, 0)
                    # TODO do we need sub_index?
                    _sub_index = int(entry.findtext("SubIndex") or "0")
                    bit_len = int(entry.findtext("BitLen", "0"))
                    data_type = entry.findtext("DataType", "UNKNOWN")

                    # Calculate index_group from index (upper 16 bits)
                    index_group = (index >> 16) & 0xFFFF
                    if index_group == 0:
                        index_group = 0xF030  # Default RxPdo index group

                    # Calculate access and fastcs_name
                    access = "Read/Write" if index_group == 0xF030 else "Read-only"
                    fastcs_name = to_pascal_case(name)

                    symbol_nodes.append(
                        SymbolNode(
                            name_template=name,
                            index_group=index_group,
                            size=(bit_len + 7) // 8,  # Convert bits to bytes
                            ads_type=self._get_ads_type(data_type),
                            type_name=data_type,
                            channels=1,
                            access=access,
                            fastcs_name=fastcs_name,
                        )
                    )

            return TerminalType(
                description=description,
                identity=identity,
                symbol_nodes=symbol_nodes,
                group_type=group_type,
            )

        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"Invalid XML content: {e}") from e
        except Exception as e:
            logger.error(f"Error parsing terminal XML: {e}", exc_info=True)
            return self.create_default_terminal(terminal_id, f"Terminal {terminal_id}")

    def _get_ads_type(self, data_type: str) -> int:
        """Map EtherCAT data types to ADS types.

        Args:
            data_type: EtherCAT data type name

        Returns:
            ADS type code
        """
        type_map = {
            "BOOL": 33,
            "BYTE": 16,
            "USINT": 16,
            "SINT": 17,
            "WORD": 18,
            "UINT": 18,
            "INT": 2,
            "DWORD": 19,
            "UDINT": 19,
            "DINT": 3,
            "REAL": 4,
            "LREAL": 5,
        }
        return type_map.get(data_type.upper(), 65)  # 65 = generic structure

    def create_default_terminal(
        self, terminal_id: str, description: str, group_type: str | None = None
    ) -> TerminalType:
        """Create a default terminal type with placeholder values.

        Args:
            terminal_id: Terminal ID
            description: Terminal description
            group_type: Optional terminal group type

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
            group_type=group_type,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
