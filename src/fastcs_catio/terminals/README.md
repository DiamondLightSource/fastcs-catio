# Terminal Type Definitions

This directory contains YAML definitions for Beckhoff EtherCAT I/O terminals organized by functional class.

## Files

- **bus_couplers.yaml** - EtherCAT couplers and extensions (EK1100, EK1110, EK1101)
- **digital_input.yaml** - Digital input terminals (EL1004, EL1014, EL1008, EL1018, EL1084, EL1809, EL1124)
- **digital_output.yaml** - Digital output terminals (EL2004, EL2008, EL2024, EL2809, EL2124)
- **counter.yaml** - Counter and frequency input terminals (EL1502)
- **analog_input.yaml** - Analog input terminals (EL3004, EL3064, EL3104, EL3124, EL3602, EL3702, ELM3704-0000)
- **analog_output.yaml** - Analog output terminals (EL4004, EL4034, EL4134)
- **power_supply.yaml** - Power supply and system terminals (EL9011, EL9100, EL9410, EL9512, EL9505)

## Usage

These terminal definitions are automatically loaded by:

1. **ADS Simulation Server** (`tests.ads_sim`) - Creates accurate symbol tables for testing
2. **FastCS Integration** (future) - Dynamic generation of FastCS controller classes

## Documentation

For detailed information about the terminal definition format, symbol node properties, and how to add new terminals, see:

**[Terminal Type Definitions Documentation](../../docs/explanations/terminal-definitions.md)**

## Format

Each YAML file contains a `terminal_types` dictionary with terminal type definitions:

```yaml
terminal_types:
  EL2024:
    description: "4-channel Digital Output 24V DC"
    identity:
      vendor_id: 2
      product_code: 0x07E83052
      revision_number: 0x00100000
    symbol_nodes:
      - name_template: "Channel {channel}^Output"
        index_group: 0xF031
        size: 0
        ads_type: 33
        type_name: "BIT"
        channels: 4
```

See the documentation link above for complete details on the structure and properties.
