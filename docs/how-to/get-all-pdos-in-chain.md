# How to Get All PDOs in an EtherCAT Chain

This guide explains how to discover the actual PDO (Process Data Object) configuration of terminals at runtime, which is necessary when the ESI XML cannot reliably predict the symbol structure.

The original intention of the YAML based terminal type descriptions created using `catio-terminals` (see [Terminal YAML Definitions](../explanations/terminal-yaml-definitions.md)) was to provide a complete mapping of all PDOs for each terminal type, generating this information from the Beckhoff ESI XML files.

However, some terminals have dynamic PDO configurations that depend on project settings in TwinCAT, making it impossible to determine the exact PDO layout from XML alone. This document outlines the extent of the problem by highlighting those terminals used at Diamond Light Source that require runtime discovery.

## Overview

Some EtherCAT terminals have **dynamic PDO configurations** that depend on:
- TwinCAT project settings
- Selected operation mode
- Oversampling factor
- PDO assignment choices

For these terminals, you must query the TwinCAT symbol table at runtime rather than relying solely on XML-derived definitions.

## Terminals in the Test Configuration

The terminals listed here are the complete set used at DLS at the time of writing (see [DLS Terminals Reference](../reference/DLS_terminals.md) for details).

The terminals are categorized by type, with notes on which require runtime discovery.

| Terminal | Description | PDO Type | Notes |
|----------|-------------|----------|-------|
| EK1100 | EtherCAT Coupler | None | Bus coupler, no process data |
| EK1122 | 2 Port EtherCAT Junction | None | Junction module, no process data |
| EL1014 | 4Ch Digital Input 24V, 10us | Static | Fixed 4 BOOL inputs |
| EL1084 | 4Ch Digital Input 24V, 3ms, negative | Static | Fixed 4 BOOL inputs |
| EL1124 | 4Ch Digital Input 5V, 10us | Static | Fixed 4 BOOL inputs |
| EL1502 | 2Ch Up/Down Counter 24V, 100kHz | **Dynamic Type 1** | Multiple PDO configurations (per-channel vs combined) |
| EL2024 | 4Ch Digital Output 24V, 2A | Static | Fixed 4 BOOL outputs |
| EL2024-0010 | 4Ch Digital Output 24V, 2A (variant) | Static | Fixed 4 BOOL outputs |
| EL2124 | 4Ch Digital Output 5V, 20mA | Static | Fixed 4 BOOL outputs |
| EL2502 | 2Ch PWM Output 24V | Static | Fixed 2 UINT PWM outputs |
| EL2595 | 1Ch LED Constant Current | Static | Status + multi-field control outputs |
| EL2612 | 2Ch Relay Output CO | Static | Fixed 2 BOOL relay outputs |
| EL2624 | 4Ch Relay Output NO | Static | Fixed 4 BOOL relay outputs |
| EL3104 | 4Ch Analog Input +/-10V Diff | **Dynamic Type 2** | Standard vs Compact PDO selection |
| EL3124 | 4Ch Analog Input 4-20mA Diff | **Dynamic Type 2** | Standard vs Compact PDO selection |
| EL3202 | 2Ch Analog Input PT100 (RTD) | Static | Fixed RTD Inputs per channel |
| EL3202-0010 | 2Ch Analog Input PT100 (RTD, variant) | Static | Fixed RTD Inputs per channel |
| EL3314 | 4Ch Analog Input Thermocouple | Static | Fixed TC Inputs + optional CJ compensation outputs |
| EL3356-0010 | 1Ch Resistor Bridge, 16bit High Precision | **Dynamic Type 3** | Multiple PDO formats (INT32, Real, Standard, Compact) |
| EL3602 | 2Ch Analog Input +/-10V Diff, 24bit | Static | Fixed AI Inputs per channel |
| EL3702 | 2Ch Analog Input +/-10V Oversample | **Dynamic Type 4** | 1-100 samples per channel |
| EL4134 | 4Ch Analog Output +/-10V, 16bit | Static | Fixed AO Output per channel |
| EL4732 | 2Ch Analog Output +/-10V Oversample | **Dynamic Type 4** | Configurable sample count |
| EL9410 | E-Bus Power Supply (Diagnostics) | Static | Fixed 2 status BOOLs (Us, Up undervoltage) |
| EL9505 | Power Supply Terminal 5V | Static | Fixed status (Power OK, Overload) |
| EL9510 | Power Supply Terminal 10V | Static | Fixed status (Power OK, Overload) |
| EL9512 | Power Supply Terminal 12V | Static | Fixed status (Power OK, Overload) |
| ELM3704-0000 | 4Ch Universal Analog Input, 24bit | **Dynamic Type 4** | Oversampling (1-100), data format (INT16/INT32/REAL), per-channel config |
| EP2338-0002 | 8Ch Digital I/O 24V, 0.5A | Static | Fixed 8 inputs + 8 outputs |
| EP2624-0002 | 4Ch Relay Output NO | Static | Fixed 4 BOOL relay outputs |
| EP3174-0002 | 4Ch Analog Input configurable | **Dynamic Type 2** | Standard vs Compact PDO selection |
| EP3204-0002 | 4Ch Analog Input PT100 (RTD) | Static | Fixed RTD Inputs per channel |
| EP3314-0002 | 4Ch Analog Input Thermocouple | Static | Fixed TC Inputs + optional CJ compensation outputs |
| EP4174-0002 | 4Ch Analog Output configurable | Static | Fixed AO Outputs per channel |
| EP4374-0002 | 2Ch AI + 2Ch AO configurable | **Dynamic Type 2** | Standard vs Compact PDO selection for inputs |

## Terminals Requiring Runtime Discovery

### Type 1: Counter Terminals with Configuration Variants (EL1502)

#### EL1502 - Up/Down Counter

**Problem:** The ESI XML defines multiple PDO configurations:

| Configuration | PDO Names | Symbol Pattern |
|---------------|-----------|----------------|
| Per-channel | `CNT Inputs Channel 1`, `CNT Inputs Channel 2` | `CNT Inputs Channel {n}.Counter value` |
| Combined | `CNT Inputs` | `CNT Inputs.Counter value` |

The YAML file includes **both** configurations, but only one will be active in TwinCAT.

**Runtime Discovery:**
```python
# Query actual symbols for an EL1502
symbols = await client.get_all_symbols()
el1502_symbols = [s for s in symbols[device_id] if "EL1502" in s.name]

# Check which configuration is active
has_per_channel = any("Channel 1" in s.name for s in el1502_symbols)
has_combined = any("CNT Inputs.Counter value" in s.name for s in el1502_symbols)
```

### Type 2: Analog Input with Standard/Compact PDO Selection (EL3104, EL3124, EP3174-0002, EP4374-0002)

**Problem:** These analog input terminals offer two PDO formats per channel:

| Format | PDO Name Pattern | Contents |
|--------|------------------|----------|
| Standard | `AI Standard Channel {n}` | Status word (underrange, overrange, limits, error) + Value |
| Compact | `AI Compact Channel {n}` | Value only (no status) |

The TwinCAT project selects one format per channel. Both are defined in XML as optional.

**Runtime Discovery:**
```python
# Query actual symbols for analog input terminals
symbols = await client.get_all_symbols()
ai_symbols = [s for s in symbols[device_id] if "AI" in s.name]

# Determine which format is active
has_standard = any("Standard" in s.name for s in ai_symbols)
has_compact = any("Compact" in s.name for s in ai_symbols)

if has_standard:
    print("Using Standard PDO format (status + value)")
elif has_compact:
    print("Using Compact PDO format (value only)")
```

### Type 3: Multi-Format Terminals (EL3356-0010)

**Problem:** The EL3356-0010 offers multiple PDO formats for measurement data:

| Format | PDO Name | Data Type |
|--------|----------|-----------|
| INT32 | `RMB Value (INT32)` | DINT (32-bit signed) |
| Real | `RMB Value (Real)` | REAL (32-bit float) |
| Standard Ch1/Ch2 | `AI Standard Channel {n}` | Status + DINT value |
| Compact Ch1/Ch2 | `AI Compact Channel {n}` | DINT value only |

Additionally, it has optional `RMB Status`, `RMB Timestamp`, and `RMB Control` PDOs.

**Runtime Discovery:**
```python
# Query actual symbols for EL3356
symbols = await client.get_all_symbols()
el3356_symbols = [s for s in symbols[device_id] if "EL3356" in s.name]

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

**Problem:** The number of samples per channel is configurable (1-100). The XML only shows a template with one sample.

| Oversampling | Samples per Channel | Total Symbols |
|--------------|---------------------|---------------|
| 1x (default) | 1 | 2 values |
| 10x | 10 | 20 values |
| 100x | 100 | 200 values |

**Runtime Discovery:**
```python
# Query actual symbols for an EL3702
symbols = await client.get_all_symbols()
el3702_ch1 = [s for s in symbols[device_id]
              if "EL3702" in s.name and "Ch1" in s.name and "Value" in s.name]

oversampling_factor = len(el3702_ch1)
print(f"EL3702 configured for {oversampling_factor}x oversampling")
```

#### EL4732 - 2Ch Oversampling Analog Output

**Problem:** Similar to EL3702, the sample count is configurable. The output PDO contains arrays of values.

**Runtime Discovery:**
```python
# Query actual symbols for an EL4732
symbols = await client.get_all_symbols()
el4732_symbols = [s for s in symbols[device_id] if "EL4732" in s.name and "Value" in s.name]

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
elm3704_symbols = [s for s in symbols[device_id] if "ELM3704" in s.name]

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
        for symbol in symbols:
            print(f"{symbol.name}: {symbol.type_name} @ {symbol.index_group:#x}:{symbol.index_offset}")
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
