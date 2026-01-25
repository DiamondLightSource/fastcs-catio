"""Tests for catio_terminals models."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from catio_terminals.models import (
    CompositeType,
    CompositeTypeMember,
    CompositeTypesConfig,
    Identity,
    SymbolNode,
    TerminalConfig,
    TerminalType,
)


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
        type_name="UINT",
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
        type_name="UINT",
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
        type_name="UINT",
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
        type_name="UINT",
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


def test_composite_type_model():
    """Test CompositeType model creation."""
    member = CompositeTypeMember(
        name="Status",
        offset=0,
        type_name="UINT",
        size=2,
        fastcs_attr="Status",
        access="read-only",
    )
    composite = CompositeType(
        description="16-bit analog input channel",
        ads_type=65,
        size=4,
        members=[member],
    )
    assert composite.description == "16-bit analog input channel"
    assert composite.ads_type == 65
    assert composite.size == 4
    assert len(composite.members) == 1
    assert composite.members[0].name == "Status"


def test_composite_types_config_load_default():
    """Test loading default composite types configuration."""
    config = CompositeTypesConfig.get_default()

    # Should have multiple types loaded
    assert len(config.composite_types) > 0

    # Check a known type exists
    assert config.is_composite("AI Standard Channel 1_TYPE")
    assert not config.is_composite("INT")  # Primitive type

    # Get and verify the type
    ai_type = config.get_type("AI Standard Channel 1_TYPE")
    assert ai_type is not None
    assert ai_type.ads_type == 65
    assert ai_type.size == 4
    assert len(ai_type.members) == 2

    # Check members
    member_names = [m.name for m in ai_type.members]
    assert "Status" in member_names
    assert "Value" in member_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
