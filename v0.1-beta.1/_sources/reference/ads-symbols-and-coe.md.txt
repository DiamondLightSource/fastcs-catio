# ADS Symbols and CoE Objects

This document describes how Beckhoff EtherCAT terminals expose data through ADS symbols and CoE (CANopen over EtherCAT) objects, and how to discover them at runtime.

## Overview

Beckhoff EtherCAT terminals expose two distinct data interfaces:

| Interface | Purpose | Access Method |
|-----------|---------|---------------|
| **ADS Symbols** | Real-time process data (I/O values) | ADS Read/Write by symbol name |
| **CoE Objects** | Configuration parameters | ADS Read/Write by index/subindex |

## ADS Symbols

### What Are ADS Symbols?

ADS (Automation Device Specification) symbols represent the live process data of an EtherCAT terminal. Each symbol maps to a memory location containing I/O values that update in real-time during the EtherCAT cycle.

For an EL3104 analog input terminal, symbols include:
- `AI Standard Channel 1` - Status and value for channel 1
- `AI Standard Channel 2` - Status and value for channel 2
- `WcState^WcState` - Working counter state (communication health)

### Symbol Discovery via ADS

To discover available symbols, query the ADS symbol table using:

**Index Group:** `0xF009` (ADSIGRP_SYM_INFOBYNAMEEX)
**Index Offset:** `0x0`

The TwinCAT ADS server returns a symbol table containing:

```
Symbol Entry:
  - Name: "Term 3 (EL3104).AI Standard Channel 1"
  - Index Group: 0xF020
  - Index Offset: 0x0
  - Size: 4 bytes
  - Data Type: "AI Standard Channel 1_TYPE"
  - ADS Type ID: 65 (BIGTYPE)
```

### Symbol Naming Convention

TwinCAT constructs symbol names hierarchically:

```
<Box Name>.<PDO Name>
```

Examples:
- `Term 3 (EL3104).AI Standard Channel 1`
- `Term 5 (EL2004).Channel 1^Output`
- `Term 7 (EL5101).ENC Status^Counter value`

The box name comes from the TwinCAT project configuration. The PDO name comes from the terminal's ESI XML definition.

### Index Groups for Terminals

EtherCAT terminals use specific index groups for symbol access:

| Index Group | Purpose |
|-------------|---------|
| `0xF020` | Input process data (TxPDO - terminal to controller) |
| `0xF021` | Working counter and diagnostic data |
| `0xF030` | Output process data (RxPDO - controller to terminal) |

### Reading Symbol Values

To read a symbol value:

1. **By Name:** Use `ADSIGRP_SYM_VALBYHND` (0xF005) with a handle obtained from `ADSIGRP_SYM_HNDBYNAME` (0xF003)

2. **By Index:** Use the symbol's index group and offset directly

```
ADS Read Request:
  Index Group: 0xF020
  Index Offset: 0x0
  Length: 4 bytes

Response: [Status (2 bytes)][Value (2 bytes)]
```

## CoE Objects

### What Are CoE Objects?

CoE (CANopen over EtherCAT) objects are configuration parameters stored in the terminal's object dictionary. They follow the CANopen standard (CiA 301) and are accessed via index and subindex.

Common CoE objects include:
- **0x1000** - Device Type
- **0x1008** - Manufacturer Device Name
- **0x1018** - Identity Object
- **0x8000+** - Terminal-specific settings (e.g., filter settings, calibration)

### CoE Object Structure

Each CoE object has:

| Field | Description |
|-------|-------------|
| Index | 16-bit object index (e.g., 0x8000) |
| SubIndex | 8-bit subindex within the object |
| Data Type | CANopen data type (BOOL, UINT16, etc.) |
| Access | Read-only (ro), Read-write (rw), Write-only (wo) |
| Default | Factory default value |

### Discovering CoE Objects

CoE objects are defined in the terminal's ESI XML file under the `<Profile><Dictionary><Objects>` section. However, you can also discover them at runtime.

**Method 1: SDO Information Service**

Use the CANopen SDO Information protocol to enumerate objects:

```
Index 0x1000 (Device Type):
  SubIndex 0: UDINT = 0x00001389

Index 0x8000 (AI Settings Ch.1):
  SubIndex 0: Number of entries = 19
  SubIndex 1: Enable user scale = FALSE
  SubIndex 2: Presentation = Signed
  ...
```

**Method 2: ADS CoE Access**

TwinCAT provides ADS access to CoE objects via:

| Index Group | Purpose |
|-------------|---------|
| `0xF302` | CoE object dictionary access |
| `0xF100` + Slave Address | Direct SDO access |

### Reading CoE Objects via ADS

To read a CoE object:

```
ADS Read Request:
  Net ID: <AMS Net ID>
  Port: 0x1001 (EtherCAT Master)
  Index Group: 0xF302
  Index Offset: (SlaveAddr << 16) | (Index)
  SubIndex: <subindex>
```

### Common CoE Objects by Terminal Type

**Analog Input (EL31xx):**
- 0x8000: AI Settings Channel 1
  - Enable user scale, Presentation, Filter settings
- 0x8010: AI Settings Channel 2
- 0x9000: AI Internal data Channel 1

**Analog Output (EL4xxx):**
- 0x8000: AO Settings Channel 1
  - Output value, Manual control, Watchdog
- 0x8010: AO Settings Channel 2

**Digital I/O (EL1xxx, EL2xxx):**
- 0x8000: DI/DO Settings
  - Filter enable, Invert polarity

**Encoder (EL5xxx):**
- 0x8000: ENC Settings
  - Counter mode, Gate mode, Reference settings

## Runtime vs Static Discovery

| Aspect | Symbols | CoE Objects |
|--------|---------|-------------|
| **Static (XML)** | PDO entries define structure | Full object dictionary in XML |
| **Runtime** | Query symbol table via ADS | Query via SDO Information |
| **Naming** | TwinCAT generates full path | Fixed by CANopen standard |
| **Type Names** | Generated (e.g., `_TYPE` suffix) | Defined in XML DataTypes |

## Practical Example: EL3104

For an EL3104 4-channel analog input:

**Symbols discovered:**
```
Term 3 (EL3104).AI Standard Channel 1  (4 bytes, BIGTYPE)
Term 3 (EL3104).AI Standard Channel 2  (4 bytes, BIGTYPE)
Term 3 (EL3104).AI Standard Channel 3  (4 bytes, BIGTYPE)
Term 3 (EL3104).AI Standard Channel 4  (4 bytes, BIGTYPE)
Term 3 (EL3104).WcState^WcState        (1 bit, BOOL)
```

**CoE objects available:**
```
0x1000: Device Type = 0x00001389
0x1008: Device Name = "EL3104"
0x8000: AI Settings Ch.1 (19 subindices)
0x8010: AI Settings Ch.2 (19 subindices)
0x8020: AI Settings Ch.3 (19 subindices)
0x8030: AI Settings Ch.4 (19 subindices)
```

## Related Documentation

- [Beckhoff XML Format](beckhoff-xml-format.md) - ESI XML structure
- [Composite Types](../explanations/composite-types.md) - How TwinCAT generates type structures
- [Beckhoff InfoSys: ADS](https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/index.html)
- [Beckhoff InfoSys: CoE](https://infosys.beckhoff.com/english.php?content=../content/1033/ethercatsystem/index.html)
