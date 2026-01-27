# Terminal YAML Definitions

This document explains how to define Beckhoff EtherCAT terminals in YAML for use with the ADS simulator and FastCS controller generation.

These YAML files can be created and edited using the `catio-terminals` GUI tool (see [Using catio-terminals](#using-catio-terminals) below).

For background on the underlying Beckhoff technologies, see:
- [ADS Symbols and CoE Objects](../reference/ads-symbols-and-coe.md) - What symbols and CoE objects are
- [EtherCAT Composite Types](../reference/ethercat-composite-types.md) - How the EtherCAT Master generates composite types

## Overview

Terminal definitions are YAML files that describe:
- **Terminal identity** - Vendor ID, product code, revision
- **Symbol nodes** - Process data (I/O values) accessible via ADS
- **Composite types** - Structured types that group primitive fields
- **CoE objects** - Configuration parameters (optional)
- **Runtime symbols** - Diagnostic symbols added by the EtherCAT master

## File Organization

Terminal definitions live in `src/catio_terminals/terminals/`, organized by function:

| File | Terminal Types |
|------|----------------|
| `analog_input.yaml` | EL3004, EL3104, EL3602, etc. |
| `analog_output.yaml` | EL4004, EL4134, etc. |
| `digital_input.yaml` | EL1004, EL1014, EL1084, etc. |
| `digital_output.yaml` | EL2004, EL2024, EL2809, etc. |
| `counter.yaml` | EL1502, EL5101, etc. |
| `bus_couplers.yaml` | EK1100, EK1110, etc. |
| `power_supply.yaml` | EL9410, EL9512, etc. |

Supporting configuration files in `src/catio_terminals/config/`:

| File | Purpose |
|------|---------|
| `composite_types.yaml` | Composite type definitions (BIGTYPE structures) |
| `runtime_symbols.yaml` | EtherCAT master diagnostic symbols |

## Terminal Definition Structure

### Basic Example

```yaml
terminal_types:
  EL3104:
    description: "4-channel Analog Input +/-10V 16-bit"
    identity:
      vendor_id: 2
      product_code: 203227218
      revision_number: 1048576
    group_type: AnaIn
    symbol_nodes:
      - name_template: "AI Standard Channel {channel}"
        index_group: 61472
        type_name: "AI Standard Channel 1_TYPE"
        channels: 4
        access: Read-only
        fastcs_name: "AiStandardChannel{channel}"
    coe_objects: []
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
  - name_template: "AI Standard Channel {channel}"
    index_group: 61472       # 0xF020 - input data
    type_name: "AI Standard Channel 1_TYPE"
    channels: 4
    access: Read-only
    fastcs_name: "AiStandardChannel{channel}"
```

| Field | Description |
|-------|-------------|
| `name_template` | Symbol name pattern. Use `{channel}` for multi-channel terminals |
| `index_group` | ADS index group (see table below) |
| `type_name` | Data type - primitive (INT, BOOL) or composite type name |
| `channels` | Number of channels using this pattern |
| `access` | `Read-only` (inputs) or `Read/Write` (outputs) |
| `fastcs_name` | PascalCase name for FastCS attributes |

**ADS Index Groups:**

| Value | Hex | Purpose |
|-------|-----|---------|
| 61472 | 0xF020 | Input bytes (TxPDO - terminal to controller) |
| 61473 | 0xF021 | Input bits and diagnostics |
| 61488 | 0xF030 | Output bytes (RxPDO - controller to terminal) |
| 61489 | 0xF031 | Output bits |

### Computed Properties

The `size` and `ads_type` fields are computed from `type_name`:

```yaml
# You write:
- name_template: "Value {channel}"
  type_name: INT

# The system computes:
#   size: 2 (bytes)
#   ads_type: 2 (ADS type code for INT)
```

Type mappings are defined in `src/catio_terminals/ads_types.py`.

## Composite Types

When a symbol's `type_name` references a composite type (like `"AI Standard Channel 1_TYPE"`), the system looks it up in `composite_types.yaml`.

### Why Composite Types?

Beckhoff's ESI XML defines PDO entries as individual primitives, but TwinCAT groups them into composite types at runtime. For example:

**XML defines:**
- `Status__Underrange` (BOOL)
- `Status__Overrange` (BOOL)
- `Value` (INT)

**TwinCAT groups as:**
- `AI Standard Channel 1` with type `AI Standard Channel 1_TYPE` (4 bytes total)

We define these groupings in `composite_types.yaml` so the simulator can return accurate type information.

### Composite Type Definition

```yaml
# src/catio_terminals/config/composite_types.yaml

composite_types:
  "AI Standard Channel 1_TYPE":
    description: "16-bit analog input channel (status + value)"
    ads_type: 65  # BIGTYPE
    size: 4
    members:
      - name: Status
        offset: 0
        type_name: UINT
        size: 2
        fastcs_attr: Status
        access: read-only
      - name: Value
        offset: 2
        type_name: INT
        size: 2
        fastcs_attr: Value
        access: read-only
```

| Field | Description |
|-------|-------------|
| `description` | Human-readable description |
| `ads_type` | Always 65 for composite types (BIGTYPE) |
| `size` | Total size in bytes |
| `members` | List of member fields |

**Member fields:**

| Field | Description |
|-------|-------------|
| `name` | Member name |
| `offset` | Byte offset within the structure |
| `type_name` | Primitive type (UINT, INT, DINT, etc.) |
| `size` | Size in bytes |
| `fastcs_attr` | FastCS attribute name |
| `access` | `read-only` or `read-write` |

### Common Composite Types

| Type Name | Used By | Size | Members |
|-----------|---------|------|---------|
| `AI Standard Channel 1_TYPE` | EL3004, EL3104, etc. | 4 | Status + Value (16-bit) |
| `AI Inputs Channel 1_TYPE` | EL3602, EL3612 | 6 | Status + Value (32-bit) |
| `AO Output Channel 1_TYPE` | EL4002, EL4004 | 2 | AnalogOutput |
| `CNT Inputs_TYPE` | EL1502 | 6 | Status + CounterValue |
| `Inputs_TYPE` | EL1004, EL1008 | 1 | Packed digital inputs |

See [EtherCAT Composite Types](../reference/ethercat-composite-types.md) for the full list.

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
catio-terminals                    # Create new file
catio-terminals terminals.yaml     # Edit existing file
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
3. Check if symbols use existing composite types
4. If needed, add new composite types to `composite_types.yaml`
5. Add the terminal definition to the appropriate YAML file

### Adding a New Composite Type

If the terminal uses a composite type not yet defined:

1. Look at the PDO structure in the XML
2. Determine the TwinCAT type name (PDO name + `_TYPE`)
3. Add to `composite_types.yaml`:

```yaml
"New Type 1_TYPE":
  description: "Description of the type"
  ads_type: 65
  size: <total bytes>
  members:
    - name: <member1>
      offset: 0
      type_name: <primitive type>
      size: <bytes>
      fastcs_attr: <FastCS name>
      access: read-only
```

## How Definitions Are Used

### ADS Simulator

The test simulator uses terminal definitions to:
- Build accurate symbol tables matching real TwinCAT behavior
- Return correct data types and sizes for symbol queries
- Simulate multi-channel terminals with proper naming

### FastCS Controller Generation

(Future) Terminal definitions will generate FastCS controllers:
- Each symbol becomes a FastCS attribute
- Composite type members become individual attributes
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
