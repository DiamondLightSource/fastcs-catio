# CATio Architecture Overview

CATio is a Python-based control system integration for EtherCAT I/O devices running under Beckhoff TwinCAT. The architecture is deliberately designed with a clean separation between two halves:

1. **FastCS EPICS IOC Layer** - Exposes Process Variables (PVs) for controlling EtherCAT devices
2. **ADS Client Layer** - Communicates with TwinCAT ADS servers on Beckhoff PLCs

## High-Level Architecture Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '14px'}}}%%
flowchart TB
    clients["EPICS Clients / Control Systems"]

    subgraph fastcs["FastCS EPICS IOC Layer"]
        direction LR
        server["CATioServerController"] --> device["CATioDeviceController<br/>(EtherCAT Master)"] --> terminal["CATioTerminalController<br/>(EK1100, EL3xxx, etc.)"]
        fastcs_files["catio_controller.py<br/>catio_hardware.py<br/>catio_attribute_io.py"]
    end

    subgraph bridge["CATio API Bridge"]
        direction LR
        conn["CATioConnection"] --> stream["CATioStreamConnection"] --> adsbridge["AsyncioADSClient"]
        bridge_files["catio_connection.py"]
    end

    subgraph adslayer["ADS Client Layer"]
        direction LR
        adsclient["AsyncioADSClient<br/>Route management (UDP)<br/>TCP connection handling<br/>AMS message send/receive<br/>I/O introspection<br/>Symbol management<br/>Notification subscriptions<br/>API query/command dispatch"]
        ads_files["client.py, messages.py<br/>devices.py, symbols.py"]
    end

    subgraph twincat["TwinCAT ADS Server"]
        direction LR
        ioserver["I/O Server<br/>(Port 300)"] --> master["EtherCAT Master<br/>(Port 65535)"] --> slaves["EtherCAT Slaves<br/>(EK/EL modules)"]
    end

    clients -->|"Channel Access / PVAccess"| fastcs
    fastcs -->|"CATioConnection API<br/>(CATioFastCSRequest/Response)"| bridge
    bridge -->|"ADS Protocol (TCP/UDP)"| adslayer
    adslayer -->|"ADS/AMS Protocol<br/>(TCP 48898, UDP 48899)"| twincat
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

```mermaid
flowchart TB
    A["EPICS Client Request"] --> B["FastCS Attribute Access"]
    B --> C["CATioControllerAttributeIO.update()"]
    C --> D["CATioConnection.send_query()"]
    D --> E["AsyncioADSClient.query() / command()"]
    E --> F["API method dispatch (get_* / set_*)"]
    F --> G["ADS Read/Write/ReadWrite commands"]
    G --> H["TwinCAT Server Response"]
    H --> I["Response propagation back to EPICS"]
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
