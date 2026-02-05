# How to Get All PDOs in an EtherCAT Chain

This guide provides practical instructions for discovering the actual PDO (Process Data Object) configuration of terminals at runtime.

**Background:** Some EtherCAT terminals have dynamic PDO configurations that depend on TwinCAT project settings. For conceptual background on dynamic PDOs, XML structure, and how `catio-terminals` handles them, see [Dynamic PDOs in EtherCAT Terminals](../explanations/dynamic-pdos.md).

## Current Status with catio-terminals

The YAML definitions include all dynamic PDOs grouped by mode. The `catio-terminals` editor allows you to select which mode you're using, filtering the PDOs accordingly.

**Implications:**
- Changing the mode in TwinCAT requires updating the mode in the YAML file and restarting the IOC
- All terminals of a given type must be in the same mode (per-terminal mode selection is a planned improvement)

For more details on the implementation, see [Dynamic PDOs - Implementation in catio-terminals](../explanations/dynamic-pdos.md#implementation-in-catio-terminals).

## Quick Reference: Terminals at Diamond Light Source

The terminals listed here are the complete set used at DLS at the time of writing (see [DLS Terminals Reference](../reference/DLS_terminals.md) for details).

For conceptual explanation of each dynamic PDO type, see [Dynamic PDOs - Types of Dynamic PDO Configurations](../explanations/dynamic-pdos.md#types-of-dynamic-pdo-configurations).

| Terminal | Description | PDO Type |
|----------|-------------|----------|
| EK1100 | EtherCAT Coupler | None |
| EK1122 | 2 Port EtherCAT Junction | None |
| EL1014 | 4Ch Digital Input 24V, 10us | Static |
| EL1084 | 4Ch Digital Input 24V, 3ms, negative | Static |
| EL1124 | 4Ch Digital Input 5V, 10us | Static |
| EL1502 | 2Ch Up/Down Counter 24V, 100kHz | **Dynamic Type 1** |
| EL2024 | 4Ch Digital Output 24V, 2A | Static |
| EL2024-0010 | 4Ch Digital Output 24V, 2A (variant) | Static |
| EL2124 | 4Ch Digital Output 5V, 20mA | Static |
| EL2502 | 2Ch PWM Output 24V | Static |
| EL2595 | 1Ch LED Constant Current | Static |
| EL2612 | 2Ch Relay Output CO | Static |
| EL2624 | 4Ch Relay Output NO | Static |
| EL3104 | 4Ch Analog Input +/-10V Diff | **Dynamic Type 2** |
| EL3124 | 4Ch Analog Input 4-20mA Diff | **Dynamic Type 2** |
| EL3202 | 2Ch Analog Input PT100 (RTD) | Static |
| EL3202-0010 | 2Ch Analog Input PT100 (RTD, variant) | Static |
| EL3314 | 4Ch Analog Input Thermocouple | Static |
| EL3356-0010 | 1Ch Resistor Bridge, 16bit High Precision | **Dynamic Type 3** |
| EL3602 | 2Ch Analog Input +/-10V Diff, 24bit | Static |
| EL3702 | 2Ch Analog Input +/-10V Oversample | **Dynamic Type 4** |
| EL4134 | 4Ch Analog Output +/-10V, 16bit | Static |
| EL4732 | 2Ch Analog Output +/-10V Oversample | **Dynamic Type 4** |
| EL9410 | E-Bus Power Supply (Diagnostics) | Static |
| EL9505 | Power Supply Terminal 5V | Static |
| EL9510 | Power Supply Terminal 10V | Static |
| EL9512 | Power Supply Terminal 12V | Static |
| ELM3704-0000 | 4Ch Universal Analog Input, 24bit | **Dynamic Type 4** |
| EP2338-0002 | 8Ch Digital I/O 24V, 0.5A | Static |
| EP2624-0002 | 4Ch Relay Output NO | Static |
| EP3174-0002 | 4Ch Analog Input configurable | **Dynamic Type 2** |
| EP3204-0002 | 4Ch Analog Input PT100 (RTD) | Static |
| EP3314-0002 | 4Ch Analog Input Thermocouple | Static |
| EP4174-0002 | 4Ch Analog Output configurable | Static |
| EP4374-0002 | 2Ch AI + 2Ch AO configurable | **Dynamic Type 2** |

## Runtime Discovery Examples

This section provides practical code examples for discovering PDO configurations at runtime for each type of dynamic terminal.

### Type 1: Configuration Variants (EL1502)

Detect whether per-channel or combined PDO configuration is active:
```python
# Query actual symbols for an EL1502
symbols = await client.get_all_symbols()
el1502_symbols = [symbol for name, symbol in symbols[device_id].items() if "EL1502" in name]

# Check which configuration is active
has_per_channel = any("Channel 1" in s.name for s in el1502_symbols)
has_combined = any("CNT Inputs.Counter value" in s.name for s in el1502_symbols)
```

### Type 2: Standard/Compact PDO Selection (EL3104, EL3124, EP3174-0002, EP4374-0002)

Detect whether Standard or Compact PDO format is active:
```python
# Query actual symbols for analog input terminals
symbols = await client.get_all_symbols()
ai_symbols = [s for name, symbol in symbols[device_id].items() if "AI" in name]

# Determine which format is active
has_standard = any("Standard" in s.name for s in ai_symbols)
has_compact = any("Compact" in s.name for s in ai_symbols)

if has_standard:
    print("Using Standard PDO format (status + value)")
elif has_compact:
    print("Using Compact PDO format (value only)")
```

### Type 3: Multi-Format Terminals (EL3356-0010)

Detect which data format and optional features are active:
```python
# Query actual symbols for EL3356
symbols = await client.get_all_symbols()
el3356_symbols = [s for name, symbol in symbols[device_id].items() if "EL3356" in name]

# Determine which value format is active
has_int32 = any("RMB Value (INT32)" in s.name for s in el3356_symbols)
has_real = any("RMB Value (Real)" in s.name for s in el3356_symbols)
has_standard = any("AI Standard" in s.name for s in el3356_symbols)
has_compact = any("AI Compact" in s.name for s in el3356_symbols)

# Check for optional features
has_timestamp = any("Timestamp" in s.name for s in el3356_symbols)
has_control = any("RMB Control" in s.name for s in el3356_symbols)
```

### Type 4: Oversampling Terminals (EL3702, EL4732, ELM3704-0000)

#### EL3702 - 2Ch Oversampling Analog Input

Detect the configured oversampling factor:**
```python
# Query actual symbols for an EL3702
symbols = await client.get_all_symbols()
el3702_ch1 = [s for name, symbol in symbols[device_id].items()
              if "EL3702" in name and "Ch1" in name and "Value" in name]

oversampling_factor = len(el3702_ch1)
print(f"EL3702 configured for {oversampling_factor}x oversampling")
```

#### EL4732 - 2Ch Oversampling Analog Output

**Problem:** Similar to EL3702, the sample count is configurable. The output PDO contains arrays of values.

**Runtime Discovery:**
```python
# Query actual symbols for an EL4732
symbols = await client.get_all_symbols()
el4732_symbols = [s for name, symbol in symbols[device_id].items() if "EL4732" in name and "Value" in name]

# Count array elements to determine oversampling factor
sample_count = len(el4732_symbols)
print(f"EL4732 configured for {sample_count} samples per cycle")
```

#### ELM3704-0000 - 4Ch Universal Analog Input with Oversampling

**Problem:** This is the most complex terminal. Each of the 4 channels can be independently configured with:

1. **Data format**: INT16, INT32 (DINT), or REAL32
2. **Oversampling factor**: 1, 2, 4, 5, 8, 10, 16, 20, 25, 32, 40, 50, 64, 80, or 100 samples
3. **Optional PDOs**: Status, Timestamp, Control, Cold Junction Temperature

The XML defines 192 TxPDOs (48 per channel) covering all combinations!

| PDO Pattern | Example | Description |
|-------------|---------|-------------|
| `PAI Status Channel {n}` | `PAI Status Channel 1` | Status byte per channel |
| `PAI Samples {count} Channel {n}` | `PAI Samples 10 Channel 1` | DINT array with count samples |
| `PAI Samples16 {count} Channel {n}` | `PAI Samples16 10 Channel 1` | INT array with count samples |
| `PAI SamplesR32 {count} Channel {n}` | `PAI SamplesR32 10 Channel 1` | REAL array with count samples |
| `PAI Timestamp Channel {n}` | `PAI Timestamp Channel 1` | 64-bit timestamp |

**Runtime Discovery:**
```python
# Query actual symbols for ELM3704
symbols = await client.get_all_symbols()
elm3704_symbols = [s for name, symbol in symbols[device_id].items() if "ELM3704" in name]

for ch in range(1, 5):
    ch_symbols = [s for s in elm3704_symbols if f"Channel {ch}" in s.name]

    # Determine data format
    if any("SamplesR32" in s.name for s in ch_symbols):
        data_format = "REAL32"
    elif any("Samples16" in s.name for s in ch_symbols):
        data_format = "INT16"
    elif any("Samples " in s.name for s in ch_symbols):  # Note space to avoid Samples16
        data_format = "INT32"
    else:
        data_format = "Unknown"

    # Determine oversampling factor from PDO name
    import re
    for s in ch_symbols:
        match = re.search(r'Samples\d* (\d+) Channel', s.name)
        if match:
            oversample = int(match.group(1))
            break
    else:
        oversample = 1

    print(f"Channel {ch}: {data_format} format, {oversample}x oversampling")
```

## How to Query All PDOs at Runtime

### Step 1: Get Symbol Table Info

```python
from fastcs_catio.client import CatioClient
from fastcs_catio._constants import IndexGroup

# Request symbol table metadata
response = await client._ads_command(
    AdsReadRequest(
        index_group=IndexGroup.ADSIGRP_SYM_UPLOADINFO2,  # 0xF00F
        index_offset=0,
        read_length=24,
    )
)
symbol_count = ...  # Parse from response
table_length = ...  # Parse from response
```

### Step 2: Download Full Symbol Table

```python
# Fetch all symbol definitions
response = await client._ads_command(
    AdsReadRequest(
        index_group=IndexGroup.ADSIGRP_SYM_UPLOAD,  # 0xF00B
        index_offset=0,
        read_length=table_length,
    )
)
# Parse symbol entries from response.data
```

### Step 3: Use the High-Level API

The `CatioClient` provides a simpler interface:

```python
async with CatioClient(target_ip="192.168.1.100") as client:
    # Discover EtherCAT devices
    await client.get_ethercat_devices()

    # Get all symbols from the symbol table
    all_symbols = await client.get_all_symbols()

    # Symbols are keyed by device ID
    for device_id, symbols in all_symbols.items():
        for name, symbol in symbols.items():
            print(f"{name}: {symbol.type_name} @ {symbol.index_group:#x}:{symbol.index_offset}")
```

## Recommendations

1. **For static terminals** (EK1100, EK1122, EL1014, EL1084, EL1124, EL2024, EL2024-0010, EL2124, EL2502, EL2595, EL2612, EL2624, EL3202, EL3202-0010, EL3314, EL3602, EL4134, EL9410, EL9505, EL9510, EL9512, EP2338-0002, EP2624-0002, EP3204-0002, EP3314-0002, EP4174-0002):
   - Use XML-derived YAML definitions directly
   - PDO structure is fixed and predictable

2. **For Type 1 counter terminals with configuration variants** (EL1502):
   - Query symbol table to determine per-channel vs combined configuration
   - YAML includes both; only one will be active

3. **For Type 2 Standard/Compact selectable terminals** (EL3104, EL3124, EP3174-0002, EP4374-0002):
   - Query symbol table at startup to determine which format is active
   - YAML should define both formats; reconcile with actual symbols

4. **For Type 3 multi-format terminals** (EL3356-0010):
   - Query symbol table to determine active value format (INT32, Real, Standard, Compact)
   - Check for optional features (Timestamp, Control)

5. **For Type 4 oversampling terminals** (EL3702, EL4732, ELM3704-0000):
   - Always query symbol table - sample count is runtime-configurable
   - ELM3704 additionally requires checking data format per channel
   - Use symbol naming patterns to extract configuration

6. **For unknown terminals**: Always query the symbol table to discover available PDOs

## See Also

- [Useful Notes on ADS and TwinCAT](../explanations/useful_notes_ads_twincat.md) - Details on ADS access methods and XML limitations
- [Terminal YAML Definitions](../explanations/terminal-yaml-definitions.md) - How terminal definitions are structured

## Appendix: Identifying Dynamic PDOs in ESI XML

The need for runtime discovery can often be identified by inspecting the `VendorSpecific` section of the Beckhoff ESI XML file for the terminal.

### The `<AlternativeSmMapping>` Tag

For many terminals (Type 2, Type 3, and Type 4 above), the XML explicitly defines mutually exclusive PDO configurations using the `<AlternativeSmMapping>` tag within the `<TwinCAT>` vendor-specific section.

**Example from EL3104 (Type 2):**

```xml
<VendorSpecific>
  <TwinCAT>
    <AlternativeSmMapping Default="1">
      <Name>Standard</Name>
      <Sm No="3">
        <Pdo>#x1a00</Pdo> <!-- AI Standard Channel 1 -->
        <Pdo>#x1a02</Pdo> <!-- AI Standard Channel 2 -->
        ...
      </Sm>
    </AlternativeSmMapping>
    <AlternativeSmMapping>
      <Name>Compact</Name>
      <Sm No="3">
        <Pdo>#x1a01</Pdo> <!-- AI Compact Channel 1 -->
        <Pdo>#x1a03</Pdo> <!-- AI Compact Channel 2 -->
        ...
      </Sm>
    </AlternativeSmMapping>
  </TwinCAT>
</VendorSpecific>
```

**Example from EL3356 (Type 3):**

In Type 3 terminals, this mechanism is used to switch between completely different data types (e.g., Integer vs Float) for the same process data.

```xml
<VendorSpecific>
  <TwinCAT>
    <AlternativeSmMapping Default="1">
      <Name>Standard (INT32)</Name>
      <Sm No="3">
        <Pdo>#x1a00</Pdo> <!-- Uses DINT (32-bit Integer) -->
        <Pdo>#x1a01</Pdo>
      </Sm>
    </AlternativeSmMapping>
    <AlternativeSmMapping>
      <Name>Standard (REAL)</Name>
      <Sm No="3">
        <Pdo>#x1a00</Pdo>
        <Pdo>#x1a02</Pdo> <!-- Uses REAL (32-bit Float) -->
      </Sm>
    </AlternativeSmMapping>
  </TwinCAT>
</VendorSpecific>
```

This structure indicates that the terminal has exclusive modes that fundamentally change which PDOs (and thus which data types and offsets) are assigned to Sync Manager 3 (Inputs).

### Multiple PDOs for the Same Function

For terminals like the EL1502 (Type 1), the indication is subtler. You will find multiple PDO definitions that cover overlapping functionality, and the CoE objects for PDO assignment (0x1C12 for RxPDOs, 0x1C13 for TxPDOs) will have a default value but allow modification.

**Example from EL1502:**
The XML defines three TxPDO maps for inputs:
- `0x1A00`: CNT TxPDO-Map Ch.1 (Channel 1 only)
- `0x1A01`: CNT TxPDO-Map Ch.2 (Channel 2 only)
- `0x1A02`: CNT TxPDO-Map (Both channels combined)

All three target the input memory, but TwinCAT will only allow one valid combination (either 0x1A00 + 0x1A01 OR 0x1A02) to be assigned to the Sync Manager at any time. The presence of "Combined" versus "Split" PDOs in the XML is a strong indicator of this dynamic behavior.
