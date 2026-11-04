# EtherCAT Composite Types

This document describes how the TwinCAT EtherCAT Master generates composite data types for terminal process data, and which types are created for different terminal categories.

## Overview

When TwinCAT compiles an EtherCAT configuration, it creates **composite types** (structured data types) for each terminal's process data. These types group related fields into single addressable units.

The EtherCAT Master generates these types automatically based on the PDO (Process Data Object) definitions in each terminal's ESI XML file.

## Type Generation Process

### From XML PDO to Composite Type

The ESI XML defines PDOs with individual entries:

```xml
<TxPdo Fixed="1">
    <Index>#x1a02</Index>
    <Name>AI Standard Channel 1</Name>
    <Entry>
        <Name>Status</Name>
        <DataType>UINT</DataType>
        <BitLen>16</BitLen>
    </Entry>
    <Entry>
        <Name>Value</Name>
        <DataType>INT</DataType>
        <BitLen>16</BitLen>
    </Entry>
</TxPdo>
```

TwinCAT generates a composite type:

```
Type Name: "AI Standard Channel 1_TYPE"
ADS Type: 65 (BIGTYPE)
Size: 4 bytes
Members:
  - Status (UINT, offset 0, 2 bytes)
  - Value (INT, offset 2, 2 bytes)
```

### Naming Convention

TwinCAT constructs type names by appending `_TYPE` to the PDO name:

| PDO Name | Generated Type Name |
|----------|---------------------|
| `AI Standard Channel 1` | `AI Standard Channel 1_TYPE` |
| `CNT Inputs` | `CNT Inputs_TYPE` |
| `AO Output Channel 1` | `AO Output Channel 1_TYPE` |
| `Inputs` | `Inputs_TYPE` |

**Note:** The type name always uses the first channel's name (e.g., "Channel 1"), even when the same type is used for all channels.

### Channel Replication

For multi-channel terminals, TwinCAT creates:
- **One type definition** shared across channels
- **Multiple symbol instances** using that type

Example for EL3104 (4-channel analog input):
```
Type: "AI Standard Channel 1_TYPE" (defined once)

Symbols:
  - AI Standard Channel 1 (uses AI Standard Channel 1_TYPE)
  - AI Standard Channel 2 (uses AI Standard Channel 1_TYPE)
  - AI Standard Channel 3 (uses AI Standard Channel 1_TYPE)
  - AI Standard Channel 4 (uses AI Standard Channel 1_TYPE)
```

## Composite Types by Terminal Category

### Analog Input Terminals (EL31xx, EL32xx, EL33xx)

**Standard Analog Input (EL3004, EL3104, etc.)**

PDO: `AI Standard Channel N`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Status word (underrange, overrange, error flags) |
| Value | INT | 2 | Signed 16-bit analog value |

Total size: 4 bytes

**High-Resolution Analog Input (EL3602, EL3612)**

PDO: `AI Inputs Channel N`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Status word |
| Value | DINT | 2 | Signed 32-bit analog value (24-bit resolution) |

Total size: 6 bytes

**Thermocouple/RTD Input (EL3202, EL3204, EL3314)**

PDO: `RTD Inputs Channel N` or `TC Inputs Channel N`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Status word |
| Value | INT | 2 | Temperature value (scaled) |

Total size: 4 bytes

### Analog Output Terminals (EL4xxx)

**Standard Analog Output (EL4002, EL4004, EL4102)**

PDO: `AO Output Channel N`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| AnalogOutput | INT | 0 | Signed 16-bit output value |

Total size: 2 bytes

**Some terminals include status feedback:**

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| AnalogOutput | INT | 0 | Output value |
| Status | UINT | 2 | Output status |

Total size: 4 bytes

### Digital Input Terminals (EL1xxx)

**Simple Digital Input (EL1004, EL1008)**

PDO: `Channel N^Input` or `Inputs`

For single-bit access:
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Input | BOOL | 0 (bit N) | Single digital input state |

For grouped access (all channels in one word):
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Inputs | BYTE/UINT | 0 | Packed digital inputs |

### Digital Output Terminals (EL2xxx)

**Simple Digital Output (EL2004, EL2008)**

PDO: `Channel N^Output` or `Outputs`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Output | BOOL | 0 (bit N) | Single digital output state |

For grouped access:
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Outputs | BYTE/UINT | 0 | Packed digital outputs |

### Counter/Encoder Terminals (EL5xxx)

**Incremental Encoder (EL5101)**

PDO: `ENC Status` (input) and `ENC Control` (output)

**ENC Status (Input):**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Encoder status flags |
| CounterValue | UDINT | 2 | 32-bit counter value |
| LatchValue | UDINT | 6 | Latched counter value |

Total size: 10 bytes

**ENC Control (Output):**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Control | UINT | 0 | Control word |
| SetCounterValue | UDINT | 2 | Value to set counter |

Total size: 6 bytes

**Up/Down Counter (EL1502, EL1512)**

PDO: `CNT Inputs` (input) and `CNT Outputs` (output)

**CNT Inputs:**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Counter status |
| CounterValue | UDINT | 2 | Current counter value |

Total size: 6 bytes

**CNT Outputs:**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Control | UINT | 0 | Counter control |
| SetCounterValue | UDINT | 2 | Preset value |

Total size: 6 bytes

### Oversampling Terminals (EL3702, EL4732)

**Oversampling Analog Input (EL3702)**

These terminals produce arrays of samples per cycle:

PDO: `Ch1 CycleCount` and `Ch1 Samples`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| CycleCount | UINT | 0 | Number of samples this cycle |
| Samples | ARRAY[0..99] OF INT | 2 | Array of oversampled values |

Total size: 202 bytes (2 + 100*2)

### Communication Terminals (EL6xxx)

**Serial Interface (EL6001, EL6021)**

PDO structure varies by protocol mode. Common pattern:

**Input:**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Status | UINT | 0 | Communication status |
| DataLength | UINT | 2 | Received data length |
| Data | ARRAY OF BYTE | 4 | Received data buffer |

**Output:**
| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| Control | UINT | 0 | Communication control |
| DataLength | UINT | 2 | Send data length |
| Data | ARRAY OF BYTE | 4 | Send data buffer |

## Special Types

### Working Counter State

All terminals include a diagnostic symbol:

PDO: `WcState^WcState`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| WcState | BOOL | 0 | Working counter valid (communication OK) |

This is typically a single bit, not a composite type.

### InfoData (Optional)

Some terminals provide extended diagnostic information:

PDO: `InfoData^State` and `InfoData^TxPdoState`

| Member | Type | Offset | Description |
|--------|------|--------|-------------|
| State | UINT | 0 | Terminal state |
| AdsAddr | UINT | 2 | ADS address |

## Type Inheritance and Variants

### PDO Selection

Many terminals offer multiple PDO mappings (Standard, Compact, Complete). The composite type depends on which PDO mapping is selected:

**EL3104 PDO Options:**
- `AI Standard` - Status + Value (4 bytes)
- `AI Compact` - Value only (2 bytes)
- `AI Complete` - Full status word + Value (4 bytes)

The generated type name changes accordingly:
- `AI Standard Channel 1_TYPE`
- `AI Compact Channel 1_TYPE`

### Revision-Specific Types

Different terminal revisions may have different PDO structures. TwinCAT generates appropriate types based on the specific revision detected.

## Summary Table

| Terminal Category | Common Type Names | Typical Size |
|-------------------|-------------------|--------------|
| Analog Input (16-bit) | `AI Standard Channel 1_TYPE` | 4 bytes |
| Analog Input (24-bit) | `AI Inputs Channel 1_TYPE` | 6 bytes |
| Analog Output | `AO Output Channel 1_TYPE` | 2-4 bytes |
| Digital Input | `Inputs_TYPE` or individual bits | 1-2 bytes |
| Digital Output | `Outputs_TYPE` or individual bits | 1-2 bytes |
| Counter/Encoder Input | `CNT Inputs_TYPE`, `ENC Status_TYPE` | 6-10 bytes |
| Counter/Encoder Output | `CNT Outputs_TYPE`, `ENC Control_TYPE` | 6 bytes |

## Related Documentation

- [ADS Symbols and CoE](ads-symbols-and-coe.md) - How to discover symbols
- [Beckhoff XML Format](beckhoff-xml-format.md) - ESI XML structure
- [Composite Types Implementation](../explanations/composite-types.md) - How we model these types
