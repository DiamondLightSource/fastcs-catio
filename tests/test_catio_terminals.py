"""Tests for catio_terminals models."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from catio_terminals.models import Identity, SymbolNode, TerminalConfig, TerminalType


def test_identity_model():
    """Test Identity model creation."""
    identity = Identity(
        vendor_id=2,
        product_code=0x0FA43052,
        revision_number=0x00100000,
    )
    assert identity.vendor_id == 2
    assert identity.product_code == 0x0FA43052
    assert identity.revision_number == 0x00100000


def test_symbol_node_model():
    """Test SymbolNode model creation."""
    symbol = SymbolNode(
        name_template="AO Output Channel {channel}",
        index_group=0xF030,
        size=2,
        ads_type=65,
        type_name="AO Output Channel 1_TYPE",
        channels=4,
    )
    assert symbol.name_template == "AO Output Channel {channel}"
    assert symbol.index_group == 0xF030
    assert symbol.channels == 4


def test_terminal_type_model():
    """Test TerminalType model creation."""
    identity = Identity(
        vendor_id=2,
        product_code=0x0FA43052,
        revision_number=0x00100000,
    )
    symbol = SymbolNode(
        name_template="AO Output Channel {channel}",
        index_group=0xF030,
        size=2,
        ads_type=65,
        type_name="AO Output Channel 1_TYPE",
        channels=4,
    )
    terminal = TerminalType(
        description="4-channel Analog Output 0..10V 12-bit",
        identity=identity,
        symbol_nodes=[symbol],
    )
    assert terminal.description == "4-channel Analog Output 0..10V 12-bit"
    assert len(terminal.symbol_nodes) == 1


def test_terminal_config_add_remove():
    """Test adding and removing terminals from config."""
    config = TerminalConfig()
    identity = Identity(
        vendor_id=2,
        product_code=0x0FA43052,
        revision_number=0x00100000,
    )
    symbol = SymbolNode(
        name_template="AO Output Channel {channel}",
        index_group=0xF030,
        size=2,
        ads_type=65,
        type_name="AO Output Channel 1_TYPE",
        channels=4,
    )
    terminal = TerminalType(
        description="4-channel Analog Output 0..10V 12-bit",
        identity=identity,
        symbol_nodes=[symbol],
    )

    # Add terminal
    config.add_terminal("EL4004", terminal)
    assert "EL4004" in config.terminal_types
    assert config.terminal_types["EL4004"].description == terminal.description

    # Remove terminal
    config.remove_terminal("EL4004")
    assert "EL4004" not in config.terminal_types


def test_terminal_config_yaml_roundtrip():
    """Test saving and loading config from YAML."""
    # Create config
    config = TerminalConfig()
    identity = Identity(
        vendor_id=2,
        product_code=0x0FA43052,
        revision_number=0x00100000,
    )
    symbol = SymbolNode(
        name_template="AO Output Channel {channel}",
        index_group=0xF030,
        size=2,
        ads_type=65,
        type_name="AO Output Channel 1_TYPE",
        channels=4,
    )
    terminal = TerminalType(
        description="4-channel Analog Output 0..10V 12-bit",
        identity=identity,
        symbol_nodes=[symbol],
    )
    config.add_terminal("EL4004", terminal)

    # Save to temp file
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        temp_path = Path(f.name)

    try:
        config.to_yaml(temp_path)

        # Load from temp file
        loaded_config = TerminalConfig.from_yaml(temp_path)

        # Verify
        assert "EL4004" in loaded_config.terminal_types
        loaded_terminal = loaded_config.terminal_types["EL4004"]
        assert loaded_terminal.description == terminal.description
        assert loaded_terminal.identity.vendor_id == identity.vendor_id
        assert len(loaded_terminal.symbol_nodes) == 1
        assert loaded_terminal.symbol_nodes[0].name_template == symbol.name_template
    finally:
        temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
