"""Cache management for Beckhoff XML files and terminal data."""

import json
import logging
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

XML_DOWNLOAD_URL = (
    "https://download.beckhoff.com/download/configuration-files/"
    "io/ethercat/xml-device-description/Beckhoff_EtherCAT_XML.zip"
)


@dataclass
class BeckhoffTerminalInfo:
    """Information about a Beckhoff terminal from the XML files."""

    terminal_id: str
    name: str
    description: str
    url: str
    xml_file: str | None = None
    product_code: int = 0
    revision_number: int = 0
    group_type: str = "Other"
    has_coe: bool = False


class XmlCache:
    """Manages downloading, extracting, and caching Beckhoff XML files."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize XML cache.

        Args:
            cache_dir: Optional custom cache directory. Defaults to
                        ~/.cache/catio_terminals
        """
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "catio_terminals")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.zip_file = self.cache_dir / "Beckhoff_EtherCAT_XML.zip"
        self.xml_dir = self.cache_dir / "beckhoff_xml"
        self.terminals_file = self.cache_dir / "terminals_cache.json"

        self._client: httpx.Client | None = None
        self._terminals: list[BeckhoffTerminalInfo] | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    )
                },
            )
        return self._client

    def is_xml_available(self) -> bool:
        """Check if XML files are already extracted and available."""
        return self.xml_dir.exists() and any(self.xml_dir.glob("*.xml"))

    def download_and_extract(self) -> bool:
        """Download and extract Beckhoff XML files if not already cached.

        Returns:
            True if files are available, False on error
        """
        if self.is_xml_available():
            logger.debug("XML files already cached")
            return True

        try:
            if not self.zip_file.exists():
                logger.info(f"Downloading Beckhoff XML files from {XML_DOWNLOAD_URL}")
                response = self.client.get(XML_DOWNLOAD_URL)
                response.raise_for_status()

                with self.zip_file.open("wb") as f:
                    f.write(response.content)
                logger.info(f"Downloaded {len(response.content)} bytes")

            logger.info(f"Extracting XML files to {self.xml_dir}")
            self.xml_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(self.zip_file, "r") as zip_ref:
                zip_ref.extractall(self.xml_dir)

            logger.info("XML files extracted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to download/extract XML files: {e}", exc_info=True)
            return False

    def get_xml_files(self) -> list[Path]:
        """Get list of all XML files in the cache.

        Returns:
            List of Path objects for XML files
        """
        if not self.xml_dir.exists():
            return []
        return list(self.xml_dir.rglob("*.xml"))

    def load_terminals(self) -> list[BeckhoffTerminalInfo] | None:
        """Load terminals from cache file.

        Returns:
            List of terminals or None if cache doesn't exist
        """
        if self._terminals is not None:
            return self._terminals

        if not self.terminals_file.exists():
            return None

        try:
            with self.terminals_file.open("r") as f:
                data = json.load(f)

            # Handle both dict format (new) and list format (old)
            if isinstance(data, dict):
                self._terminals = [
                    BeckhoffTerminalInfo(**item) for item in data.values()
                ]
            else:
                self._terminals = [BeckhoffTerminalInfo(**item) for item in data]

            logger.info(f"Loaded {len(self._terminals)} terminals from cache")
            return self._terminals

        except Exception as e:
            logger.error(f"Failed to load terminals cache: {e}")
            return None

    def save_terminals(self, terminals: list[BeckhoffTerminalInfo]) -> None:
        """Save terminals to cache file.

        Args:
            terminals: List of terminals to save
        """
        try:
            # Save as dict keyed by terminal_id for easier lookups
            terminals_dict = {t.terminal_id: asdict(t) for t in terminals}

            with self.terminals_file.open("w") as f:
                json.dump(terminals_dict, f, indent=2)

            self._terminals = terminals
            logger.info(f"Saved {len(terminals)} terminals to cache")

        except Exception as e:
            logger.error(f"Failed to save terminals cache: {e}")

    def clear_terminals_cache(self) -> None:
        """Clear the terminals cache file and in-memory cache."""
        self._terminals = None
        if self.terminals_file.exists():
            self.terminals_file.unlink()
            logger.info("Cleared terminals cache")

    def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
