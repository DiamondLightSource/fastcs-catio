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
catio-terminals --update-cache

# Launch editor
catio-terminals path/to/terminals.yaml
```
