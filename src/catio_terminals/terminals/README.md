# Terminal Definition Files

This directory contains YAML files that define Beckhoff EtherCAT terminal types for use with the fastcs-catio project.

## Documentation

For complete documentation on terminal definitions, including:

- How to generate and edit terminal files using `catio-terminals`
- YAML file structure and properties
- ADS runtime symbols vs XML definitions
- Adding new terminal types

See the main documentation: [Terminal Type Definitions](../../../docs/explanations/terminal-definitions.md)

## Quick Reference

### File Organization

| File | Terminal Types |
|------|----------------|
| `bus_couplers.yaml` | EK1100, EK1110, etc. |
| `digital_input.yaml` | EL1004, EL1014, EL1084, etc. |
| `digital_output.yaml` | EL2004, EL2024, EL2809, etc. |
| `counter.yaml` | EL1502, etc. |
| `analog_input.yaml` | EL3004, EL3104, EL3602, etc. |
| `analog_output.yaml` | EL4004, EL4134, etc. |
| `power_supply.yaml` | EL9410, EL9512, etc. |

### Editing Terminal Files

Use the `catio-terminals` GUI editor:

```bash
# Update XML cache first
catio-terminals update-cache

# Launch editor with a file
catio-terminals edit path/to/terminals.yaml

# Or launch without a file and use Open/Create New
catio-terminals
```

---

# Architecture: Composite Types

## Overview

Terminal YAML files reference **composite types** by their TwinCAT type name (e.g., `"AI Standard Channel 1_TYPE"`). The actual member breakdown is defined in a shared file:

```
src/catio_terminals/config/composite_types.yaml
```

## How It Works

### Terminal YAML (simple reference)

```yaml
terminal_types:
  EL3104:
    description: 4-channel Analog Input +/-10V 16-bit
    identity:
      vendor_id: 2
      product_code: 0x0C203052
      revision_number: 0x00100000
    symbol_nodes:
      - name_template: "AI Standard Channel {channel}"
        index_group: 0xF030
        type_name: "AI Standard Channel 1_TYPE"  # References composite_types.yaml
        channels: 4
```

### composite_types.yaml (shared definitions)

```yaml
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

## Benefits

1. **DRY** - `AI Standard Channel 1_TYPE` defined once, used by EL3004, EL3064, EL3104, EL3124
2. **Simulator accuracy** - Uses exact TwinCAT type name for symbol table responses
3. **FastCS generation** - Looks up member breakdown to generate controller attributes
4. **Simple primitives** - Types like `BIT`, `UINT` not in composite_types are treated as simple 1:1 symbols

## Type Resolution

When processing a symbol_node:

1. If `type_name` exists in `composite_types.yaml` ??? it's a composite type with members
2. Otherwise ??? it's a primitive type (BIT, BOOL, INT, UINT, etc.) mapping 1:1 to an ADS symbol

## Use Cases

| Consumer | Uses |
|----------|------|
| **Simulator** | `type_name` for symbol table, `size` for data allocation |
| **FastCS Generator** | `members` list to create controller attributes with correct dtypes and offsets |
| **Validation** | `ads_type`, `size` to verify consistency |
