"""Utilities for fetching and parsing Beckhoff terminal information."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from lxml import etree

from catio_terminals.models import Identity, SymbolNode, TerminalType
from catio_terminals.utils import to_pascal_case

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
TERMINAL_ID_PATTERN = re.compile(r"(E[LKPSJ]\d{4})", re.IGNORECASE)
CHANNEL_KEYWORD_PATTERN = re.compile(
    r"(.*?)\s*(?:Channel|Ch\.?|Input|Output|AI|AO|DI|DO)\s+(\d+)(.*)",
    re.IGNORECASE,
)
CHANNEL_NUMBER_PATTERN = re.compile(r"(.+?)\s+(\d+)$")
HEX_PREFIX_PATTERN = re.compile(r"#x([0-9a-fA-F]+)")
KEYWORD_EXTRACT_PATTERN = re.compile(
    r"(Channel|Ch\.?|Input|Output|AI|AO|DI|DO)", re.IGNORECASE
)


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

    def _parse_hex_value(self, value: str) -> int:
        """Parse Beckhoff hex string to integer.

        Handles both '#x' prefix (Beckhoff format) and standard '0x' prefix.

        Args:
            value: Hex string to parse

        Returns:
            Integer value
        """
        if value.startswith("#x"):
            return int(value[2:], 16)
        return int(value, 0)

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
                    tree = etree.parse(str(xml_file))
                    root = tree.getroot()

                    # Extract GroupType using XPath (much faster than iteration)
                    group_type = "Other"
                    # Try to find GroupType element
                    group_elements = root.xpath("//*[local-name()='GroupType']")
                    if group_elements and isinstance(group_elements, list):
                        group_elem = group_elements[0]
                        if hasattr(group_elem, "text") and group_elem.text:
                            group_text = str(group_elem.text)
                            if group_text.strip():
                                potential_type = group_text.strip()
                                # Only use if it looks like a group type
                                terminal_prefixes = ("EL", "EK", "EP", "ES", "EJ")
                                if not potential_type.startswith(terminal_prefixes):
                                    group_type = potential_type
                                group_type = potential_type

                    # Use XPath to find Device elements directly
                    devices_result = root.xpath("//*[local-name()='Device']")
                    devices = devices_result if isinstance(devices_result, list) else []

                    for device in devices:
                        # Use XPath to find Type element with ProductCode
                        type_elems = device.xpath(".//*[@ProductCode]/..")
                        if not type_elems:
                            continue

                        # Try to get the terminal ID from Type elements
                        terminal_id = None
                        type_children = device.xpath(
                            ".//*[contains(local-name(), 'Type')]"
                        )
                        for child in type_children:
                            type_text = child.text
                            if type_text and type_text.startswith(
                                ("EL", "EK", "EP", "ES", "EJ")
                            ):
                                terminal_id = type_text.strip()
                                break

                        # Use pre-compiled regex to extract from filename as fallback
                        if not terminal_id:
                            filename = xml_file.stem
                            match = TERMINAL_ID_PATTERN.search(filename)
                            if match:
                                terminal_id = match.group(1).upper()

                        if not terminal_id or terminal_id in seen_ids:
                            continue

                        seen_ids.add(terminal_id)

                        # Use XPath to extract name/description more efficiently
                        name = terminal_id
                        description = f"Terminal {terminal_id}"

                        name_elems = device.xpath(".//*[local-name()='Name']")
                        for name_elem in name_elems:
                            if name_elem.text:
                                name = name_elem.text.strip()

                        info_elems = device.xpath(
                            ".//*[local-name()='Info' or local-name()='Description']"
                        )
                        for info_elem in info_elems:
                            if info_elem.text:
                                description = info_elem.text.strip()

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
                    tree = etree.parse(str(xml_file))
                    root = tree.getroot()

                    # Extract GroupType using XPath
                    group_type = "Other"
                    group_elements = root.xpath("//*[local-name()='GroupType']")
                    if group_elements and isinstance(group_elements, list):
                        group_elem = group_elements[0]
                        if hasattr(group_elem, "text") and group_elem.text:
                            group_type = str(group_elem.text).strip()

                    # Use XPath to find all Device elements directly
                    devices_result = root.xpath("//*[local-name()='Device']")
                    devices = devices_result if isinstance(devices_result, list) else []

                    for device in devices:
                        # Use XPath to check for ProductCode
                        type_elem = device.find("Type")
                        if type_elem is None:
                            continue

                        terminal_id = None
                        type_children = device.xpath(
                            ".//*[contains(local-name(), 'Type')]"
                        )
                        for child in type_children:
                            type_text = child.text
                            if type_text and type_text.startswith(
                                ("EL", "EK", "EP", "ES", "EJ")
                            ):
                                terminal_id = type_text.strip()
                                break

                        if not terminal_id:
                            filename = xml_file.stem
                            match = TERMINAL_ID_PATTERN.search(filename)
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
                            # Use helper function for hex conversion
                            product_code_str = type_elem.get("ProductCode") or "0"
                            revision_str = type_elem.get("RevisionNo") or "0"
                            product_code = self._parse_hex_value(product_code_str)
                            revision_number = self._parse_hex_value(revision_str)

                        # Use XPath to extract English name (LcId=1033)
                        name = terminal_id
                        description = f"Terminal {terminal_id}"

                        name_elems = device.xpath(".//Name[@LcId='1033']")
                        if name_elems and name_elems[0].text:
                            # Extract description after terminal ID for clean display
                            desc_text = name
                            if desc_text.startswith(terminal_id):
                                desc_text = desc_text[len(terminal_id) :].strip()
                            description = desc_text if desc_text else name
                        else:
                            # Fallback to any Name element
                            name_elems = device.xpath(".//Name")
                            if name_elems and name_elems[0].text:
                                name = name_elems[0].text.strip()

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
            # Parse XML content - lxml expects bytes or string
            if isinstance(xml_content, str):
                root = etree.fromstring(xml_content.encode("utf-8"))
            else:
                root = etree.fromstring(xml_content)

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
            product_code_str = type_elem.get("ProductCode") or "0"
            revision_str = type_elem.get("RevisionNo") or "0"
            product_code = self._parse_hex_value(product_code_str)
            revision = self._parse_hex_value(revision_str)

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

            # Dictionary to track symbols with channel patterns
            # Key: (name_pattern, index_group, size, ads_type, type_name, access)
            # Value: list of channel numbers
            channel_groups: dict = {}

            # Dictionary to track duplicate entries (same name, no channel number)
            # Key: (name, index_group, size, ads_type, type_name, access)
            # Value: count of duplicates
            duplicate_tracker: dict = {}

            # Process TxPdo (inputs from terminal to controller)
            for pdo in device.findall(".//TxPdo"):
                for entry in pdo.findall("Entry"):
                    name = entry.findtext("Name", "")
                    if not name:  # Skip padding entries
                        continue

                    # Handle Beckhoff's #x prefix for hex values
                    index_str = entry.findtext("Index", "0")
                    index = self._parse_hex_value(index_str)
                    sub_index_str = entry.findtext("SubIndex") or "0"
                    _sub_index = self._parse_hex_value(sub_index_str)
                    bit_len = int(entry.findtext("BitLen", "0"))
                    data_type = entry.findtext("DataType", "UNKNOWN")

                    # Calculate index_group from index (upper 16 bits)
                    index_group = (index >> 16) & 0xFFFF
                    if index_group == 0:
                        index_group = 0xF020  # Default TxPdo index group

                    # Calculate access and fastcs_name
                    access = "Read-only" if index_group == 0xF020 else "Read/Write"
                    size = (bit_len + 7) // 8  # Convert bits to bytes
                    ads_type = self._get_ads_type(data_type)

                    # Use pre-compiled regex for channel pattern detection
                    channel_match = CHANNEL_KEYWORD_PATTERN.search(name)
                    if not channel_match:
                        # Try matching names that end with a number
                        channel_match = CHANNEL_NUMBER_PATTERN.search(name)

                    if channel_match:
                        prefix = channel_match.group(1).strip()
                        channel_num = int(channel_match.group(2))
                        suffix = (
                            channel_match.group(3).strip()
                            if len(channel_match.groups()) > 2
                            else ""
                        )

                        # Create pattern - preserve original word if explicit
                        # (Channel/Input/etc) or use prefix with number
                        if CHANNEL_KEYWORD_PATTERN.search(name):
                            # Extract the keyword using pre-compiled pattern
                            keyword_match = KEYWORD_EXTRACT_PATTERN.search(name)
                            keyword = (
                                keyword_match.group(1) if keyword_match else "Channel"
                            )
                            if prefix and suffix:
                                name_pattern = (
                                    f"{prefix} {keyword} {{channel}} {suffix}"
                                )
                            elif prefix:
                                name_pattern = f"{prefix} {keyword} {{channel}}"
                            elif suffix:
                                name_pattern = f"{keyword} {{channel}} {suffix}"
                            else:
                                name_pattern = f"{keyword} {{channel}}"
                        else:
                            # Just name ending with number
                            name_pattern = f"{prefix} {{channel}}"

                        # Create grouping key
                        group_key = (
                            name_pattern,
                            index_group,
                            size,
                            ads_type,
                            data_type,
                            access,
                        )

                        if group_key not in channel_groups:
                            channel_groups[group_key] = []
                        channel_groups[group_key].append(channel_num)
                    else:
                        # No channel pattern - check if this is a duplicate entry
                        dup_key = (name, index_group, size, ads_type, data_type, access)

                        if dup_key in duplicate_tracker:
                            # This is a duplicate - increment count
                            duplicate_tracker[dup_key] += 1
                        else:
                            # First occurrence - track it
                            duplicate_tracker[dup_key] = 1

            # Process RxPdo (outputs from controller to terminal)
            for pdo in device.findall(".//RxPdo"):
                for entry in pdo.findall("Entry"):
                    name = entry.findtext("Name", "")
                    if not name:  # Skip padding entries
                        continue

                    # Handle Beckhoff's #x prefix for hex values
                    index_str = entry.findtext("Index", "0")
                    index = self._parse_hex_value(index_str)
                    # TODO do we need sub_index?
                    sub_index_str = entry.findtext("SubIndex") or "0"
                    _sub_index = self._parse_hex_value(sub_index_str)
                    bit_len = int(entry.findtext("BitLen", "0"))
                    data_type = entry.findtext("DataType", "UNKNOWN")

                    # Calculate index_group from index (upper 16 bits)
                    index_group = (index >> 16) & 0xFFFF
                    if index_group == 0:
                        index_group = 0xF030  # Default RxPdo index group

                    # Calculate access and fastcs_name
                    access = "Read/Write" if index_group == 0xF030 else "Read-only"
                    size = (bit_len + 7) // 8  # Convert bits to bytes
                    ads_type = self._get_ads_type(data_type)

                    # Use pre-compiled regex for channel pattern detection
                    channel_match = CHANNEL_KEYWORD_PATTERN.search(name)
                    if not channel_match:
                        # Try matching names that end with a number
                        channel_match = CHANNEL_NUMBER_PATTERN.search(name)

                    if channel_match:
                        prefix = channel_match.group(1).strip()
                        channel_num = int(channel_match.group(2))
                        suffix = (
                            channel_match.group(3).strip()
                            if len(channel_match.groups()) > 2
                            else ""
                        )

                        # Create pattern - preserve original word if explicit
                        # (Channel/Input/etc) or use prefix with number
                        if CHANNEL_KEYWORD_PATTERN.search(name):
                            # Extract the keyword using pre-compiled pattern
                            keyword_match = KEYWORD_EXTRACT_PATTERN.search(name)
                            keyword = (
                                keyword_match.group(1) if keyword_match else "Channel"
                            )
                            if prefix and suffix:
                                name_pattern = (
                                    f"{prefix} {keyword} {{channel}} {suffix}"
                                )
                            elif prefix:
                                name_pattern = f"{prefix} {keyword} {{channel}}"
                            elif suffix:
                                name_pattern = f"{keyword} {{channel}} {suffix}"
                            else:
                                name_pattern = f"{keyword} {{channel}}"
                        else:
                            # Just name ending with number
                            name_pattern = f"{prefix} {{channel}}"

                        # Create grouping key
                        group_key = (
                            name_pattern,
                            index_group,
                            size,
                            ads_type,
                            data_type,
                            access,
                        )

                        if group_key not in channel_groups:
                            channel_groups[group_key] = []
                        channel_groups[group_key].append(channel_num)
                    else:
                        # No channel pattern - check if this is a duplicate entry
                        dup_key = (name, index_group, size, ads_type, data_type, access)

                        if dup_key in duplicate_tracker:
                            # This is a duplicate - increment count
                            duplicate_tracker[dup_key] += 1
                        else:
                            # First occurrence - track it
                            duplicate_tracker[dup_key] = 1

            # Create symbol nodes for grouped channels
            for group_key, channel_nums in channel_groups.items():
                name_pattern, index_group, size, ads_type, data_type, access = group_key
                num_channels = len(channel_nums)
                fastcs_name = to_pascal_case(name_pattern)

                symbol_nodes.append(
                    SymbolNode(
                        name_template=name_pattern,
                        index_group=index_group,
                        size=size,
                        ads_type=ads_type,
                        type_name=data_type,
                        channels=num_channels,
                        access=access,
                        fastcs_name=fastcs_name,
                    )
                )

            # Create symbol nodes for duplicate entries (same name, no channel number)
            for dup_key, count in duplicate_tracker.items():
                name, index_group, size, ads_type, data_type, access = dup_key

                if count > 1:
                    # Multiple entries with same name - create symbol with {channel}
                    name_pattern = f"{name} {{channel}}"
                    fastcs_name = to_pascal_case(name_pattern)
                    symbol_nodes.append(
                        SymbolNode(
                            name_template=name_pattern,
                            index_group=index_group,
                            size=size,
                            ads_type=ads_type,
                            type_name=data_type,
                            channels=count,
                            access=access,
                            fastcs_name=fastcs_name,
                        )
                    )
                else:
                    # Single entry - create as-is
                    fastcs_name = to_pascal_case(name)
                    symbol_nodes.append(
                        SymbolNode(
                            name_template=name,
                            index_group=index_group,
                            size=size,
                            ads_type=ads_type,
                            type_name=data_type,
                            channels=1,
                            access=access,
                            fastcs_name=fastcs_name,
                        )
                    )

            # Parse CoE Objects (CANopen over EtherCAT dictionary)
            coe_objects = []

            # First, build a dictionary of DataType definitions for subindex details
            datatype_map = {}
            datatypes_section = device.find(".//Profile/Dictionary/DataTypes")
            if datatypes_section is not None:
                for datatype in datatypes_section.findall("DataType"):
                    dt_name = datatype.findtext("Name", "")
                    if not dt_name:
                        continue

                    # Store subitem information
                    subitems = []
                    for subitem in datatype.findall("SubItem"):
                        subidx_str = subitem.findtext("SubIdx", "0")
                        try:
                            subidx = int(subidx_str)
                        except ValueError:
                            continue

                        sub_name = subitem.findtext("Name", "")
                        sub_type = subitem.findtext("Type", "")
                        sub_bitsize_str = subitem.findtext("BitSize", "0")
                        try:
                            sub_bitsize = int(sub_bitsize_str)
                        except ValueError:
                            sub_bitsize = 0

                        sub_flags = subitem.find("Flags")
                        sub_access = "ro"
                        if sub_flags is not None:
                            sub_access = sub_flags.findtext("Access", "ro").lower()

                        subitems.append(
                            {
                                "subindex": subidx,
                                "name": sub_name,
                                "type": sub_type,
                                "bitsize": sub_bitsize,
                                "access": sub_access,
                            }
                        )

                    datatype_map[dt_name] = subitems

            objects_section = device.find(".//Profile/Dictionary/Objects")
            if objects_section is not None:
                for obj in objects_section.findall("Object"):
                    # Get CoE Index
                    index_str = obj.findtext("Index", "0")
                    try:
                        coe_index = self._parse_hex_value(index_str)
                    except ValueError:
                        logger.warning(f"Invalid CoE index: {index_str}")
                        continue

                    # Get object name
                    obj_name = obj.findtext("Name", "Unknown")

                    # Get data type
                    type_name = obj.findtext("Type", "UNKNOWN")

                    # Get bit size
                    bit_size = int(obj.findtext("BitSize", "0"))

                    # Get access flags
                    flags = obj.find("Flags")
                    if flags is not None:
                        access = flags.findtext("Access", "ro").lower()
                    else:
                        access = "ro"

                    # Get datatype definition for subindices
                    datatype_subitems = datatype_map.get(type_name, [])

                    # Parse SubIndices from Object's Info section
                    subindices = []
                    info_section = obj.find("Info")
                    if info_section is not None:
                        for idx, subitem in enumerate(info_section.findall("SubItem")):
                            subitem_name = subitem.findtext("Name", f"SubIndex {idx}")

                            # Get default data from the Object's Info section
                            subitem_info = subitem.find("Info")
                            default_data = None
                            if subitem_info is not None:
                                default_data = subitem_info.findtext("DefaultData")

                            # Match with DataType definition by name
                            subitem_type = None
                            subitem_bitsize = None
                            subitem_access = None
                            subindex_num = idx

                            for dt_sub in datatype_subitems:
                                if dt_sub["name"] == subitem_name:
                                    subindex_num = dt_sub["subindex"]
                                    subitem_type = dt_sub["type"]
                                    subitem_bitsize = dt_sub["bitsize"]
                                    subitem_access = dt_sub["access"]
                                    break

                            # Fallback: try to extract subindex from name
                            if subitem_type is None and "SubIndex" in subitem_name:
                                try:
                                    num_str = subitem_name.split()[-1]
                                    subindex_num = int(num_str)
                                except (ValueError, IndexError):
                                    pass

                            from catio_terminals.models import CoESubIndex

                            subindices.append(
                                CoESubIndex(
                                    subindex=subindex_num,
                                    name=subitem_name,
                                    type_name=subitem_type,
                                    bit_size=subitem_bitsize,
                                    access=subitem_access,
                                    default_data=default_data,
                                )
                            )

                    from catio_terminals.models import CoEObject

                    coe_objects.append(
                        CoEObject(
                            index=coe_index,
                            name=obj_name,
                            type_name=type_name,
                            bit_size=bit_size,
                            access=access,
                            subindices=subindices,
                        )
                    )

            return TerminalType(
                description=description,
                identity=identity,
                symbol_nodes=symbol_nodes,
                coe_objects=coe_objects,
                group_type=group_type,
            )

        except etree.ParseError as e:
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
