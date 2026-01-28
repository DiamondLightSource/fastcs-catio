"""Tests for XML parser PDO entry processing, especially bit field grouping."""

from catio_terminals.xml_parser import parse_terminal_details

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
    """Tests for grouping bit fields into composite Status/Control symbols."""

    def test_bit_fields_grouped_into_status(self):
        """Verify bit fields from TxPdo are grouped into a Status symbol."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        # Get symbol names
        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should have Status composite instead of individual bits
        assert "CNT Inputs Channel {channel}.Status" in symbol_names

        # Should NOT have individual bit entries
        assert (
            "CNT Inputs Channel {channel}.Output functions enabled" not in symbol_names
        )
        assert "CNT Inputs Channel {channel}.Status of output" not in symbol_names

        # Should still have the Counter value entry
        assert "CNT Inputs Channel {channel}.Counter value" in symbol_names

    def test_bit_fields_grouped_into_control(self):
        """Verify bit fields from RxPdo are grouped into a Control symbol."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should have Control composite instead of individual bits
        assert "CNT Outputs Channel {channel}.Control" in symbol_names

        # Should NOT have individual bit entries
        assert (
            "CNT Outputs Channel {channel}.Enable output functions" not in symbol_names
        )
        assert "CNT Outputs Channel {channel}.Set output" not in symbol_names

        # Should still have the Set counter value entry
        assert "CNT Outputs Channel {channel}.Set counter value" in symbol_names

    def test_status_symbol_type_is_composite(self):
        """Verify Status symbol has appropriate composite type (USINT/UINT)."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        # Find Status symbol
        status_symbols = [
            s for s in terminal.symbol_nodes if "Status" in s.name_template
        ]

        assert len(status_symbols) == 1
        status = status_symbols[0]

        # 4 bits should fit in USINT (8 bits)
        assert status.type_name == "USINT"

    def test_control_symbol_type_is_composite(self):
        """Verify Control symbol has appropriate composite type."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        # Find Control symbol
        control_symbols = [
            s for s in terminal.symbol_nodes if "Control" in s.name_template
        ]

        assert len(control_symbols) == 1
        control = control_symbols[0]

        # Control bits should fit in USINT
        assert control.type_name == "USINT"

    def test_channel_count_preserved(self):
        """Verify channel count is correctly detected for grouped symbols."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        # Find Status symbol (should have 2 channels)
        status_symbols = [
            s for s in terminal.symbol_nodes if "Status" in s.name_template
        ]

        assert len(status_symbols) == 1
        assert status_symbols[0].channels == 2

    def test_access_modes_correct(self):
        """Verify Status is read-only and Control is read/write."""
        terminal = parse_terminal_details(COUNTER_TERMINAL_XML, "EL1502", "DigIn")

        assert terminal is not None

        for symbol in terminal.symbol_nodes:
            if "Status" in symbol.name_template:
                assert symbol.access == "Read-only"
            elif "Control" in symbol.name_template:
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

    def test_single_bit_pdo_creates_status(self):
        """Single bit PDO should create a Status symbol."""
        terminal = parse_terminal_details(DIGITAL_INPUT_XML, "EL1004", "DigIn")

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should have Status composite (since the only entry is a bit)
        assert "Channel {channel}.Status" in symbol_names

        # Should NOT have individual Input entries
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
        terminal = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")

        assert terminal is not None

        symbol_names = [s.name_template for s in terminal.symbol_nodes]

        # Should have a single consolidated Samples array symbol with channel
        assert "PAI Samples 5 Channel {channel}.Samples" in symbol_names

        # Should NOT have individual array element entries
        assert "PAI Samples 5 Channel {channel}.Samples__ARRAY [0]" not in symbol_names
        assert "Samples__ARRAY [0]" not in symbol_names

    def test_array_type_is_correct(self):
        """Consolidated array should have correct type name."""
        terminal = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")

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
        terminal = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")

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
        terminal = parse_terminal_details(ARRAY_TERMINAL_XML, "ELM3704", "AnaIn")

        assert terminal is not None

        # Without consolidation: 10 entries (5 per channel x 2 channels)
        # With consolidation: 1 symbol (templated for 2 channels)
        assert len(terminal.symbol_nodes) == 1
