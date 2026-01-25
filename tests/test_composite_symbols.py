"""Tests for the composite_symbols module."""

import pytest

from catio_terminals.composite_symbols import (
    COMPOSITE_MAPPINGS,
    CompositeSymbol,
    CompositeSymbolMapping,
    get_composite_view_data,
    group_symbols_by_composite,
)
from catio_terminals.models import (
    CompositeTypesConfig,
    Identity,
    SymbolNode,
    TerminalType,
)


@pytest.fixture
def composite_types() -> CompositeTypesConfig:
    """Load the composite types configuration."""
    return CompositeTypesConfig.get_default()


@pytest.fixture
def analog_input_terminal() -> TerminalType:
    """Create a sample analog input terminal with primitive symbols."""
    return TerminalType(
        description="4-channel Analog Input +/-10V 12-bit",
        identity=Identity(vendor_id=2, product_code=196882514, revision_number=1048576),
        symbol_nodes=[
            SymbolNode(
                name_template="Underrange {channel}",
                index_group=0xF020,
                type_name="BOOL",
                channels=4,
            ),
            SymbolNode(
                name_template="Overrange {channel}",
                index_group=0xF020,
                type_name="BOOL",
                channels=4,
            ),
            SymbolNode(
                name_template="Error {channel}",
                index_group=0xF020,
                type_name="BOOL",
                channels=4,
            ),
            SymbolNode(
                name_template="Value {channel}",
                index_group=0xF020,
                type_name="INT",
                channels=4,
            ),
            # Add an ungrouped symbol
            SymbolNode(
                name_template="WcState",
                index_group=0xF100,
                type_name="UINT",
                channels=1,
            ),
        ],
        coe_objects=[],
        group_type="AnaIn",
    )


@pytest.fixture
def digital_output_terminal() -> TerminalType:
    """Create a sample digital output terminal."""
    return TerminalType(
        description="4-channel Digital Output 24V DC",
        identity=Identity(vendor_id=2, product_code=131928146, revision_number=1048576),
        symbol_nodes=[
            SymbolNode(
                name_template="Output {channel}",
                index_group=0xF030,
                type_name="BOOL",
                channels=4,
            ),
        ],
        coe_objects=[],
        group_type="DigOut",
    )


class TestCompositeSymbolMapping:
    """Test CompositeSymbolMapping dataclass."""

    def test_mapping_attributes(self) -> None:
        """Test mapping has correct attributes."""
        mapping = CompositeSymbolMapping(
            type_name="Test_TYPE",
            name_template="Test {channel}",
            group_types=["TestGroup"],
            member_patterns={"Member1": ["Pattern1"]},
        )
        assert mapping.type_name == "Test_TYPE"
        assert mapping.name_template == "Test {channel}"
        assert mapping.group_types == ["TestGroup"]
        assert mapping.member_patterns == {"Member1": ["Pattern1"]}


class TestCompositeMappings:
    """Test COMPOSITE_MAPPINGS constant."""

    def test_anain_mapping_exists(self) -> None:
        """Test that AnaIn mapping is defined."""
        anain_mappings = [m for m in COMPOSITE_MAPPINGS if "AnaIn" in m.group_types]
        assert len(anain_mappings) > 0

    def test_digout_mapping_exists(self) -> None:
        """Test that DigOut mapping is defined."""
        digout_mappings = [m for m in COMPOSITE_MAPPINGS if "DigOut" in m.group_types]
        assert len(digout_mappings) > 0


class TestGroupSymbolsByComposite:
    """Test group_symbols_by_composite function."""

    def test_groups_analog_input_symbols(
        self, analog_input_terminal: TerminalType, composite_types: CompositeTypesConfig
    ) -> None:
        """Test that analog input symbols are grouped correctly."""
        grouped = group_symbols_by_composite(analog_input_terminal, composite_types)

        # Should have grouped symbols
        assert len(grouped.composite_symbols) > 0

        # Check the composite symbol
        comp = grouped.composite_symbols[0]
        assert isinstance(comp, CompositeSymbol)
        assert "AI" in comp.name_template
        assert comp.channels == 4  # 4-channel terminal

        # The ungrouped WcState symbol should remain
        assert len(grouped.ungrouped_symbols) == 1
        assert grouped.ungrouped_symbols[0].name_template == "WcState"

    def test_groups_digital_output_symbols(
        self,
        digital_output_terminal: TerminalType,
        composite_types: CompositeTypesConfig,
    ) -> None:
        """Test that digital output symbols are grouped correctly."""
        grouped = group_symbols_by_composite(digital_output_terminal, composite_types)

        # Should have grouped symbols
        assert len(grouped.composite_symbols) > 0

        # Check the composite symbol
        comp = grouped.composite_symbols[0]
        assert "Output" in comp.name_template or "CNT" in comp.name_template

    def test_no_grouping_without_composite_types(
        self, analog_input_terminal: TerminalType
    ) -> None:
        """Test that no grouping occurs without composite_types config."""
        grouped = group_symbols_by_composite(analog_input_terminal, None)

        # All symbols should be ungrouped
        assert len(grouped.composite_symbols) == 0
        assert len(grouped.ungrouped_symbols) == len(analog_input_terminal.symbol_nodes)


class TestGetCompositeViewData:
    """Test get_composite_view_data function."""

    def test_returns_tuple(
        self, analog_input_terminal: TerminalType, composite_types: CompositeTypesConfig
    ) -> None:
        """Test returns tuple of composite and ungrouped lists."""
        composite_list, ungrouped_list = get_composite_view_data(
            analog_input_terminal, composite_types
        )
        assert isinstance(composite_list, list)
        assert isinstance(ungrouped_list, list)

    def test_handles_none_composite_types(
        self, analog_input_terminal: TerminalType
    ) -> None:
        """Test handles None composite_types gracefully."""
        composite_list, ungrouped_list = get_composite_view_data(
            analog_input_terminal, None
        )
        assert len(composite_list) == 0
        assert len(ungrouped_list) == len(analog_input_terminal.symbol_nodes)


class TestCompositeSymbol:
    """Test CompositeSymbol dataclass."""

    def test_composite_symbol_properties(
        self, analog_input_terminal: TerminalType, composite_types: CompositeTypesConfig
    ) -> None:
        """Test CompositeSymbol has expected properties."""
        grouped = group_symbols_by_composite(analog_input_terminal, composite_types)

        if len(grouped.composite_symbols) > 0:
            comp = grouped.composite_symbols[0]
            assert hasattr(comp, "name_template")
            assert hasattr(comp, "type_name")
            assert hasattr(comp, "composite_type")
            assert hasattr(comp, "primitive_symbols")
            assert hasattr(comp, "channels")
            assert hasattr(comp, "index_group")
            assert hasattr(comp, "access")
            assert hasattr(comp, "fastcs_name")
