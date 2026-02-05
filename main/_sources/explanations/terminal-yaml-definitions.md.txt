# Terminal YAML Definitions

This document explains how to define Beckhoff EtherCAT terminals in YAML for use with the ADS simulator and FastCS controller generation.

These YAML files can be created and edited using the `catio-terminals` GUI tool (see [Using catio-terminals](#using-catio-terminals) below).

For background on the underlying Beckhoff technologies, see:
- [ADS Symbols and CoE Objects](../reference/ads-symbols-and-coe.md) - What symbols and CoE objects are
- [EtherCAT Composite Types](../reference/ethercat-composite-types.md) - How the EtherCAT Master generates composite types

## Overview

Terminal definitions are YAML files that describe:
- **Composite types** - Bit field definitions for packed status/control bytes
- **Terminal identity** - Vendor ID, product code, revision
- **Symbol nodes** - Process data (I/O values) accessible via ADS
- **CoE objects** - Configuration parameters with subindices
- **Runtime symbols** - Diagnostic symbols added by the EtherCAT master (defined separately)

## File Organization

Terminal definitions live in `src/catio_terminals/terminals/`, organized as follows:

| File | Terminal Types |
|------|----------------|
| `terminal_types.yaml` | All terminals currently in use at DLS |

Supporting configuration files in `src/catio_terminals/config/`:

| File | Purpose |
|------|---------|
| `runtime_symbols.yaml` | EtherCAT master diagnostic symbols |

## Terminal Definition Structure

### Top-Level Structure

```yaml
composite_types:
  InputBits:
    description: 'Bit fields: Input'
    ads_type: 65
    size: 1
    members: []
    bit_fields:
      - name: Input
        bit: 0
  # ... more composite types

terminal_types:
  EL3104:
    description: "4-channel Analog Input +/-10V 16-bit"
    identity:
      vendor_id: 2
      product_code: 203227218
      revision_number: 1048576
    group_type: AnaIn
    symbol_nodes:
      # ... symbols
    coe_objects:
      # ... CoE objects
```

### Composite Types Section

Composite types define packed bit fields for status and control bytes:

```yaml
composite_types:
  Status__Underrange_6Bits:
    description: 'Bit fields: Status__Underrange, Status__Overrange, Status__Error,
      Status__Sync error, Status__TxPDO State, Status__TxPDO Toggle'
    ads_type: 65
    size: 1
    members: []
    bit_fields:
      - name: Status__Underrange
        bit: 0
      - name: Status__Overrange
        bit: 1
      - name: Status__Error
        bit: 2
      - name: Status__Sync error
        bit: 3
      - name: Status__TxPDO State
        bit: 4
      - name: Status__TxPDO Toggle
        bit: 5
```

### Identity Section

Uniquely identifies the terminal hardware:

```yaml
identity:
  vendor_id: 2              # Beckhoff = 2
  product_code: 203227218   # From ESI XML (decimal)
  revision_number: 1048576  # Firmware revision
```

These values come from the terminal's ESI XML `<Type>` element.

### Symbol Nodes

Symbol nodes define the ADS symbols for process data. Each symbol maps to memory that updates during the EtherCAT cycle.

```yaml
symbol_nodes:
  - name_template: CNT Inputs Channel {channel}
    index_group: 61488
    type_name: Status__Output functions enabled_7Bits
    channels: 2
    access: Read-only
    fastcs_name: cnt_inputs_channel_{channel}
    selected: false
  - name_template: CNT Inputs.Counter value
    index_group: 61488
    type_name: UDINT
    channels: 1
    access: Read-only
    fastcs_name: cnt_inputs_counter_value
    selected: true
```

| Field | Description |
|-------|-------------|
| `name_template` | Symbol name pattern. Use `{channel}` for multi-channel terminals |
| `index_group` | ADS index group (see table below) |
| `type_name` | Data type - primitive (INT, BOOL, UDINT) or composite type name |
| `channels` | Number of channels using this pattern |
| `access` | `Read-only` (inputs) or `Read/Write` (outputs) |
| `fastcs_name` | Snake_case name for FastCS attributes |
| `selected` | Whether this symbol is included in FastCS controllers |

**ADS Index Groups:**

| Value | Hex | Purpose |
|-------|-----|---------|
| 61472 | 0xF020 | Input bytes (TxPDO - terminal to controller) |
| 61473 | 0xF021 | Input bits and diagnostics |
| 61488 | 0xF030 | Output bytes (RxPDO - controller to terminal) |
| 61489 | 0xF031 | Output bits |

### CoE Objects

CoE (CANopen over EtherCAT) objects define configuration parameters with subindices:

```yaml
coe_objects:
  - index: 32768           # 0x8000 in decimal
    name: CNT Settings Ch.1
    type_name: DT8000
    bit_size: 128
    access: rw
    subindices:
      - subindex: 1
        name: Enable function to set output
        type_name: BOOL
        bit_size: 1
        access: rw
        default_data: '00'
        fastcs_name: enable_function_to_set_output_idx8000
      - subindex: 17
        name: Switch on treshold value
        type_name: UDINT
        bit_size: 32
        access: rw
        default_data: '00000000'
        fastcs_name: switch_on_treshold_value_idx8000
    fastcs_name: cnt_settings_ch_1_idx8000
```

| Field | Description |
|-------|-------------|
| `index` | CoE index (decimal) |
| `name` | Human-readable name |
| `type_name` | Data type for the object |
| `bit_size` | Total size in bits |
| `access` | `ro` (read-only) or `rw` (read-write) |
| `subindices` | List of subindex definitions |
| `fastcs_name` | FastCS attribute name |

### Computed Properties

The `size` and `ads_type` fields are computed from `type_name`:

```yaml
# You write:
- name_template: "Counter value"
  type_name: UDINT

# The system computes:
#   size: 4 (bytes)
#   ads_type: 19 (ADS type code for UDINT)
```

Type mappings are defined in `src/catio_terminals/ads_types.py`.

## Runtime Symbols

The EtherCAT master adds diagnostic symbols at runtime that aren't in Beckhoff's XML. These are defined separately in `runtime_symbols.yaml`.

### Common Runtime Symbols

| Symbol | Type | Description |
|--------|------|-------------|
| `WcState^WcState` | BIT | Working counter - communication health |
| `InfoData^State` | UINT | EtherCAT state machine state |
| `InputToggle` | BIT | Toggles each cycle for data freshness |

### Runtime Symbol Definition

```yaml
# src/catio_terminals/config/runtime_symbols.yaml

runtime_symbols:
  - name_template: WcState^WcState
    index_group: 61473  # 0xF021
    type_name: BIT
    channels: 1
    access: Read-only
    fastcs_name: WcstateWcstate
    description: Working Counter State
    group_blacklist:
      - Coupler  # Couplers may not have WcState
```

### Filtering Runtime Symbols

Runtime symbols can be filtered to apply only to certain terminals:

| Filter | Description |
|--------|-------------|
| `whitelist` | Only apply to these terminal IDs |
| `blacklist` | Exclude these terminal IDs |
| `group_whitelist` | Only apply to these group types (AnaIn, DigOut, etc.) |
| `group_blacklist` | Exclude these group types |

(using-catio-terminals)=
## Using catio-terminals

The `catio-terminals` GUI editor simplifies creating and maintaining terminal YAML files.

### Installation

```bash
uv pip install -e ".[terminals]"
```

### Update XML Cache

```bash
catio-terminals update-cache
```

Downloads Beckhoff's ESI XML files to `~/.cache/catio_terminals/`.

### Edit Terminal Files

```bash
catio-terminals edit                    # Create new file
catio-terminals edit terminals.yaml     # Edit existing file
```

### Workflow

1. **Add Terminal** - Search Beckhoff's catalog by ID
2. **Select Symbols** - Choose which PDO entries to include
3. **Save** - Only selected symbols are written to YAML

The editor merges your selections with XML data, ensuring symbols match Beckhoff's official definitions.

## Adding a New Terminal

### Option 1: Using catio-terminals (Recommended)

1. Launch the editor and open the appropriate YAML file
2. Click "Add Terminal" and search for the terminal ID
3. Select the symbols to include
4. Save

### Option 2: Manual Entry

1. Find the terminal in Beckhoff's XML (see [Beckhoff XML Format](../reference/beckhoff-xml-format.md))
2. Extract identity, PDO names, and data types
3. Add the terminal definition to the appropriate YAML file

## How Definitions Are Used

### ADS Simulator

The test simulator uses terminal definitions to:
- Build accurate symbol tables matching real TwinCAT behavior
- Return correct data types and sizes for symbol queries
- Simulate multi-channel terminals with proper naming

### FastCS Controller Generation

Terminal definitions generate FastCS controllers:
- Each symbol with `selected: true` becomes a FastCS attribute
- Channel templates expand to numbered attributes

### catio-terminals UI

The GUI displays:
- Symbols grouped by composite type when applicable
- Composite type members nested under parent symbols
- Runtime symbols in a separate section

## Related Documentation

- [ADS Symbols and CoE Objects](../reference/ads-symbols-and-coe.md) - Underlying Beckhoff concepts
- [EtherCAT Composite Types](../reference/ethercat-composite-types.md) - Type generation details
- [Beckhoff XML Format](../reference/beckhoff-xml-format.md) - ESI XML schema
- [Architecture Overview](architecture-overview.md) - Overall system design
