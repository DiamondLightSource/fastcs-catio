"""Tests for the composite_symbols module."""

import pytest

from catio_terminals.composite_symbols import (
    CompositeSymbol,
    convert_primitives_to_composites,
    get_composite_view_data,
    group_symbols_by_composite,
)
from catio_terminals.models import (
    CompositeSymbolMapping,
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
    """Test composite mappings from YAML configuration."""

    def test_anain_mapping_exists(self, composite_types: CompositeTypesConfig) -> None:
        """Test that AnaIn mapping is defined."""
        mappings = composite_types.get_mappings()
        anain_mappings = [m for m in mappings if "AnaIn" in m.group_types]
        assert len(anain_mappings) > 0

    def test_digout_mapping_exists(self, composite_types: CompositeTypesConfig) -> None:
        """Test that DigOut mapping is defined."""
        mappings = composite_types.get_mappings()
        digout_mappings = [m for m in mappings if "DigOut" in m.group_types]
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


class TestConvertPrimitivesToComposites:
    """Test convert_primitives_to_composites function."""

    def test_converts_analog_input_primitives(
        self, analog_input_terminal: TerminalType, composite_types: CompositeTypesConfig
    ) -> None:
        """Test that analog input primitives are converted to composite."""
        result = convert_primitives_to_composites(
            analog_input_terminal, composite_types
        )

        # Should have fewer symbols (primitives grouped into composite)
        assert len(result) < len(analog_input_terminal.symbol_nodes)

        # First symbol should be the composite type
        composite_sym = result[0]
        assert composite_sym.type_name == "AI Standard Channel 1_TYPE"
        assert "AI" in composite_sym.name_template
        assert composite_sym.channels == 4

        # WcState should remain as primitive
        wcstate = [s for s in result if s.name_template == "WcState"]
        assert len(wcstate) == 1
        assert wcstate[0].type_name == "UINT"

    def test_converts_digital_output_primitives(
        self,
        digital_output_terminal: TerminalType,
        composite_types: CompositeTypesConfig,
    ) -> None:
        """Test that digital output primitives are converted to composite."""
        result = convert_primitives_to_composites(
            digital_output_terminal, composite_types
        )

        # Should have converted to composite
        assert len(result) == 1
        composite_sym = result[0]
        assert composite_sym.type_name == "Outputs_TYPE"
        assert composite_sym.channels == 4

    def test_no_conversion_without_composite_types(
        self, analog_input_terminal: TerminalType
    ) -> None:
        """Test that no conversion occurs without composite_types config."""
        result = convert_primitives_to_composites(analog_input_terminal, None)

        # Should return all symbols unchanged
        assert len(result) == len(analog_input_terminal.symbol_nodes)

    def test_preserves_already_composite_symbols(
        self, composite_types: CompositeTypesConfig
    ) -> None:
        """Test that symbols already using composite types are preserved."""
        terminal = TerminalType(
            description="Terminal with composite symbols",
            identity=Identity(vendor_id=2, product_code=123, revision_number=1),
            symbol_nodes=[
                SymbolNode(
                    name_template="AI Standard Channel {channel}",
                    index_group=0xF020,
                    type_name="AI Standard Channel 1_TYPE",  # Already composite
                    channels=4,
                ),
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

        result = convert_primitives_to_composites(terminal, composite_types)

        # Should have 2 symbols - composite should be preserved, not re-grouped
        assert len(result) == 2
        assert result[0].type_name == "AI Standard Channel 1_TYPE"
        assert result[1].type_name == "UINT"
