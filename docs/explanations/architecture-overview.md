# CATio Architecture Overview

CATio is a Python-based control system integration for EtherCAT I/O devices running under Beckhoff TwinCAT. The architecture is deliberately designed with a clean separation between two halves:

1. **FastCS EPICS IOC Layer** - Exposes Process Variables (PVs) for controlling EtherCAT devices
2. **ADS Client Layer** - Communicates with TwinCAT ADS servers on Beckhoff PLCs

## High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          EPICS Clients / Control Systems                     │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Channel Access / PVAccess
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FastCS EPICS IOC Layer                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                       CATioServerController                            │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │  CATioDeviceController (EtherCAT Master)                         │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  CATioTerminalController (EK1100, EL3xxx, etc.)            │  │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Components: catio_controller.py, catio_hardware.py, catio_attribute_io.py   │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ CATioConnection API
                                        │ (CATioFastCSRequest/Response)
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            CATio API Bridge                                  │
│                                                                              │
│  CATioConnection  ─────►  CATioStreamConnection  ─────►  AsyncioADSClient    │
│                                                                              │
│  Components: catio_connection.py                                             │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ ADS Protocol (TCP/UDP)
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            ADS Client Layer                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  AsyncioADSClient                                                      │  │
│  │  • Route management (UDP)                                              │  │
│  │  • TCP connection handling                                             │  │
│  │  • AMS message send/receive                                            │  │
│  │  • I/O introspection                                                   │  │
│  │  • Symbol management                                                   │  │
│  │  • Notification subscriptions                                          │  │
│  │  • API query/command dispatch                                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Components: client.py, messages.py, devices.py, symbols.py                  │
└──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ ADS/AMS Protocol
                                        │ (TCP Port 48898, UDP Port 48899)
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       Beckhoff TwinCAT ADS Server                            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  I/O Server (Port 300)                                                 │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │  EtherCAT Master Device (Port 65535)                             │  │  │
│  │  │  ┌────────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  EtherCAT Slave Terminals (EK/EL modules)                  │  │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Overview

### FastCS EPICS IOC Layer

The top layer provides EPICS integration through the FastCS framework:

- **CATioServerController**: Root controller representing the I/O server; manages TCP connections and device discovery
- **CATioDeviceController**: Represents EtherCAT Master devices with their associated attributes
- **CATioTerminalController**: Represents individual EtherCAT slave terminals (couplers, I/O modules)
- **CATioControllerAttributeIO**: Handles attribute read/write operations through the API

### API Bridge Layer

The middle layer provides a clean interface between FastCS and the ADS client:

- **CATioConnection**: Singleton managing the TCP connection lifecycle
- **CATioStreamConnection**: Wraps the ADS client with async context management
- **CATioFastCSRequest/Response**: Request/response objects for API communication

### ADS Client Layer

The bottom layer implements the TwinCAT ADS protocol:

- **AsyncioADSClient**: Asynchronous ADS client handling all protocol communication
- **RemoteRoute**: UDP-based route management for network discovery
- **Message classes**: Structured ADS message types for various commands
- **Device/Symbol models**: Data classes representing EtherCAT hardware and ADS symbols

## Data Flow

### Initialization Flow

1. **Route Discovery**: UDP communication discovers the remote TwinCAT server's AMS NetId
2. **Route Addition**: Client machine is added to the TwinCAT server's routing table
3. **TCP Connection**: Establish persistent TCP connection for ADS communication
4. **I/O Introspection**: Query server for devices, slaves, and symbol information
5. **Controller Creation**: Build FastCS controller hierarchy matching hardware topology
6. **Attribute Registration**: Create EPICS PVs for each accessible parameter

### Runtime Data Flow

```
EPICS Client Request
        │
        ▼
FastCS Attribute Access
        │
        ▼
CATioControllerAttributeIO.update()
        │
        ▼
CATioConnection.send_query()
        │
        ▼
AsyncioADSClient.query() / command()
        │
        ▼
API method dispatch (get_* / set_*)
        │
        ▼
ADS Read/Write/ReadWrite commands
        │
        ▼
TwinCAT Server Response
        │
        ▼
Response propagation back to EPICS
```

## Key Design Decisions

### Asynchronous Architecture

The entire stack uses Python's `asyncio` for non-blocking I/O operations:

- Enables concurrent handling of multiple PV requests
- Supports continuous notification monitoring without blocking
- Allows efficient polling of device states

### Controller Hierarchy

Controllers form a tree structure mirroring the physical EtherCAT topology:

```
IOServer
└── IODevice (EtherCAT Master)
    ├── IOSlave (EK1100 Coupler)
    │   ├── IOSlave (EL3xxx Input)
    │   └── IOSlave (EL4xxx Output)
    └── IOSlave (EK1101 Coupler)
        └── ...
```

### Symbol-Based Access

ADS symbols provide named access to device parameters rather than raw memory addresses:

- Symbols discovered during introspection
- Notification subscriptions for efficient updates
- Type information preserved for proper data conversion

## Configuration

CATio is configured through command-line parameters:

- **target_ip**: IP address of the Beckhoff PLC
- **target_port**: AMS port for the I/O device (typically 851 for TwinCAT)
- **poll_period**: Interval for standard attribute polling
- **notification_period**: Interval for processing ADS notifications

## See Also

- [FastCS EPICS IOC Implementation](fastcs-epics-ioc.md) - Detailed explanation of the EPICS layer
- [ADS Client Implementation](ads-client.md) - Detailed explanation of the ADS protocol layer
- [API Decoupling Analysis](api-decoupling.md) - Discussion of the API design and potential improvements
