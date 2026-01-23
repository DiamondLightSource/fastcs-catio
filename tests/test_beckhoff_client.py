"""Tests for Beckhoff XML cache and parsing modules."""

import json
from pathlib import Path

import pytest

from catio_terminals.xml_cache import BeckhoffTerminalInfo, XmlCache
from catio_terminals.xml_parser import (
    generate_terminal_url,
    get_ads_type,
    parse_hex_value,
    parse_terminal_catalog,
)


class TestParseHexValue:
    """Tests for hex value parsing."""

    def test_beckhoff_format(self):
        """Test parsing Beckhoff #x prefix format."""
        assert parse_hex_value("#x1234") == 0x1234
        assert parse_hex_value("#xABCD") == 0xABCD
        assert parse_hex_value("#x00100000") == 0x00100000

    def test_standard_format(self):
        """Test parsing standard 0x prefix format."""
        assert parse_hex_value("0x1234") == 0x1234
        assert parse_hex_value("0xABCD") == 0xABCD

    def test_decimal_format(self):
        """Test parsing decimal format."""
        assert parse_hex_value("1234") == 1234
        assert parse_hex_value("0") == 0


class TestGetAdsType:
    """Tests for ADS type mapping."""

    def test_known_types(self):
        """Test mapping of known data types."""
        assert get_ads_type("BOOL") == 33
        assert get_ads_type("INT") == 2
        assert get_ads_type("REAL") == 4
        assert get_ads_type("LREAL") == 5

    def test_case_insensitive(self):
        """Test that type mapping is case-insensitive."""
        assert get_ads_type("bool") == 33
        assert get_ads_type("Bool") == 33

    def test_unknown_type(self):
        """Test that unknown types return generic structure code."""
        assert get_ads_type("UNKNOWN") == 65
        assert get_ads_type("CustomType") == 65


class TestGenerateTerminalUrl:
    """Tests for URL generation."""

    def test_analog_input(self):
        """Test URL for analog input terminal."""
        url = generate_terminal_url("EL3004", "AnaIn")
        assert "el-ed3xxx-analog-input" in url
        assert "el3004" in url.lower()

    def test_digital_output(self):
        """Test URL for digital output terminal."""
        url = generate_terminal_url("EL2008", "DigOut")
        assert "el-ed2xxx-digital-output" in url
        assert "el2008" in url.lower()

    def test_unknown_group(self):
        """Test URL for unknown group type."""
        url = generate_terminal_url("EL9999", "Unknown")
        assert "ethercat-terminals" in url


class TestXmlCache:
    """Tests for XmlCache class."""

    def test_cache_directory_creation(self, tmp_path: Path):
        """Test that cache directory is created on init."""
        cache_dir = tmp_path / "test_cache"
        cache = XmlCache(cache_dir=cache_dir)

        assert cache_dir.exists()
        assert cache.cache_dir == cache_dir
        cache.close()

    def test_is_xml_available_empty(self, tmp_path: Path):
        """Test is_xml_available returns False when no XML files exist."""
        cache = XmlCache(cache_dir=tmp_path)
        assert cache.is_xml_available() is False
        cache.close()

    def test_is_xml_available_with_files(self, tmp_path: Path):
        """Test is_xml_available returns True when XML files exist."""
        cache = XmlCache(cache_dir=tmp_path)
        cache.xml_dir.mkdir(parents=True, exist_ok=True)
        (cache.xml_dir / "test.xml").write_text("<root/>")

        assert cache.is_xml_available() is True
        cache.close()

    def test_get_xml_files(self, tmp_path: Path):
        """Test getting list of XML files."""
        cache = XmlCache(cache_dir=tmp_path)
        cache.xml_dir.mkdir(parents=True, exist_ok=True)

        # Create some test files
        (cache.xml_dir / "file1.xml").write_text("<root/>")
        (cache.xml_dir / "file2.xml").write_text("<root/>")
        (cache.xml_dir / "not_xml.txt").write_text("text")

        xml_files = cache.get_xml_files()
        assert len(xml_files) == 2
        assert all(f.suffix == ".xml" for f in xml_files)
        cache.close()

    def test_save_and_load_terminals(self, tmp_path: Path):
        """Test saving and loading terminals to/from cache."""
        cache = XmlCache(cache_dir=tmp_path)

        terminals = [
            BeckhoffTerminalInfo(
                terminal_id="EL3004",
                name="EL3004 4Ch. Ana. Input",
                description="4Ch. Ana. Input",
                url="https://example.com/el3004",
                product_code=0x0BBC3052,
                revision_number=0x00100000,
                group_type="AnaIn",
            ),
            BeckhoffTerminalInfo(
                terminal_id="EL2008",
                name="EL2008 8Ch. Dig. Output",
                description="8Ch. Dig. Output",
                url="https://example.com/el2008",
                product_code=0x07D83052,
                group_type="DigOut",
            ),
        ]

        cache.save_terminals(terminals)
        assert cache.terminals_file.exists()

        # Load with a new cache instance
        cache2 = XmlCache(cache_dir=tmp_path)
        loaded = cache2.load_terminals()

        assert loaded is not None
        assert len(loaded) == 2
        assert {t.terminal_id for t in loaded} == {"EL3004", "EL2008"}

        cache.close()
        cache2.close()

    def test_clear_terminals_cache(self, tmp_path: Path):
        """Test clearing the terminals cache."""
        cache = XmlCache(cache_dir=tmp_path)

        # Save some terminals
        terminals = [
            BeckhoffTerminalInfo(
                terminal_id="EL1008",
                name="Test",
                description="Test",
                url="https://example.com",
            )
        ]
        cache.save_terminals(terminals)
        assert cache.terminals_file.exists()

        # Clear cache
        cache.clear_terminals_cache()
        assert not cache.terminals_file.exists()
        assert cache.load_terminals() is None

        cache.close()


class TestBeckhoffTerminalInfo:
    """Tests for BeckhoffTerminalInfo dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        info = BeckhoffTerminalInfo(
            terminal_id="EL1008",
            name="Test Terminal",
            description="Test",
            url="https://example.com",
        )
        assert info.xml_file is None
        assert info.product_code == 0
        assert info.revision_number == 0
        assert info.group_type == "Other"

    def test_all_fields(self):
        """Test all fields can be set."""
        info = BeckhoffTerminalInfo(
            terminal_id="EL3004",
            name="EL3004 4Ch. Ana. Input",
            description="4 channel analog input",
            url="https://example.com/el3004",
            xml_file="/path/to/file.xml",
            product_code=0x0BBC3052,
            revision_number=0x00100000,
            group_type="AnaIn",
        )
        assert info.terminal_id == "EL3004"
        assert info.product_code == 0x0BBC3052


@pytest.mark.asyncio
async def test_xml_cache_download_and_parse():
    """Integration test: download XML files and parse terminals.

    This test actually downloads files from Beckhoff's server.
    It verifies the full workflow of:
    1. Downloading the XML zip file
    2. Extracting XML files
    3. Parsing terminal catalog
    4. Saving to cache
    5. Loading from cache
    """
    cache = XmlCache()

    try:
        # Clear any existing cache to test fresh download
        cache.clear_terminals_cache()

        # Download and extract XML files
        success = cache.download_and_extract()
        assert success, "Failed to download/extract XML files"

        # Get XML files
        xml_files = cache.get_xml_files()
        assert len(xml_files) > 0, f"No XML files found in {cache.xml_dir}"
        print(f"\nFound {len(xml_files)} XML files")

        # Parse terminal catalog with limit
        max_terminals = 10
        progress_messages = []

        def progress_callback(message: str, progress: float):
            progress_messages.append((message, progress))

        terminals = parse_terminal_catalog(
            xml_files,
            max_terminals=max_terminals,
            progress_callback=progress_callback,
        )

        print(f"Parsed {len(terminals)} terminals")
        assert len(terminals) > 0, "No terminals parsed from XML files"
        assert len(terminals) <= max_terminals, (
            f"Expected at most {max_terminals} terminals, got {len(terminals)}"
        )

        # Verify terminal data
        for terminal in terminals[:3]:
            print(f"  - {terminal.terminal_id}: {terminal.name}")
            assert terminal.terminal_id, "Terminal ID should not be empty"
            assert terminal.name, "Terminal name should not be empty"

        # Save to cache
        cache.save_terminals(terminals)
        assert cache.terminals_file.exists(), "Cache file was not created"

        # Verify cache contents
        with cache.terminals_file.open("r") as f:
            cache_data = json.load(f)

        assert isinstance(cache_data, dict), "Cache should be a dictionary"
        assert len(cache_data) == len(terminals), (
            f"Cache has {len(cache_data)} entries, expected {len(terminals)}"
        )

        # Load from cache with new instance
        cache2 = XmlCache()
        loaded = cache2.load_terminals()

        assert loaded is not None, "Failed to load terminals from cache"
        assert len(loaded) == len(terminals), (
            f"Loaded {len(loaded)} terminals, expected {len(terminals)}"
        )

        # Verify IDs match
        original_ids = {t.terminal_id for t in terminals}
        loaded_ids = {t.terminal_id for t in loaded}
        assert original_ids == loaded_ids, "Terminal IDs don't match after reload"

        cache2.close()

    finally:
        cache.close()
