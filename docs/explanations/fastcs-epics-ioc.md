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
└── EtherCATMasterController (EtherCAT Master device)
    ├── Dynamic EK1100 controller (Coupler, hoisted to server if single-segment path)
    │   ├── Dynamic EL3064 controller (Analog Input)
    │   └── Dynamic EL2008 controller (Digital Output)
    └── Dynamic EK1101 controller (Coupler)
        └── ...
```

This hierarchy is significant because:

1. **Each level corresponds to physical hardware**: The server represents the Beckhoff PLC, devices represent EtherCAT Masters, and terminals represent individual I/O modules
2. **Attributes are scoped appropriately**: Server-level attributes (like version info) are separate from terminal-level attributes (like input values)
3. **The tree is auto-generated**: CATio introspects the hardware and builds controllers dynamically
4. **Couplers with top-level paths are hoisted**: When a coupler or box resolves to a single-segment PV path (e.g., `BL04I-EA-E1RIO-01`), it is registered directly under the server rather than nested under the device, enabling PVI to render it as a top-level screen

### The Base Controller

All CATio controllers inherit from `CATioController`, which extends the FastCS `Controller` class. The base class provides:

- A shared TCP connection to the TwinCAT server (class-level singleton `_tcp_connection`)
- Unique integer identifiers for API dispatch (class-level counter `_identifier`)
- References to corresponding hardware objects (`IOServer`, `IODevice`, or `IOSlave`)
- Attribute grouping for organized PV naming

Each controller instance registers three IO handler objects that route attribute reads and writes to the appropriate ADS mechanism:

| IO class | Purpose |
|----------|---------|
| `CATioControllerAttributeIO` | Standard polled controller attributes (device/terminal metadata) |
| `CATioControllerSymbolAttributeIO` | PDO symbol attributes from ADS symbol read/write |
| `CATioControllerCoEAttributeIO` | CoE configuration parameter attributes |

The `CATioController` class is defined in [catio_controller.py](../../src/fastcs_catio/catio_controller.py). It includes connection management, attribute registration, and the core interface for communicating with the ADS client.

### The Server Controller

`CATioServerController` is the root of the hierarchy. It handles:

- **Route establishment**: Uses UDP to register this client with the TwinCAT router
- **TCP connection**: Opens the persistent ADS communication channel
- **Hardware discovery**: Introspects the I/O server to find all devices and terminals
- **Subcontroller creation**: Instantiates the appropriate controller classes for discovered hardware

All server settings are packaged in a `CATioServerControllerOptions` dataclass, which groups:

| Sub-dataclass | Purpose |
|---------------|---------|
| `CATioTCPSettings` | Target IP and port for the TwinCAT server |
| `CATioRouteSettings` | UDP route credentials (user name, password) |
| `CATioScanTimings` | Polling and notification update periods |
| `CATioNameMappings` | PV name templates for device, node, and module controllers |

During initialization, the server controller queries the TwinCAT system and builds the complete controller tree automatically. The key method is `register_subcontrollers()` which traverses the discovered hardware tree and calls `get_subcontrollers_from_node()` recursively to create corresponding FastCS controllers. Couplers and boxes whose resolved path consists of a single segment are *hoisted* from the device level up to the server level, so PVI can render them inline on the top-level screen.

### Device and Terminal Controllers

The concrete device controller for an EtherCAT master is `EtherCATMasterController` (a `CATioDeviceController` subclass defined in [catio_hardware.py](../../src/fastcs_catio/catio_hardware.py)). The set of supported device types is stored in `SUPPORTED_DEVICE_CONTROLLERS`. `CATioDeviceController` exposes attributes including:

| Attribute | Description |
|-----------|-------------|
| `SlaveCount` | Number of terminals connected to this master |
| `SlavesStates` | Array of EtherCAT state machine values for all terminals |
| `SlavesCrcCounters` | CRC error counters for network diagnostics |
| `NodeCount` | Number of EtherCAT nodes registered on the device |
| `SystemTime` | EtherCAT frame timestamp |
| `SentCyclicFrames` | Count of sent cyclic EtherCAT frames |
| `LostCyclicFrames` | Count of lost cyclic EtherCAT frames |
| `SentAcyclicFrames` | Count of sent acyclic EtherCAT frames |
| `LostAcyclicFrames` | Count of lost acyclic EtherCAT frames |

`EtherCATMasterController` adds further notification-stream attributes (`InFrm0State`, `InFrm0WcState`, `InFrm0InpToggle`, `OutFrm0Ctrl`, `OutFrm0WcCtrl`, `InputsDevState`, `OutputsDevCtrl`, `InputsSlaveCount`) that are updated via ADS notifications rather than polling.

`CATioTerminalController` represents individual I/O modules (EK couplers, EL terminals) with attributes including:

| Attribute | Description |
|-----------|-------------|
| `StateMachine` | The terminal's EtherCAT state machine value |
| `LinkStatus` | Network link health indicator |
| `CrcErrorSum` | Accumulated CRC errors (sum across all ports) |
| `CrcErrorPortA/B/C/D` | Per-port CRC error counters |
| `Node` | Chain node index for this terminal |
| `Position` | Chain position index for this terminal |
| `Address` | EtherCAT address |

## Dynamic Terminal Controllers

Not all terminals are alike. A digital input module exposes different data than an analog output module. CATio handles this through dynamically generated controller classes based on YAML terminal definitions.

### How Dynamic Generation Works

When CATio discovers a terminal, it calls `get_terminal_controller_class(terminal_id)` from `catio_dynamic_controller.py`. This factory function:

1. Looks up the terminal type (e.g., "EL3064") across all YAML files in `src/catio_terminals/terminals/`
2. Creates a controller class dynamically based on the YAML definition (`DynamicEL3064Controller`, etc.)
3. Adds runtime symbol attributes (e.g., `WcState`, `InfoData`) applicable to this terminal type
4. Adds PDO symbol attributes for process data (from `catio_dynamic_symbol.py`)
5. Adds CoE attributes for configuration parameters (from `catio_dynamic_coe.py`)
6. Caches the class for reuse across multiple instances of the same terminal type

The key modules involved:

| Module | Purpose |
|--------|---------|
| `catio_dynamic_controller.py` | Factory function and dynamic class creation |
| `catio_dynamic_symbol.py` | Adds PDO symbol attributes to controllers |
| `catio_dynamic_coe.py` | Adds CoE parameter attributes to controllers |
| `catio_dynamic_types.py` | Type conversion between TwinCAT, numpy, and FastCS |

### Terminal YAML Definitions

Each terminal type is defined in `src/catio_terminals/terminals/terminal_types.yaml` (the terminal config loader supports multiple YAML files via glob patterns) with:

- **Symbol nodes**: Process data accessible via ADS (inputs/outputs)
- **CoE objects**: Configuration parameters with subindices
- **Selection**: Only symbols with `selected: true` become attributes

For example, a digital input terminal might expose:

| Attribute Type | Source | Examples |
|----------------|--------|----------|
| Runtime symbols | `runtime_symbols.yaml` | WcState, InfoData |
| PDO symbols | `symbol_nodes` in YAML | Input values, status bits |
| CoE parameters | `coe_objects` in YAML | Filter settings, calibration |

This approach allows adding new terminal types by editing YAML files without changing Python code. See [Terminal YAML Definitions](terminal-yaml-definitions.md) for details on the YAML format.

## The Attribute I/O System

FastCS attributes need to know how to read (and optionally write) their values. CATio implements this through three IO classes in [catio_attribute_io.py](../../src/fastcs_catio/catio_attribute_io.py):

| Class | Ref class | Used for |
|-------|-----------|----------|
| `CATioControllerAttributeIO` | `CATioControllerAttributeIORef` | Standard polled controller attributes (metadata, counters) |
| `CATioControllerSymbolAttributeIO` | `CATioControllerSymbolAttributeIORef` | PDO symbol read/write via ADS symbol names |
| `CATioControllerCoEAttributeIO` | `CATioControllerCoEAttributeIORef` | CoE configuration parameters read/write |

All three are registered with every controller instance in `CATioController.__init__`, and FastCS dispatches each attribute's update or send call to the appropriate IO object based on the `io_ref` type.

### How Attribute Updates Work

The update flow for a standard polled attribute follows these steps:

1. FastCS calls the `update()` method on an attribute's IO handler at the configured polling interval
2. The IO handler constructs an API query string based on the attribute name and controller context
3. The query is sent through `CATioConnection` to the `AsyncioADSClient`
4. The client dispatches to the appropriate `get_*` method
5. The response flows back and the attribute value is updated

For symbol attributes, the `CATioControllerSymbolAttributeIO` handler looks up the ADS symbol name via `ads_name_map` on the controller, then issues a `SYMBOL_PARAM` request to read or write the value directly by symbol name.

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

CATio generates EPICS PV names that reflect the hardware hierarchy. The naming is configured via `CATioNameMappings` (part of `CATioServerControllerOptions`) using three Python `str.format`-style templates:

| Template field | Default | Controls |
|----------------|---------|---------|
| `device_prefix` | `ETH{}` | EtherCAT master devices |
| `node_prefix` | `E1RIO{}` | EtherCAT couplers/boxes |
| `module_prefix` | `MOD{}` | Individual I/O terminals |

Templates may use `{}` or `{n}` for the numeric index, `{id}` for the IOC root prefix, `{device_prefix}` (inside `node_prefix` and `module_prefix`), and `{node_prefix}` (inside `module_prefix`). Rendered results are split on `:` to produce multi-segment controller paths.

In the shipped `fastcs.yaml` the site configuration is:

```yaml
name_mappings:
  device_prefix: "{id}:ETH{:02d}"
  node_prefix: "BL04I-EA-E1RIO-{:02d}"
  module_prefix: "{node_prefix}:MOD{:02d}"
```

With `id: BL04I-EA-CATIO-01`, this produces PV names like:

| PV Name | Description |
|---------|-------------|
| `BL04I-EA-CATIO-01:Name` | I/O server name |
| `BL04I-EA-CATIO-01:ETH01:SlaveCount` | Number of slaves on EtherCAT Master 1 |
| `BL04I-EA-E1RIO-01:MOD05:Value` | Value from module 5 on remote I/O node 1 |
| `BL04I-EA-E1RIO-01:MOD05:StateMachine` | EtherCAT state of that module |

Since `node_prefix` here does not include `{device_prefix}`, node controllers resolve to a single path segment (e.g., `BL04I-EA-E1RIO-01`) and are hoisted directly under the server controller.

## Lifecycle Management

CATio controllers follow a specific lifecycle managed by FastCS:

### Initialization Phase

1. **Route addition**: UDP message registers this client with the TwinCAT router
2. **TCP connection**: Establishes persistent ADS communication channel via `create_tcp_connection()`
3. **Introspection**: Queries server for devices, terminals, and symbols via `CATioConnection.initialise()`
4. **Controller creation**: `register_subcontrollers()` traverses the hardware tree and calls `get_subcontrollers_from_node()` recursively
5. **Attribute registration**: Each subcontroller's `initialise()` creates FastCS attributes
6. **Attribute map**: `get_complete_attribute_map()` builds a flat map of all PV keys, used to gate notification subscriptions

### Runtime Phase

- Polling handlers execute at their configured intervals (default `poll_period: 1.0` seconds)
- Notification streams are processed via the `@scan(NOTIFICATION_UPDATE_PERIOD)` method on the server controller (default every 0.2 seconds)
- Subscriptions are gated to only the attributes present in the attribute map — symbols unused by any PV are not subscribed to
- The controller tree remains stable (hot-plugging is not supported)

### Shutdown Phase

1. **Notification cleanup**: Disables notification monitoring and clears the cached stream
2. **Connection closure**: Closes the TCP connection gracefully via `CATioConnection.close()`
3. **Route removal**: Currently disabled in code (route deletion is commented out)

## Testing Considerations

When writing tests for CATio controllers, you typically need to mock the ADS client layer. The `MockADSServer` class in [mock_server.py](../../tests/mock_server.py) simulates TwinCAT responses.

This allows testing controller logic without real hardware by:

- Simulating ADS command responses
- Providing mock symbol data
- Testing notification handling

## See Also

- [Architecture Overview](architecture-overview.md) - High-level system architecture
- [ADS Client Implementation](ads-client.md) - Details of the ADS protocol layer
- [API Decoupling Analysis](decisions/0003-api-decoupling-analysis.md) - API design discussion
