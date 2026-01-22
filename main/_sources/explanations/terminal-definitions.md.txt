# Terminal Type Definitions

Terminal type definitions in CATio describe Beckhoff EtherCAT I/O terminals and their characteristics. These definitions are stored in YAML files organized by terminal class in `src/fastcs_catio/terminals/`.

## Purpose

Terminal type definitions serve two purposes:

1. **ADS Simulation**: The test ADS simulator uses these definitions to emulate terminal behavior and create accurate symbol tables
2. **FastCS Integration**: (Future) These definitions will be used to dynamically generate FastCS controller classes for each terminal type

## File Organization

Terminal definitions are organized by functional class:

- `bus_couplers.yaml` - EtherCAT couplers and extensions (EK1100, EK1110, etc.)
- `digital_input.yaml` - Digital input terminals (EL1004, EL1014, EL1084, etc.)
- `digital_output.yaml` - Digital output terminals (EL2004, EL2024, EL2809, etc.)
- `counter.yaml` - Counter and frequency input terminals (EL1502, etc.)
- `analog_input.yaml` - Analog input terminals (EL3004, EL3104, EL3602, etc.)
- `analog_output.yaml` - Analog output terminals (EL4004, EL4134, etc.)
- `power_supply.yaml` - Power supply and system terminals (EL9410, EL9512, etc.)

## Terminal Definition Structure

Each terminal type definition contains:

### Identity

CANopen identity information that uniquely identifies the terminal:

```yaml
identity:
  vendor_id: 2              # Vendor ID (2 = Beckhoff)
  product_code: 0x07E83052  # Product code
  revision_number: 0x00100000
```

### Symbol Nodes

Symbol nodes define the high-level symbols that appear in the ADS symbol table. The client expands these based on `type_name` patterns (see `src/fastcs_catio/symbols.py` for expansion logic).

```yaml
symbol_nodes:
  - name_template: "Channel {channel}^Output"
    index_group: 0xF031  # ADS index group
    size: 0              # Data size in bytes (0 for bit)
    ads_type: 33         # ADS data type (33=BIT, 65=BIGTYPE)
    type_name: "BIT"     # Type pattern for expansion
    channels: 4          # Number of channels
```

### Symbol Node Properties

| Property | Description |
|----------|-------------|
| `name_template` | Name pattern supporting `{channel}` placeholder |
| `index_group` | ADS index group (see table below) |
| `size` | Data size in bytes (0 for bit-level access) |
| `ads_type` | ADS data type (33=BIT, 65=BIGTYPE) |
| `type_name` | Type pattern used by client for symbol expansion |
| `channels` | Number of channels (for multi-channel terminals) |

### ADS Index Groups

| Index Group | Name | Purpose |
|-------------|------|---------|
| 0xF020 | RWIB | Input bytes (read/write) |
| 0xF021 | RWIX | Input bits (read/write) |
| 0xF030 | RWOB | Output bytes (read/write) |
| 0xF031 | RWOX | Output bits (read/write) |

## Symbol Naming Convention

Symbols follow the TwinCAT naming convention:

```
TIID^Device N (EtherCAT)^<terminal_name>^<symbol_name>
```

Example: `TIID^Device 1 (EtherCAT)^Term 4 (EL2024)^Channel 1^Output`

## Type Name Patterns

The `type_name` field must match expansion patterns defined in `src/fastcs_catio/symbols.py`:

| Type Name | Expansion | Example Terminal |
|-----------|-----------|------------------|
| `BIT` | Simple bit value | Digital I/O |
| `Channel 1_TYPE` | Digital input channel (8 bits) | EL1004, EL1014 |
| `CNT Inputs_TYPE` | Counter inputs (status + value) | EL1502 |
| `CNT Outputs_TYPE` | Counter outputs (control + set value) | EL1502 |
| `AI Standard Channel 1_TYPE` | Analog input (status + value) | EL3004, EL3104 |
| `AO Output Channel 1_TYPE` | Analog output value | EL4004, EL4134 |

The client expands these type patterns into multiple actual symbols. For example, `Channel 1_TYPE` with 8 channels expands into:

- `Channel 1^Input` (bit 0)
- `Channel 2^Input` (bit 1)
- ...
- `Channel 8^Input` (bit 7)

## Example: Complete Terminal Definition

```yaml
terminal_types:
  EL2024:
    description: "4-channel Digital Output 24V DC"
    identity:
      vendor_id: 2
      product_code: 0x07E83052
      revision_number: 0x00100000
    symbol_nodes:
      # Output channels - individual bit symbols
      - name_template: "Channel {channel}^Output"
        index_group: 0xF031  # ADSIGRP_IOIMAGE_RWOX
        size: 0              # Bit-level access
        ads_type: 33         # BIT
        type_name: "BIT"
        channels: 4
      # Working counter state
      - name_template: "WcState^WcState"
        index_group: 0xF021
        size: 0
        ads_type: 33
        type_name: "BIT"
        channels: 1
```

## Adding New Terminal Types

To add a new terminal type:

1. Identify the appropriate YAML file in `src/fastcs_catio/terminals/` based on terminal class
2. Add the terminal definition with:
   - Correct CANopen identity (vendor_id, product_code, revision_number)
   - Symbol node definitions matching the terminal's I/O structure
   - Appropriate `type_name` values that match patterns in `symbols.py`
3. The terminal type will be automatically loaded by the ADS simulator

## See Also

- [ADS Client Architecture](ads-client.md)
- [Architecture Overview](architecture-overview.md)
- Terminal type source files: `src/fastcs_catio/terminals/`
- Symbol expansion logic: `src/fastcs_catio/symbols.py`
