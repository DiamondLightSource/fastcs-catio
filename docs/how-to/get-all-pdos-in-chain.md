# How to Get All PDOs in an EtherCAT Chain

This guide explains how to discover the actual PDO (Process Data Object) configuration of terminals at runtime, which is necessary when the ESI XML cannot reliably predict the symbol structure.

## Overview

Some EtherCAT terminals have **dynamic PDO configurations** that depend on:
- TwinCAT project settings
- Selected operation mode
- Oversampling factor
- PDO assignment choices

For these terminals, you must query the TwinCAT symbol table at runtime rather than relying solely on XML-derived definitions.

## Terminals in the Test Configuration

The following terminals are defined in `tests/ads_sim/terminal_types.yaml`:

| Terminal | Description | PDO Type | Notes |
|----------|-------------|----------|-------|
| EK1100 | EtherCAT Coupler | None | Bus coupler, no process data |
| EK1110 | EtherCAT Extension | None | Extension module, no process data |
| EL1004 | 4Ch Digital Input 24V | Static | Fixed 4 BOOL inputs |
| EL1014 | 4Ch Digital Input 24V | Static | Fixed 4 BOOL inputs |
| EL1084 | 8Ch Digital Input 24V | Static | Fixed 8 BOOL inputs |
| EL2024 | 4Ch Digital Output 24V | Static | Fixed 4 BOOL outputs |
| EL1502 | 2Ch Up/Down Counter | **Dynamic** | Multiple PDO configurations |
| EL9410 | E-Bus Power Supply | Static | Fixed 2 status BOOLs |
| EL3702 | 2Ch Analog Input Oversample | **Dynamic** | 1-100 samples per channel |

## Terminals Requiring Runtime Discovery

### EL1502 - Counter Terminal

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

### EL3702 - Oversampling Analog Input

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

1. **For static terminals** (EL1004, EL1014, EL2024, etc.): Use XML-derived YAML definitions directly

2. **For dynamic terminals** (EL1502, EL3702, etc.):
   - Use YAML as a starting template
   - Query TwinCAT symbol table at startup
   - Reconcile YAML definitions with actual symbols
   - Log warnings for mismatches

3. **For unknown terminals**: Always query the symbol table to discover available PDOs

## See Also

- [Useful Notes on ADS and TwinCAT](../explanations/useful_notes_ads_twincat.md) - Details on ADS access methods and XML limitations
- [Terminal YAML Definitions](../explanations/terminal-yaml-definitions.md) - How terminal definitions are structured
