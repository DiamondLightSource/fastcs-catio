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
        compact_group = terminal.get_pdo_group("Compact")
        assert compact_group is not None
        assert compact_group.name == "Compact"
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

    def test_parse_pdo_groups_from_exclude_elements(self):
        """Test parsing PDO groups from Exclude elements (EL1502 pattern).

        The default group is determined by which PDOs have the Sm attribute
        (Sync Manager assignment). In EL1502, the Combined PDOs have Sm,
        so Combined is the default.
        """
        # This simulates EL1502's PDO structure with per-channel vs combined modes
        # Note: Combined PDOs have Sm attribute, making them the default
        xml_content = """
        <Device>
            <Type>EL1502</Type>
            <TxPdo Fixed="1">
                <Index>#x1a00</Index>
                <Name>CNT Inputs Channel 1</Name>
                <Exclude>#x1a02</Exclude>
            </TxPdo>
            <TxPdo Fixed="1">
                <Index>#x1a01</Index>
                <Name>CNT Inputs Channel 2</Name>
                <Exclude>#x1a02</Exclude>
            </TxPdo>
            <TxPdo Fixed="1" Sm="3">
                <Index>#x1a02</Index>
                <Name>CNT Inputs</Name>
                <Exclude>#x1a00</Exclude>
                <Exclude>#x1a01</Exclude>
            </TxPdo>
            <RxPdo Fixed="1">
                <Index>#x1600</Index>
                <Name>CNT Outputs Channel 1</Name>
                <Exclude>#x1602</Exclude>
            </RxPdo>
            <RxPdo Fixed="1">
                <Index>#x1601</Index>
                <Name>CNT Outputs Channel 2</Name>
                <Exclude>#x1602</Exclude>
            </RxPdo>
            <RxPdo Fixed="1" Sm="2">
                <Index>#x1602</Index>
                <Name>CNT Outputs</Name>
                <Exclude>#x1600</Exclude>
                <Exclude>#x1601</Exclude>
            </RxPdo>
        </Device>
        """
        device = etree.fromstring(xml_content)
        groups = parse_pdo_groups(device)

        assert len(groups) == 2

        # Find groups by name
        per_channel = next(g for g in groups if g.name == "Per-Channel")
        combined = next(g for g in groups if g.name == "Combined")

        # Combined should be default (has Sm attribute in XML)
        assert per_channel.is_default is False
        assert combined.is_default is True

        # Check PDO indices
        assert set(per_channel.pdo_indices) == {0x1600, 0x1601, 0x1A00, 0x1A01}
        assert set(combined.pdo_indices) == {0x1602, 0x1A02}


class TestDynamicPdoYamlSerialization:
    """Tests for YAML serialization of dynamic PDO terminals."""

    def test_dynamic_pdo_terminal_saves_all_symbols(self, tmp_path):
        """Test that dynamic PDO terminals save ALL symbols with selected field."""
        from catio_terminals.models import TerminalConfig

        # Create terminal with dynamic PDOs and mixed selection
        terminal = TerminalType(
            description="Test Dynamic",
            identity=Identity(vendor_id=2, product_code=0x1234, revision_number=0),
            pdo_groups=[
                PdoGroup(name="GroupA", is_default=True, symbol_indices=[0, 1]),
                PdoGroup(name="GroupB", symbol_indices=[2, 3]),
            ],
            selected_pdo_group="GroupA",
            symbol_nodes=[
                SymbolNode(
                    name_template="SymA1",
                    index_group=0xF020,
                    type_name="INT",
                    selected=True,
                ),
                SymbolNode(
                    name_template="SymA2",
                    index_group=0xF020,
                    type_name="INT",
                    selected=True,
                ),
                SymbolNode(
                    name_template="SymB1",
                    index_group=0xF020,
                    type_name="INT",
                    selected=False,  # Not selected
                ),
                SymbolNode(
                    name_template="SymB2",
                    index_group=0xF020,
                    type_name="INT",
                    selected=False,  # Not selected
                ),
            ],
        )
        config = TerminalConfig()
        config.add_terminal("TEST_DYNAMIC", terminal)

        # Save to YAML
        yaml_path = tmp_path / "test_dynamic.yaml"
        config.to_yaml(yaml_path)

        # Load and verify ALL symbols are saved (not just selected ones)
        loaded = TerminalConfig.from_yaml(yaml_path)
        loaded_terminal = loaded.terminal_types["TEST_DYNAMIC"]

        # Should have all 4 symbols
        assert len(loaded_terminal.symbol_nodes) == 4

        # Check selected state is preserved
        sym_map = {s.name_template: s for s in loaded_terminal.symbol_nodes}
        assert sym_map["SymA1"].selected is True
        assert sym_map["SymA2"].selected is True
        assert sym_map["SymB1"].selected is False
        assert sym_map["SymB2"].selected is False

    def test_static_terminal_saves_all_symbols_with_selected_field(self, tmp_path):
        """Test that static terminals also save ALL symbols with selected field."""
        from catio_terminals.models import TerminalConfig

        # Create static terminal (no pdo_groups)
        terminal = TerminalType(
            description="Test Static",
            identity=Identity(vendor_id=2, product_code=0x5678, revision_number=0),
            symbol_nodes=[
                SymbolNode(
                    name_template="SelectedSym",
                    index_group=0xF020,
                    type_name="INT",
                    selected=True,
                ),
                SymbolNode(
                    name_template="UnselectedSym",
                    index_group=0xF020,
                    type_name="INT",
                    selected=False,
                ),
            ],
        )
        config = TerminalConfig()
        config.add_terminal("TEST_STATIC", terminal)

        # Save to YAML
        yaml_path = tmp_path / "test_static.yaml"
        config.to_yaml(yaml_path)

        # Load and verify ALL symbols are saved with selected field
        loaded = TerminalConfig.from_yaml(yaml_path)
        loaded_terminal = loaded.terminal_types["TEST_STATIC"]

        # Should have all 2 symbols
        assert len(loaded_terminal.symbol_nodes) == 2

        # Check selected state is preserved
        sym_map = {s.name_template: s for s in loaded_terminal.symbol_nodes}
        assert sym_map["SelectedSym"].selected is True
        assert sym_map["UnselectedSym"].selected is False
