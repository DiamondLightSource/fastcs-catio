# FastCS EPICS IOC Implementation

This document explains how CATio uses the FastCS framework to expose EtherCAT devices as EPICS Process Variables (PVs), enabling control system integration.

## What is FastCS?

[FastCS](https://github.com/DiamondLightSource/FastCS) is a Python framework for building EPICS Input/Output Controllers (IOCs). It provides a declarative approach where Python class attributes automatically become EPICS PVs. CATio leverages FastCS to create a hierarchical controller structure that mirrors the physical EtherCAT topology.

Key benefits of using FastCS include:

- **Automatic PV generation**: Define Python attributes, get EPICS PVs
- **Asynchronous I/O**: Built on `asyncio` for non-blocking operations
- **Hierarchical controllers**: Natural mapping to nested hardware structures
- **Built-in scanning**: Periodic polling with configurable intervals

## The Controller Hierarchy

CATio organizes its FastCS controllers in a tree structure that reflects the physical EtherCAT network:

```
CATioServerController (root)
    └── CATioDeviceController (EtherCAT Master)
            ├── CATioTerminalController (EK1100 Coupler)
            │       ├── CATioTerminalController (EL3064 Analog Input)
            │       └── CATioTerminalController (EL2008 Digital Output)
            └── CATioTerminalController (EK1101 Coupler)
                    └── ...
```

This hierarchy is significant because:

1. **Each level corresponds to physical hardware**: The server represents the Beckhoff PLC, devices represent EtherCAT Masters, and terminals represent individual I/O modules
2. **Attributes are scoped appropriately**: Server-level attributes (like version info) are separate from terminal-level attributes (like input values)
3. **The tree is auto-generated**: CATio introspects the hardware and builds controllers dynamically

### The Base Controller

All CATio controllers inherit from `CATioController`, which extends the FastCS `Controller` class. The base class provides:

- A shared TCP connection to the TwinCAT server (class-level singleton)
- Unique identifiers for API dispatch
- References to corresponding hardware objects (`IOServer`, `IODevice`, or `IOSlave`)
- Attribute grouping for organized PV naming

```{literalinclude} ../../src/catio/catio_controller.py
:language: python
:start-at: class CATioController
:end-before: @property
```

### The Server Controller

`CATioServerController` is the root of the hierarchy. It handles:

- **Route establishment**: Uses UDP to register this client with the TwinCAT router
- **TCP connection**: Opens the persistent ADS communication channel
- **Hardware discovery**: Introspects the I/O server to find all devices and terminals
- **Subcontroller creation**: Instantiates the appropriate controller classes for discovered hardware

During initialization, the server controller queries the TwinCAT system and builds the complete controller tree automatically. The key method is `register_subcontrollers()` which traverses the discovered hardware tree and creates corresponding FastCS controllers.

### Device and Terminal Controllers

`CATioDeviceController` represents EtherCAT Master devices and exposes attributes like:

| Attribute | Description |
|-----------|-------------|
| `SlaveCount` | Number of terminals connected to this master |
| `SlavesStates` | Array of EtherCAT state machine values for all terminals |
| `SlavesCrcCounters` | CRC error counters for network diagnostics |
| `FrameCounters` | Statistics on cyclic and acyclic EtherCAT frames |

`CATioTerminalController` represents individual I/O modules (EK couplers, EL terminals) with attributes like:

| Attribute | Description |
|-----------|-------------|
| `EcatState` | The terminal's EtherCAT state machine value |
| `LinkStatus` | Network link health indicator |
| `CrcErrorSum` | Accumulated CRC errors for this terminal |

## Hardware-Specific Controllers

Not all terminals are alike. A digital input module exposes different data than an analog output module. CATio handles this through specialized controller classes defined in [catio_hardware.py](../../src/catio/catio_hardware.py).

The `SUPPORTED_CONTROLLERS` dictionary maps Beckhoff terminal type codes to their controller classes. When CATio discovers a terminal, it looks up the type (e.g., "EL3064") in this dictionary and instantiates the appropriate controller.

Each terminal type exposes its specific attributes:

| Controller Family | Terminal Types | Key Attributes |
|-------------------|----------------|----------------|
| `EL10xxController` | EL1004, EL1008, etc. | Digital input values |
| `EL20xxController` | EL2004, EL2008, etc. | Digital output values (read/write) |
| `EL30xxController` | EL3064, EL3102, etc. | Analog input values, scaling info |
| `EL40xxController` | EL4002, EL4132, etc. | Analog output values, range config |
| `ELM3xxxController` | ELM3004, ELM3602, etc. | High-precision measurements, oversampling |

## The Attribute I/O System

FastCS attributes need to know how to read (and optionally write) their values. CATio implements this through `CATioControllerAttributeIO`, which bridges FastCS attributes to the ADS client API.

### How Attribute Updates Work

The update flow for a CATio attribute follows these steps:

1. FastCS calls the `update()` method on an attribute's I/O handler at the configured polling interval
2. The I/O handler constructs an API query string based on the attribute name and controller context
3. The query is sent through `CATioConnection` to the `AsyncioADSClient`
4. The client dispatches to the appropriate `get_*` method
5. The response flows back and the attribute value is updated

This indirection means attributes don't need to know ADS protocol details - they just specify their name and polling period.

```{literalinclude} ../../src/catio/catio_attribute_io.py
:language: python
:start-at: class CATioControllerAttributeIO
:end-before: class
```

### Polling vs Notifications

CATio supports two update mechanisms:

**Polling** (default): The I/O handler periodically queries the ADS server. Simple and reliable, but adds latency and network traffic proportional to the number of attributes and polling rate.

**Notifications**: The ADS server pushes value changes to the client. More efficient for high-frequency data, but requires subscription management and careful buffer handling.

The choice depends on the attribute's requirements:

| Update Mode | Use Case | Typical Period |
|-------------|----------|----------------|
| `ONCE` | Static configuration (device name, version) | Read at startup only |
| Standard polling | Slowly-changing diagnostics (CRC counters) | 1-2 seconds |
| Fast polling | Process values needing moderate rates | 100-500 ms |
| Notifications | High-frequency acquisition data | Sub-millisecond |

## PV Naming Convention

CATio generates EPICS PV names that reflect the hardware hierarchy:

```
<PREFIX>:<Server>:<Device>:<Coupler>:<Terminal>:<Attribute>
```

For example:

| PV Name | Description |
|---------|-------------|
| `CATIO:IOServer:Name` | I/O server name |
| `CATIO:IOServer:ETH1:SlaveCount` | Number of slaves on EtherCAT Master 1 |
| `CATIO:IOServer:ETH1:RIO1:MOD5:Value` | Value from module 5 on remote I/O node 1 |
| `CATIO:IOServer:ETH1:RIO1:MOD5:EcatState` | EtherCAT state of that module |

The naming components come from:

- **ecat_name**: The name configured in TwinCAT (e.g., "Device1", "Term 5 (EL3064)")
- **get_type_name()**: A method that converts Beckhoff names to PV-friendly format (e.g., "ETH1", "RIO1", "MOD5")

## Lifecycle Management

CATio controllers follow a specific lifecycle managed by FastCS:

### Initialization Phase

1. **Route addition**: UDP message registers this client with the TwinCAT router
2. **TCP connection**: Establishes persistent ADS communication channel
3. **Introspection**: Queries server for devices, terminals, and symbols
4. **Controller creation**: Builds the controller tree matching discovered hardware
5. **Attribute registration**: Creates FastCS attributes for each controller

### Runtime Phase

- Polling handlers execute at their configured intervals
- Notification streams are processed and distributed to attributes
- The controller tree remains stable (hot-plugging is not supported)

### Shutdown Phase

1. **Notification cleanup**: Unsubscribes from all ADS notifications
2. **Connection closure**: Closes the TCP connection gracefully
3. **Route removal**: Optionally removes the route from TwinCAT

## Testing Considerations

When writing tests for CATio controllers, you typically need to mock the ADS client layer. The `MockADSServer` class in the test suite simulates TwinCAT responses:

```{literalinclude} ../../tests/mock_server.py
:language: python
:pyobject: MockADSServer
:end-before: async def start
```

This allows testing controller logic without real hardware by:

- Simulating ADS command responses
- Providing mock symbol data
- Testing notification handling

## See Also

- [Architecture Overview](architecture-overview.md) - High-level system architecture
- [ADS Client Implementation](ads-client.md) - Details of the ADS protocol layer
- [API Decoupling Analysis](api-decoupling.md) - Discussion of the API design
