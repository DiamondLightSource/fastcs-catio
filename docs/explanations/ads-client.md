# ADS Client Implementation

This document explains how CATio implements the Beckhoff ADS (Automation Device Specification) protocol to communicate with TwinCAT systems running on Beckhoff PLCs.

## What is ADS?

ADS is Beckhoff's proprietary protocol for communication with TwinCAT automation systems. It provides a standardized way to:

- Read and write PLC variables
- Query device information and state
- Subscribe to value change notifications
- Access EtherCAT diagnostic data

The protocol runs over TCP (port 48898) for reliable communication or UDP (port 48899) for route management. CATio implements a pure-Python ADS client using `asyncio` for non-blocking operations.

For the official specification, see the [Beckhoff ADS Documentation](https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html).

## Protocol Architecture

ADS messages are wrapped in AMS (Automation Message Specification) frames for transport:

```
┌───────────────────────────────────────────┐
│            ADS Commands                   │
│   (Read, Write, Notification, etc.)       │
├───────────────────────────────────────────┤
│            AMS Header                     │
│   (NetId, Port, CommandId, InvokeId)      │
├───────────────────────────────────────────┤
│          TCP/IP Transport                 │
│   (Port 48898 for unencrypted ADS)        │
└───────────────────────────────────────────┘
```

Key concepts:

- **AMS NetId**: A 6-byte address identifying a TwinCAT system (often derived from IP, e.g., `192.168.1.100.1.1`)
- **AMS Port**: Identifies the target service within TwinCAT (I/O server = 300, EtherCAT Master = 65535)
- **Invoke ID**: Correlates requests with responses for async operation
- **Index Group/Offset**: Addresses specific data within a service

## Establishing Communication

Before sending ADS commands, the client must establish a route with the TwinCAT router.

### Route Discovery and Registration

TwinCAT maintains a routing table of authorized clients. CATio uses UDP messages to:

1. **Discover the target's AMS NetId**: Query the TwinCAT system for its network identity
2. **Register this client**: Add an entry to the routing table with authentication credentials

```{literalinclude} ../../src/catio/client.py
:language: python
:start-at: class RemoteRoute
:end-before: def _get_route_info_as_bytes
```

The route registration includes:

| Parameter | Purpose |
|-----------|---------|
| `remote` | IP address of the TwinCAT system |
| `routename` | Human-readable name for this client |
| `hostnetid` | This client's AMS NetId |
| `username` | TwinCAT authentication user |
| `password` | TwinCAT authentication password |

:::{note}
Default TwinCAT credentials are typically `Administrator` / `1`. Production systems should use proper authentication.
:::

### TCP Connection

Once routed, CATio opens a persistent TCP connection for ADS communication:

```{literalinclude} ../../src/catio/client.py
:language: python
:start-at: @classmethod
:start-after: ### CLIENT CONNECTION
:end-before: async def close
```

The connection uses Python's `asyncio.open_connection()` for non-blocking I/O, returning stream reader/writer pairs for bidirectional communication.

## ADS Commands

CATio implements the core ADS command set:

| Command ID | Name | Purpose |
|------------|------|---------|
| 0x01 | `READDEVICEINFO` | Get device name and version |
| 0x02 | `READ` | Read data from index group/offset |
| 0x03 | `WRITE` | Write data to index group/offset |
| 0x04 | `READSTATE` | Get ADS and device state |
| 0x06 | `ADDDEVICENOTE` | Subscribe to value notifications |
| 0x07 | `DELETEDEVICENOTE` | Unsubscribe from notifications |
| 0x08 | `DEVICENOTE` | Notification data (server-initiated) |
| 0x09 | `READWRITE` | Combined read and write operation |

### Request/Response Pattern

ADS communication is asynchronous: the client sends a request and later receives a response matched by invoke ID. CATio handles this with `ResponseEvent` objects:

1. Send request with unique invoke ID
2. Create `ResponseEvent` and store in pending map
3. Background task receives response, looks up event by invoke ID
4. Event is set, awakening the waiting coroutine

This pattern allows multiple concurrent requests without blocking.

## I/O Server Introspection

When CATio connects, it introspects the TwinCAT I/O server to discover the hardware topology. This involves a series of ADS reads to gather:

### Server Information

- Device name, version, and build number
- Number of registered EtherCAT devices

### Device Discovery

For each EtherCAT device:
- Device ID, type, and name
- AMS NetId (for direct communication)
- CANopen identity (vendor, product, revision)
- Frame counters for diagnostic statistics
- Slave terminal count

### Terminal Discovery

For each slave terminal:
- EtherCAT address
- Terminal type and name (e.g., "EL3064")
- CANopen identity
- State machine and link status
- CRC error counters per port

This information populates the `IOServer`, `IODevice`, and `IOSlave` data structures that the FastCS layer uses to create controllers.

## Symbol Management

ADS symbols provide named access to PLC variables, avoiding hard-coded index group/offset values. CATio discovers available symbols and maps them for convenient access.

### The AdsSymbol Structure

```{literalinclude} ../../src/catio/devices.py
:language: python
:start-at: @dataclass
:start-after: # ===== EtherCAT OBJECTS
:end-before: @property
```

Symbols carry type information (`dtype`) allowing CATio to correctly interpret binary data. The `group` and `offset` fields are used in ADS read/write commands.

### Symbol-Based Access vs Direct Access

| Approach | Pros | Cons |
|----------|------|------|
| **Symbol-based** | Self-documenting, type-safe | Requires symbol upload, slight overhead |
| **Direct index** | Fastest possible access | Brittle if PLC changes, no type info |

CATio uses symbol-based access for maintainability, falling back to direct indexing only for standard EtherCAT registers that have fixed addresses.

## Notification System

For high-frequency data, polling is inefficient. ADS notifications let the server push value changes to the client.

### How Notifications Work

1. **Subscribe**: Client sends `ADDDEVICENOTE` with index group/offset, buffer size, and timing parameters
2. **Receive handle**: Server returns a notification handle for this subscription
3. **Receive updates**: Server sends `DEVICENOTE` messages when values change
4. **Unsubscribe**: Client sends `DELETEDEVICENOTE` with the handle

### Notification Parameters

| Parameter | Purpose |
|-----------|---------|
| `max_delay` | Maximum time (100ns units) before server sends accumulated changes |
| `cycle_time` | Minimum interval between notifications |
| `transmission_mode` | When to send (on change, cyclic, etc.) |

CATio typically uses `ADSTRANS_SERVERCYCLE` mode where the server sends data at regular intervals regardless of whether values changed.

### Buffering and Processing

Notifications can arrive faster than the application processes them. CATio uses a buffering strategy:

1. Background task accumulates notification data in a `bytearray`
2. Periodically (configurable flush period), the buffer contents are queued
3. The FastCS layer processes queued notifications and updates attributes

This decouples network I/O from application processing, preventing backpressure.

## The API Layer

CATio's ADS client exposes a clean API for the FastCS layer, abstracting protocol details behind method calls.

### Query and Command Dispatch

The client uses string-based dispatch to route API calls:

- `query("SYSTEM_TREE")` → calls `get_system_tree()`
- `command("DEVICE_STATE", ...)` → calls `set_device_state(...)`

This pattern, while flexible, has tradeoffs discussed in [API Decoupling Analysis](api-decoupling.md).

### Key API Methods

| Method | Purpose |
|--------|---------|
| `get_system_tree()` | Returns hierarchical view of I/O system |
| `get_io_from_map()` | Retrieves IOServer/IODevice/IOSlave by ID |
| `get_device_framecounters_attr()` | Frame statistics for an EtherCAT device |
| `get_device_slavesstates_attr()` | State array for all terminals on a device |
| `get_terminal_states_attr()` | State of a specific terminal |

## Error Handling

ADS operations can fail for various reasons. CATio defines error codes matching the TwinCAT specification:

| Error Code | Meaning |
|------------|---------|
| `0x700` | General device error |
| `0x701` | Service not supported |
| `0x702` | Invalid index group |
| `0x703` | Invalid index offset |
| `0x706` | Invalid data |
| `0x745` | No notification handle |

The client raises exceptions with meaningful messages when operations fail, allowing proper error recovery in the FastCS layer.

## Testing with MockADSServer

CATio includes a mock ADS server for testing without hardware:

```{literalinclude} ../../tests/mock_server.py
:language: python
:pyobject: MockADSServer
:end-before: async def start
```

The mock server:
- Accepts TCP connections on the standard ADS port
- Parses AMS headers and dispatches to command handlers
- Returns configurable mock responses
- Simulates notification subscriptions

This enables comprehensive testing of the client logic independent of real TwinCAT systems.

## See Also

- [Architecture Overview](architecture-overview.md) - High-level system architecture
- [FastCS EPICS IOC Implementation](fastcs-epics-ioc.md) - Details of the EPICS layer
- [API Decoupling Analysis](api-decoupling.md) - API design discussion
