"""Utilities for fetching and parsing Beckhoff terminal information."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass

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

    def __init__(self) -> None:
        """Initialize Beckhoff client."""
        self.client = httpx.Client(timeout=30.0)

    async def search_terminals(self, query: str = "") -> list[BeckhoffTerminalInfo]:
        """Search for Beckhoff terminals.

        Args:
            query: Search query string

        Returns:
            List of terminal information

        Note:
            This is a simplified implementation. In practice, you would need to
            scrape the Beckhoff website or use their API if available.
            For now, this returns some common terminal types as examples.
        """
        # This is a placeholder - in a real implementation, you would scrape
        # the Beckhoff website or use an API
        logger.info(f"Searching for terminals: {query}")

        common_terminals = [
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
            BeckhoffTerminalInfo(
                terminal_id="EL4034",
                name="4-channel Analog Output +/-10V",
                description="4-channel analog output terminal +/-10V, 12-bit",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el4034/",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL4134",
                name="4-channel Analog Output +/-10V 16-bit",
                description="4-channel analog output terminal +/-10V, 16-bit",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el4134/",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL5101",
                name="1-channel Incremental Encoder",
                description="1-channel encoder terminal, incremental, 24V DC",
                url=f"{self.BASE_URL}/en-us/products/i-o/ethercat-terminals/el5101/",
            ),
        ]

        if query:
            query_lower = query.lower()
            return [
                t
                for t in common_terminals
                if query_lower in t.terminal_id.lower() or query_lower in t.name.lower()
            ]
        return common_terminals

    async def fetch_terminal_xml(self, terminal_id: str) -> str | None:
        """Fetch XML description for a terminal.

        Args:
            terminal_id: Terminal ID (e.g., "EL4004")

        Returns:
            XML content as string, or None if not found

        Note:
            This is a placeholder. In practice, you would need to download
            the ESI XML file from Beckhoff's website or TwinCAT installation.
        """
        logger.info(f"Fetching XML for terminal: {terminal_id}")

        # Placeholder - return None for now
        # In a real implementation, you would:
        # 1. Download ESI files from Beckhoff
        # 2. Parse the XML to extract terminal information
        # 3. Return the XML content
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
