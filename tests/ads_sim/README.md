# ADS Simulation Server

A standalone ADS protocol simulation server for testing `fastcs-catio` without
real hardware.

## Overview

This module provides a simulated EtherCAT chain with configurable devices and
slaves. It implements the ADS protocol (TCP port 48898, UDP port 48899) and
responds to the same messages that real Beckhoff hardware would.

## Comparison with real hardware

This simulator was built to closely mimic the behavior of real TwinCAT hardware on Greg's desk with 107 EtherCAT slices.

The following is Gemini 3 Pro's assessment of Claude Opus 4.5's work!:-

Comparison of the output files sim.out (ADS Simulator) and real.out (Real Hardware) shows that they are now **functionally identical** in terms of ADS symbol exposure and connection behavior.

The simulator `ads_sim` has been successfully aligned with the real TwinCAT hardware.

### Key Matches

1.  **Symbol Count**: Both systems now expose exactly **461 available symbols** from 377 table entries.
    *   *Sim Log:* `INFO: 377 entries in the symbol table returned a total of 461 available symbols.`
    *   *Real Log:* `INFO: 377 entries in the symbol table returned a total of 461 available symbols.`

2.  **Server Identity**: The simulated server name now matches the real hardware.
    *   Both report: `INFO: ADS device info: name=I/O Server, version=3-1, build=4024`

3.  **Hardware Tree**: The detected EtherCAT topology is identical in both logs, with the same number of slaves (105) and identical structure (Term 2 to Term 106).

4.  **Symbol Notifications**:
    *   The subscription sequence matches exactly.
    *   The cleanup sequence matches exactly (both delete 461 notification handles on shutdown).
    *   *Note:* The handle IDs (e.g., `1833` vs `2294`) differ, which is expected as these are dynamic runtime assignments.

5.  **Warnings/errors**: Both logs exhibit the same warnings regarding CAS (Channel Access Server) ports and an identical `asyncio.CancelledError` on shutdown, indicating the behavior is consistent even in edge cases.




## Usage

### Running the Server

```bash
# Run with default configuration
python -m tests.ads_sim

# Run with custom configuration
python -m tests.ads_sim --config /path/to/config.yaml

# Run on specific host/port
python -m tests.ads_sim --host 0.0.0.0 --port 48898
```

### Connecting with the Client

```python
import asyncio
from fastcs_catio.client import AsyncioADSClient

async def main():
    client = await AsyncioADSClient.connected_to(
        target_ip='127.0.0.1',
        target_ams_net_id='10.0.0.1.3.1',
        target_ams_port=300
    )

    # Introspect the I/O server
    await client.introspect_io_server()

    # Get symbols
    symbols = await client.get_all_symbols()

    await client.close()

asyncio.run(main())
```

## Configuration

The EtherCAT chain is configured via YAML. The default configuration is in
`erver_config_CX7000_cs2.yaml`, which defines the server settings and device instances.
Terminal type definitions are stored in separate YAML files in
`src/catio_terminals/terminals/`, organized by terminal class.

### Structure

Server configuration file (`erver_config_CX7000_cs2.yaml`):

```yaml
# Server information
server:
  name: "TwinCAT System"
  version: "3.1"
  build: 4024

# Device configuration
devices:
  - id: 1
    name: "Device 1 (EtherCAT)"
    type: 94
    netid: "10.0.0.1.3.1"
    slaves:
      - type: "EK1100"
        name: "Term 1 (EK1100)"
        node: 1
        position: 0
      - type: "EL2024"
        name: "Term 2 (EL2024)"
        node: 1
        position: 1
```

Terminal type definition files (`src/catio_terminals/terminals/*.yaml`):

```yaml
# Define terminal types and their symbols
terminal_types:
  EL2024:
    description: "4-channel Digital Output 24V DC"
    identity:
      vendor_id: 2
      product_code: 0x07E83052
      revision_number: 0x00100000
    symbol_nodes:
      - name_template: "Channel {channel}^Output"
        index_group: 0xF031  # ADSIGRP_IOIMAGE_RWOX
        size: 0
        ads_type: 33  # BIT
        type_name: "BIT"
        channels: 4
```

### Terminal Types

The following terminal types are supported:

| Type   | Description                     | Symbols |
|--------|---------------------------------|---------|
| EK1100 | EtherCAT Coupler               | None    |
| EK1110 | EtherCAT Extension             | None    |
| EL9410 | E-Bus Power Supply             | None    |
| EL1004 | 4-ch Digital Input 24V DC      | 2       |
| EL1014 | 4-ch Digital Input 24V DC      | 2       |
| EL1084 | 8-ch Digital Input 24V DC      | 2       |
| EL1502 | 2-ch Up/Down Counter 24V DC    | 5       |
| EL2024 | 4-ch Digital Output 24V DC     | 9       |

## Supported ADS Commands

The simulation server supports the following ADS commands:

- **Read Device Info** (0x01): Returns server name, version
- **Read State** (0x04): Returns ADS/device state
- **Read** (0x02): Read from index group/offset
- **Write** (0x03): Write to index group/offset
- **Read Write** (0x09): Combined read/write operation
- **Add Device Notification** (0x06): Register for value updates
- **Delete Device Notification** (0x07): Unregister notifications

### Index Groups

| Group  | Name                  | Purpose                       |
|--------|-----------------------|-------------------------------|
| 0xF000 | SYMTAB_INFO          | Symbol table metadata         |
| 0xF003 | IODevice             | Device operations             |
| 0xF00B | SUMREAD              | Batch read operations         |
| 0xF00F | SYMBOL_TABLE         | Symbol table data             |
| 0xF020 | RWIB                 | Input bytes (read/write)      |
| 0xF021 | RWIX                 | Input bits (read/write)       |
| 0xF030 | RWOB                 | Output bytes (read/write)     |
| 0xF031 | RWOX                 | Output bits (read/write)      |

## Architecture

```
tests/ads_sim/
├── __init__.py          # Package exports
├── __main__.py          # CLI entry point
├── ethercat_chain.py    # Chain configuration parser
├── erver_config_CX7000_cs2.yaml   # Default server/device configuration
├── server.py            # ADS protocol server
└── README.md            # This file

src/catio_terminals/terminals/
├── analog_input.yaml    # Analog input terminal types
├── analog_output.yaml   # Analog output terminal types
├── bus_couplers.yaml    # EtherCAT couplers and extensions
├── counter.yaml         # Counter/frequency input terminals
├── digital_input.yaml   # Digital input terminal types
├── digital_output.yaml  # Digital output terminal types
└── power_supply.yaml    # Power supply terminals
```

## Development

### Running Tests

```bash
# Run linting
uv run ruff check tests/ads_sim/

# Run type checking
uv run pyright tests/ads_sim/
```

### Adding New Terminal Types

1. Add the terminal type definition to the appropriate YAML file in
   `src/catio_terminals/terminals/` (or create a new one for a new class)
2. Define the `identity` (vendor_id, product_code, revision_number)
3. Define `symbol_nodes` with appropriate `type_name` values that match
   patterns in `src/fastcs_catio/symbols.py`
4. The new terminal type will be automatically loaded when the server starts
