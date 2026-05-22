"""Tests for XML parser PDO entry processing, especially bit field grouping."""

from catio_terminals.models import SymbolNode
from catio_terminals.xml import list_revisions_for_terminal, parse_terminal_details
from catio_terminals.xml.pdo import _drop_non_leaf_parents

# Sample XML for a terminal with bit fields that should be grouped into Status
COUNTER_TERMINAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor>
    <Id>2</Id>
    <Name>Beckhoff</Name>
  </Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x05de3052" RevisionNo="#x00010000">EL1502</Type>
        <Name LcId="1033">EL1502 2Ch. +/- Counter 24V, 100kHz</Name>
        <GroupType>DigIn</GroupType>
        <TxPdo Fixed="1">
          <Index>#x1a00</Index>
          <Name>CNT Inputs Channel 1</Name>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Output functions enabled</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>2</SubIndex>
            <BitLen>1</BitLen>
            <Name>Status of output</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>3</SubIndex>
            <BitLen>1</BitLen>
            <Name>Set counter done</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>4</SubIndex>
            <BitLen>1</BitLen>
            <Name>Counter inhibited</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>17</SubIndex>
            <BitLen>32</BitLen>
            <Name>Counter value</Name>
            <DataType>UDINT</DataType>
          </Entry>
        </TxPdo>
        <TxPdo Fixed="1">
          <Index>#x1a01</Index>
          <Name>CNT Inputs Channel 2</Name>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Output functions enabled</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>2</SubIndex>
            <BitLen>1</BitLen>
            <Name>Status of output</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>17</SubIndex>
            <BitLen>32</BitLen>
            <Name>Counter value</Name>
            <DataType>UDINT</DataType>
          </Entry>
        </TxPdo>
        <RxPdo Fixed="1">
          <Index>#x1600</Index>
          <Name>CNT Outputs Channel 1</Name>
          <Entry>
            <Index>#x7000</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Enable output functions</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x7000</Index>
            <SubIndex>2</SubIndex>
            <BitLen>1</BitLen>
            <Name>Set output</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x7000</Index>
            <SubIndex>3</SubIndex>
            <BitLen>1</BitLen>
            <Name>Set counter</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x7000</Index>
            <SubIndex>17</SubIndex>
            <BitLen>32</BitLen>
            <Name>Set counter value</Name>
            <DataType>UDINT</DataType>
          </Entry>
        </RxPdo>
        <RxPdo Fixed="1">
          <Index>#x1601</Index>
          <Name>CNT Outputs Channel 2</Name>
          <Entry>
            <Index>#x7010</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Enable output functions</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x7010</Index>
            <SubIndex>2</SubIndex>
            <BitLen>1</BitLen>
            <Name>Set output</Name>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x7010</Index>
            <SubIndex>17</SubIndex>
            <BitLen>32</BitLen>
            <Name>Set counter value</Name>
            <DataType>UDINT</DataType>
          </Entry>
        </RxPdo>
        <Profile>
          <Dictionary>
            <DataTypes></DataTypes>
            <Objects></Objects>
          </Dictionary>
        </Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""


class TestBitFieldGrouping:
    """Tests for grouping bit fields into composite symbols using PDO name."""

    def test_bit_fields_grouped_into_pdo_name(self):
        """Verify TxPdo bit fields are coalesced and the bare-struct parent
        is dropped (its child `.Counter value` makes it a non-leaf)."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Bare-struct parent is filtered out — it's a non-leaf prefix of
        # `.Counter value` and would only produce an orphan PV.
        assert "CNT Inputs Channel {channel}" not in symbol_names

        # Individual bit entries are still coalesced (not emitted separately).
        assert (
            "CNT Inputs Channel {channel}.Output functions enabled" not in symbol_names
        )
        assert "CNT Inputs Channel {channel}.Status of output" not in symbol_names

        # The byte-aligned leaf survives.
        assert "CNT Inputs Channel {channel}.Counter value" in symbol_names

        # The bit-field composite type is still emitted for reference.
        assert "Output functions enabled_4Bits" in composite_types

    def test_bit_fields_grouped_into_pdo_name_rxpdo(self):
        """Verify RxPdo bit fields are coalesced and the bare-struct parent
        is dropped (its child `.Set counter value` makes it a non-leaf)."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Bare-struct parent is filtered out.
        assert "CNT Outputs Channel {channel}" not in symbol_names

        # Individual bit entries are still coalesced (not emitted separately).
        assert (
            "CNT Outputs Channel {channel}.Enable output functions" not in symbol_names
        )
        assert "CNT Outputs Channel {channel}.Set output" not in symbol_names

        # The byte-aligned leaf survives.
        assert "CNT Outputs Channel {channel}.Set counter value" in symbol_names

        # The bit-field composite type is still emitted for reference.
        assert "Enable output functions_3Bits" in composite_types

    def test_txpdo_composite_type_emitted(self):
        """Bit-field composite types are still emitted even when the parent
        symbol is filtered out as a non-leaf."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None
        # First bit field is "Output functions enabled", 4 bits total.
        assert "Output functions enabled_4Bits" in composite_types

    def test_rxpdo_composite_type_emitted(self):
        """RxPdo bit-field composite type is still emitted."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None
        # First bit field is "Enable output functions", 3 bits total.
        assert "Enable output functions_3Bits" in composite_types

    def test_channel_count_preserved(self):
        """Verify channel count is correctly detected on the surviving leaf."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        # The `.Counter value` leaf is the survivor; check it carries the
        # channel count that was on the (now-dropped) bare-struct parent.
        counter_symbols = [
            s
            for s in terminal.symbol_nodes
            if s.name_template == "CNT Inputs Channel {channel}.Counter value"
        ]
        assert len(counter_symbols) == 1
        assert counter_symbols[0].channels == 2

    def test_access_modes_correct(self):
        """Verify TxPdo symbols are read-only and RxPdo symbols are read/write."""
        result = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        for symbol in terminal.symbol_nodes:
            if "CNT Inputs" in symbol.name_template:
                assert symbol.access == "Read-only"
            elif "CNT Outputs" in symbol.name_template:
                assert symbol.access == "Read/Write"


# Sample XML for a terminal with only bit fields (no value entries)
DIGITAL_INPUT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor>
    <Id>2</Id>
    <Name>Beckhoff</Name>
  </Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x03ec3052" RevisionNo="#x00100000">EL1004</Type>
        <Name LcId="1033">EL1004 4-channel Digital Input 24V</Name>
        <GroupType>DigIn</GroupType>
        <TxPdo Fixed="1" Sm="0">
          <Index>#x1a00</Index>
          <Name>Channel 1</Name>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Input</Name>
            <DataType>BOOL</DataType>
          </Entry>
        </TxPdo>
        <TxPdo Fixed="1" Sm="0">
          <Index>#x1a01</Index>
          <Name>Channel 2</Name>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Input</Name>
            <DataType>BOOL</DataType>
          </Entry>
        </TxPdo>
        <Profile>
          <Dictionary>
            <DataTypes></DataTypes>
            <Objects></Objects>
          </Dictionary>
        </Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""


class TestSingleBitPdo:
    """Tests for PDOs that contain only a single bit entry."""

    def test_single_bit_pdo_uses_pdo_name(self):
        """Single bit PDO should use the PDO name directly."""
        result = parse_terminal_details(DIGITAL_INPUT_XML, "EL1004", "DigIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should use the PDO name directly (e.g., "Channel {channel}")
        assert "Channel {channel}" in symbol_names

        # Should NOT have .Status or .Input suffixes
        assert "Channel {channel}.Status" not in symbol_names
        assert "Channel {channel}.Input" not in symbol_names


# Sample XML for testing array entry consolidation
ARRAY_TERMINAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor>
    <Id>2</Id>
    <Name>Beckhoff</Name>
  </Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0e74e052" RevisionNo="#x00010000">ELM3704</Type>
        <Name LcId="1033">ELM3704 4Ch. Multi-function Input</Name>
        <GroupType>AnaIn</GroupType>
        <TxPdo Fixed="1">
          <Index>#x1a80</Index>
          <Name>PAI Samples 5 Channel 1</Name>
          <Entry>
            <Index>#x6080</Index>
            <SubIndex>1</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [0]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6080</Index>
            <SubIndex>2</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [1]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6080</Index>
            <SubIndex>3</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [2]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6080</Index>
            <SubIndex>4</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [3]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6080</Index>
            <SubIndex>5</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [4]</Name>
            <DataType>DINT</DataType>
          </Entry>
        </TxPdo>
        <TxPdo Fixed="1">
          <Index>#x1a90</Index>
          <Name>PAI Samples 5 Channel 2</Name>
          <Entry>
            <Index>#x6090</Index>
            <SubIndex>1</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [0]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6090</Index>
            <SubIndex>2</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [1]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6090</Index>
            <SubIndex>3</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [2]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6090</Index>
            <SubIndex>4</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [3]</Name>
            <DataType>DINT</DataType>
          </Entry>
          <Entry>
            <Index>#x6090</Index>
            <SubIndex>5</SubIndex>
            <BitLen>32</BitLen>
            <Name>Samples__ARRAY [4]</Name>
            <DataType>DINT</DataType>
          </Entry>
        </TxPdo>
        <Profile>
          <Dictionary>
            <DataTypes></DataTypes>
            <Objects></Objects>
          </Dictionary>
        </Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""


class TestArrayConsolidation:
    """Tests for array entry consolidation."""

    def test_array_entries_consolidated(self):
        """Array element entries should be consolidated into a single symbol."""
        result = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should have a single consolidated Samples array symbol with channel
        assert "PAI Samples 5 Channel {channel}.Samples" in symbol_names

        # Should NOT have individual array element entries
        assert "PAI Samples 5 Channel {channel}.Samples__ARRAY [0]" not in symbol_names
        assert "Samples__ARRAY [0]" not in symbol_names

    def test_array_type_is_correct(self):
        """Consolidated array should have correct type name."""
        result = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        # Find the Samples symbol
        samples_symbol = next(
            (s for s in terminal.symbol_nodes if "Samples" in s.name_template),
            None,
        )
        assert samples_symbol is not None

        # Type should be ARRAY [0..4] OF DINT (5 elements, indices 0-4)
        assert samples_symbol.type_name == "ARRAY [0..4] OF DINT"

    def test_array_channel_count_preserved(self):
        """Array consolidation should preserve channel templating."""
        result = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        samples_symbol = next(
            (s for s in terminal.symbol_nodes if "Samples" in s.name_template),
            None,
        )
        assert samples_symbol is not None

        # Should have 2 channels
        assert samples_symbol.channels == 2

    def test_symbol_count_reduced(self):
        """Array consolidation should reduce symbol count significantly."""
        result = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        # Without consolidation: 10 entries (5 per channel x 2 channels)
        # With consolidation: 1 symbol (templated for 2 channels)
        assert len(terminal.symbol_nodes) == 1


# Sample XML for testing tooltip/comment extraction
TOOLTIP_TERMINAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor>
    <Id>2</Id>
    <Name>Beckhoff</Name>
  </Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104 4Ch. Ana. Input +/-10V</Name>
        <GroupType>AnaIn</GroupType>
        <TxPdo Fixed="1">
          <Index>#x1a00</Index>
          <Name>AI Standard Channel 1</Name>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Status__Underrange</Name>
            <Comment>Bit set when upper value limit exceeded</Comment>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>2</SubIndex>
            <BitLen>1</BitLen>
            <Name>Status__Overrange</Name>
            <Comment>Bit set when lower value limit exceeded</Comment>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>17</SubIndex>
            <BitLen>16</BitLen>
            <Name>Value</Name>
            <Comment>The analog input value in raw ADC counts</Comment>
            <DataType>INT</DataType>
          </Entry>
        </TxPdo>
        <TxPdo Fixed="1">
          <Index>#x1a02</Index>
          <Name>AI Standard Channel 2</Name>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>1</SubIndex>
            <BitLen>1</BitLen>
            <Name>Status__Underrange</Name>
            <Comment>Bit set when upper value limit exceeded</Comment>
            <DataType>BOOL</DataType>
          </Entry>
          <Entry>
            <Index>#x6010</Index>
            <SubIndex>17</SubIndex>
            <BitLen>16</BitLen>
            <Name>Value</Name>
            <Comment>The analog input value in raw ADC counts</Comment>
            <DataType>INT</DataType>
          </Entry>
        </TxPdo>
        <Profile>
          <Dictionary>
            <DataTypes></DataTypes>
            <Objects></Objects>
          </Dictionary>
        </Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""


class TestTooltipExtraction:
    """Tests for extracting Comment elements as tooltips."""

    def test_value_entry_has_tooltip(self):
        """Verify that Comment elements are extracted as tooltips for value entries."""
        result = parse_terminal_details(TOOLTIP_TERMINAL_XML, "EL3104", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        # Find the Value symbol
        value_symbol = next(
            (s for s in terminal.symbol_nodes if "Value" in s.name_template),
            None,
        )
        assert value_symbol is not None, "Value symbol should exist"

        # Should have tooltip extracted from Comment
        assert value_symbol.tooltip == "The analog input value in raw ADC counts"

    def test_tooltip_preserves_across_channels(self):
        """Verify tooltips are preserved when symbols are grouped by channel."""
        result = parse_terminal_details(TOOLTIP_TERMINAL_XML, "EL3104", "AnaIn")
        terminal, composite_types = result if result else (None, {})

        assert terminal is not None

        # Find the Value symbol (should be templated for both channels)
        value_symbol = next(
            (s for s in terminal.symbol_nodes if "Value" in s.name_template),
            None,
        )
        assert value_symbol is not None

        # Should have 2 channels
        assert value_symbol.channels == 2

        # Tooltip should be present
        assert value_symbol.tooltip is not None

    def test_entry_without_comment_has_no_tooltip(self):
        """Verify entries without Comment elements have None for tooltip."""
        # Create XML without comments
        xml_no_comments = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor><Id>2</Id></Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104 Test</Name>
        <GroupType>AnaIn</GroupType>
        <TxPdo Fixed="1">
          <Index>#x1a00</Index>
          <Name>AI Channel 1</Name>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>17</SubIndex>
            <BitLen>16</BitLen>
            <Name>Value</Name>
            <DataType>INT</DataType>
          </Entry>
        </TxPdo>
        <Profile><Dictionary><DataTypes></DataTypes><Objects></Objects></Dictionary></Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""
        result = parse_terminal_details(xml_no_comments, "EL3104", "AnaIn")
        terminal, _ = result if result else (None, {})

        assert terminal is not None

        value_symbol = next(
            (s for s in terminal.symbol_nodes if "Value" in s.name_template),
            None,
        )
        assert value_symbol is not None
        assert value_symbol.tooltip is None

    def test_multiline_comment_normalized(self):
        """Verify multi-line comments are normalized to single line."""
        xml_multiline = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor><Id>2</Id></Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104 Test</Name>
        <GroupType>AnaIn</GroupType>
        <TxPdo Fixed="1">
          <Index>#x1a00</Index>
          <Name>AI Channel 1</Name>
          <Entry>
            <Index>#x6000</Index>
            <SubIndex>17</SubIndex>
            <BitLen>16</BitLen>
            <Name>Value</Name>
            <Comment>Bit0: Value greater than Limit1
Bit1: Value smaller than Limit1</Comment>
            <DataType>INT</DataType>
          </Entry>
        </TxPdo>
        <Profile><Dictionary><DataTypes></DataTypes><Objects></Objects></Dictionary></Profile>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""
        result = parse_terminal_details(xml_multiline, "EL3104", "AnaIn")
        terminal, _ = result if result else (None, {})

        assert terminal is not None

        value_symbol = next(
            (s for s in terminal.symbol_nodes if "Value" in s.name_template),
            None,
        )
        assert value_symbol is not None

        # Multi-line should be normalized to single line with space
        assert (
            value_symbol.tooltip
            == "Bit0: Value greater than Limit1 Bit1: Value smaller than Limit1"
        )


class TestListRevisions:
    """Tests for list_revisions_for_terminal."""

    _MULTI_REVISION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor><Id>2</Id><Name>Beckhoff</Name></Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x11142852" RevisionNo="#x00100002">EP4374-0002</Type>
        <Name LcId="1033">EP4374-0002 old</Name>
      </Device>
      <Device>
        <Type ProductCode="#x11142852" RevisionNo="#x00110002">EP4374-0002</Type>
        <Name LcId="1033">EP4374-0002 mid</Name>
      </Device>
      <Device>
        <Type ProductCode="#x11142852" RevisionNo="#x00120002">EP4374-0002</Type>
        <Name LcId="1033">EP4374-0002 newest</Name>
      </Device>
      <Device>
        <Type ProductCode="#xDEADBEEF" RevisionNo="#x00990099">OTHER-0000</Type>
        <Name LcId="1033">unrelated</Name>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""

    def test_returns_sorted_unique_revisions(self):
        revisions = list_revisions_for_terminal(self._MULTI_REVISION_XML, "EP4374-0002")

        assert revisions == [0x00100002, 0x00110002, 0x00120002]

    def test_ignores_other_terminals(self):
        # Even though OTHER-0000 has a revision, it shouldn't appear in
        # EP4374-0002's list.
        revisions = list_revisions_for_terminal(self._MULTI_REVISION_XML, "EP4374-0002")

        assert 0x00990099 not in revisions

    def test_missing_terminal_returns_empty(self):
        assert list_revisions_for_terminal(self._MULTI_REVISION_XML, "EL9999") == []

    def test_single_revision_xml(self):
        single = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor><Id>2</Id><Name>Beckhoff</Name></Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104</Name>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""
        assert list_revisions_for_terminal(single, "EL3104") == [0x00100000]

    def test_malformed_xml_returns_empty(self):
        assert list_revisions_for_terminal("not<xml", "EL3104") == []

    def test_deduplicates_repeated_revisions(self):
        repeated = """<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor><Id>2</Id><Name>Beckhoff</Name></Vendor>
  <Descriptions>
    <Devices>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104 first</Name>
      </Device>
      <Device>
        <Type ProductCode="#x0c203052" RevisionNo="#x00100000">EL3104</Type>
        <Name LcId="1033">EL3104 duplicate</Name>
      </Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
"""
        assert list_revisions_for_terminal(repeated, "EL3104") == [0x00100000]


class TestDropNonLeafParents:
    """Direct tests for `_drop_non_leaf_parents`."""

    def _node(self, name: str) -> SymbolNode:
        return SymbolNode(
            name_template=name,
            index_group=0x6000,
            type_name="INT",
        )

    def test_parent_with_child_dropped(self):
        nodes = [
            self._node("TC Inputs Channel {channel}"),
            self._node("TC Inputs Channel {channel}.Value"),
        ]
        kept, _ = _drop_non_leaf_parents(nodes, {})
        names = [n.name_template for n in kept]
        assert names == ["TC Inputs Channel {channel}.Value"]

    def test_standalone_leaf_kept(self):
        # No siblings prefixed by this name → it's a leaf.
        nodes = [self._node("Standalone Leaf")]
        kept, _ = _drop_non_leaf_parents(nodes, {})
        assert [n.name_template for n in kept] == ["Standalone Leaf"]

    def test_sub_byte_siblings_dont_save_the_parent(self):
        # EL3314 shape: parent + .Value + sub-byte bit children. Parent still
        # gets dropped because any child template that starts with `<parent>.`
        # makes the parent non-leaf, regardless of byte alignment.
        nodes = [
            self._node("TC Inputs Channel {channel}"),
            self._node("TC Inputs Channel {channel}.Value"),
            self._node("TC Inputs Channel {channel}.Status__Limit 1"),
            self._node("TC Inputs Channel {channel}.Status__Limit 2"),
        ]
        kept, _ = _drop_non_leaf_parents(nodes, {})
        names = [n.name_template for n in kept]
        assert "TC Inputs Channel {channel}" not in names
        assert "TC Inputs Channel {channel}.Value" in names
        # Sub-byte rows survive the generator filter (they're still leaves);
        # the bus-side expander gates them out separately.
        assert "TC Inputs Channel {channel}.Status__Limit 1" in names

    def test_pdo_indices_remapped(self):
        # Parent at old index 0, child at old index 1 with pdo 7.
        # After dropping the parent the child shifts to new index 0.
        nodes = [
            self._node("Parent"),
            self._node("Parent.Child"),
        ]
        kept, remapped = _drop_non_leaf_parents(nodes, {0: 5, 1: 7})
        assert [n.name_template for n in kept] == ["Parent.Child"]
        # Old index 0 (the parent) is gone. Old index 1 → new index 0.
        assert remapped == {0: 7}

    def test_dotted_prefix_must_be_followed_by_dot(self):
        # "Foo Bar" is not a prefix of "Foo Bar Baz" — the trailing `.` is
        # what distinguishes a struct parent from an unrelated row that just
        # happens to share an opening substring.
        nodes = [
            self._node("Foo Bar"),
            self._node("Foo Bar Baz"),
        ]
        kept, _ = _drop_non_leaf_parents(nodes, {})
        names = [n.name_template for n in kept]
        assert "Foo Bar" in names
        assert "Foo Bar Baz" in names
