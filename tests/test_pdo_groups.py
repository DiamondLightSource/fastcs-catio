"""Tests for PDO group parsing and model functionality."""

from lxml import etree

from catio_terminals.models import Identity, PdoGroup, SymbolNode, TerminalType
from catio_terminals.xml_pdo_groups import (
    assign_symbols_to_groups,
    build_pdo_to_group_map,
    parse_pdo_groups,
)


class TestPdoGroupModel:
    """Tests for PdoGroup model."""

    def test_pdo_group_creation(self):
        """Test basic PdoGroup creation."""
        group = PdoGroup(
            name="Standard",
            is_default=True,
            pdo_indices=[0x1A00, 0x1A02],
            symbol_indices=[0, 1],
        )
        assert group.name == "Standard"
        assert group.is_default is True
        assert group.pdo_indices == [0x1A00, 0x1A02]
        assert group.symbol_indices == [0, 1]

    def test_pdo_group_default_values(self):
        """Test PdoGroup default values."""
        group = PdoGroup(name="Test")
        assert group.is_default is False
        assert group.pdo_indices == []
        assert group.symbol_indices == []


class TestTerminalTypeWithPdoGroups:
    """Tests for TerminalType with PDO groups."""

    def test_has_dynamic_pdos_empty(self):
        """Test has_dynamic_pdos with no groups."""
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
        )
        assert terminal.has_dynamic_pdos is False

    def test_has_dynamic_pdos_with_groups(self):
        """Test has_dynamic_pdos with groups."""
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
            pdo_groups=[
                PdoGroup(name="Standard", is_default=True, symbol_indices=[0, 1]),
                PdoGroup(name="Compact", symbol_indices=[2, 3]),
            ],
        )
        assert terminal.has_dynamic_pdos is True

    def test_default_pdo_group(self):
        """Test getting default PDO group."""
        standard = PdoGroup(name="Standard", is_default=True, symbol_indices=[0, 1])
        compact = PdoGroup(name="Compact", symbol_indices=[2, 3])
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
            pdo_groups=[standard, compact],
        )
        assert terminal.default_pdo_group == standard

    def test_get_pdo_group_by_name(self):
        """Test getting PDO group by name."""
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
            pdo_groups=[
                PdoGroup(name="Standard", is_default=True, symbol_indices=[0, 1]),
                PdoGroup(name="Compact", symbol_indices=[2, 3]),
            ],
        )
        assert terminal.get_pdo_group("Compact").name == "Compact"
        assert terminal.get_pdo_group("Unknown") is None

    def test_get_active_symbol_indices_no_groups(self):
        """Test active symbol indices without PDO groups."""
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
            symbol_nodes=[
                SymbolNode(name_template="Sym1", index_group=0xF020, type_name="INT"),
                SymbolNode(name_template="Sym2", index_group=0xF020, type_name="INT"),
            ],
        )
        # All symbols available when no groups
        assert terminal.get_active_symbol_indices() == {0, 1}

    def test_get_active_symbol_indices_with_groups(self):
        """Test active symbol indices with PDO groups."""
        terminal = TerminalType(
            description="Test",
            identity=Identity(vendor_id=2, product_code=0, revision_number=0),
            symbol_nodes=[
                SymbolNode(
                    name_template="Standard1", index_group=0xF020, type_name="INT"
                ),
                SymbolNode(
                    name_template="Standard2", index_group=0xF020, type_name="INT"
                ),
                SymbolNode(
                    name_template="Compact1", index_group=0xF020, type_name="INT"
                ),
                SymbolNode(
                    name_template="Compact2", index_group=0xF020, type_name="INT"
                ),
            ],
            pdo_groups=[
                PdoGroup(name="Standard", is_default=True, symbol_indices=[0, 1]),
                PdoGroup(name="Compact", symbol_indices=[2, 3]),
            ],
            selected_pdo_group="Standard",
        )
        # Only Standard symbols active
        assert terminal.get_active_symbol_indices() == {0, 1}

        # Switch to Compact
        terminal.selected_pdo_group = "Compact"
        assert terminal.get_active_symbol_indices() == {2, 3}


class TestPdoGroupParsing:
    """Tests for PDO group XML parsing."""

    def test_parse_pdo_groups_from_xml(self):
        """Test parsing AlternativeSmMapping from XML."""
        xml_content = """
        <Device>
            <Info>
                <VendorSpecific>
                    <TwinCAT>
                        <AlternativeSmMapping Default="1">
                            <Name>Standard</Name>
                            <Sm No="3">
                                <Pdo>#x1a00</Pdo>
                                <Pdo>#x1a02</Pdo>
                            </Sm>
                        </AlternativeSmMapping>
                        <AlternativeSmMapping>
                            <Name>Compact</Name>
                            <Sm No="3">
                                <Pdo>#x1a01</Pdo>
                                <Pdo>#x1a03</Pdo>
                            </Sm>
                        </AlternativeSmMapping>
                    </TwinCAT>
                </VendorSpecific>
            </Info>
        </Device>
        """
        device = etree.fromstring(xml_content)
        groups = parse_pdo_groups(device)

        assert len(groups) == 2
        assert groups[0].name == "Standard"
        assert groups[0].is_default is True
        assert groups[0].pdo_indices == [0x1A00, 0x1A02]
        assert groups[1].name == "Compact"
        assert groups[1].is_default is False
        assert groups[1].pdo_indices == [0x1A01, 0x1A03]

    def test_parse_pdo_groups_no_vendor_specific(self):
        """Test parsing XML without VendorSpecific section."""
        xml_content = """
        <Device>
            <Type>EL1004</Type>
        </Device>
        """
        device = etree.fromstring(xml_content)
        groups = parse_pdo_groups(device)
        assert groups == []

    def test_build_pdo_to_group_map(self):
        """Test building PDO to group mapping."""
        groups = [
            PdoGroup(name="Standard", pdo_indices=[0x1A00, 0x1A02]),
            PdoGroup(name="Compact", pdo_indices=[0x1A01, 0x1A03]),
        ]
        mapping = build_pdo_to_group_map(groups)
        assert mapping == {
            0x1A00: "Standard",
            0x1A02: "Standard",
            0x1A01: "Compact",
            0x1A03: "Compact",
        }

    def test_assign_symbols_to_groups(self):
        """Test assigning symbols to PDO groups."""
        groups = [
            PdoGroup(name="Standard", pdo_indices=[0x1A00]),
            PdoGroup(name="Compact", pdo_indices=[0x1A01]),
        ]
        symbol_pdo_mapping = {
            0: 0x1A00,  # Symbol 0 from PDO 0x1A00
            1: 0x1A00,  # Symbol 1 from PDO 0x1A00
            2: 0x1A01,  # Symbol 2 from PDO 0x1A01
            3: 0x1A01,  # Symbol 3 from PDO 0x1A01
        }
        assign_symbols_to_groups(groups, symbol_pdo_mapping)

        assert groups[0].symbol_indices == [0, 1]
        assert groups[1].symbol_indices == [2, 3]
