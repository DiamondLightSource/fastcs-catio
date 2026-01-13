# FastCS EPICS IOC Implementation

This document provides a detailed explanation of the FastCS EPICS IOC layer in CATio, which exposes Process Variables (PVs) for controlling EtherCAT devices on an Ethercat Bus.

## Overview

CATio uses [FastCS](https://github.com/DiamondLightSource/FastCS) as the framework for building an EPICS IOC. FastCS provides:

- Automatic PV generation from Python class attributes
- Asynchronous I/O handling
- Structured controller hierarchies
- Built-in support for polling and scanning

## Controller Hierarchy

### CATioController (Base Class)

The `CATioController` class ([catio_controller.py](../../src/catio/catio_controller.py)) serves as the base for all CATio controllers:

```python
class CATioController(Controller, Tracer):
    """
    A controller for an ADS-based EtherCAT system.
    """
    _tcp_connection: CATioConnection = CATioConnection()
    
    def __init__(
        self,
        name: str = "UNKNOWN",
        ecat_name: str = "",
        description: str | None = None,
        group: str = "",
    ):
        self._identifier: int = next(CATioController._ctrl_obj)
        self._io: IOServer | IODevice | IOSlave | None = None
        self.name: str = name
        self.ecat_name = ecat_name
        ...
```

Key features:

- **Shared TCP Connection**: All controllers share a single `CATioConnection` instance (class variable)
- **Unique Identifier**: Each controller gets a unique numeric ID for API dispatch
- **I/O Reference**: Each controller references its corresponding hardware object (IOServer, IODevice, or IOSlave)
- **Attribute Groups**: Controllers organize attributes by functional groups

### CATioServerController

The root controller representing the TwinCAT I/O server:

```python
class CATioServerController(CATioController):
    def __init__(
        self,
        target_ip: str,
        route: RemoteRoute,
        target_port: int,
        poll_period: float,
        notification_period: float,
    ) -> None:
        # Get remote target netid via UDP
        target_netid = get_remote_address(target_ip)
        
        # Add communication route
        if not route.add():
            raise ConnectionRefusedError("Remote route addition failed.")
        
        # Define TCP connection settings
        self._tcp_settings = CATioServerConnectionSettings(
            target_ip, target_netid.to_string(), target_port
        )
        ...
```

Responsibilities:

- **Connection Management**: Establishes UDP route and TCP connection to TwinCAT
- **Device Discovery**: Introspects the I/O server to discover EtherCAT devices
- **Controller Registration**: Creates and registers subcontrollers for devices and terminals
- **Notification Management**: Controls the notification monitoring lifecycle

### CATioDeviceController

Represents an EtherCAT Master device:

```python
class CATioDeviceController(CATioController):
    io_function: str = "Generic I/O device on the EtherCAT system"

    async def get_io_attributes(self) -> None:
        """Create device-specific FastCS attributes."""
        await self.get_generic_attributes()
        
        # Device-specific attributes
        self.add_attribute("SlaveCount", AttrR(datatype=Int(), ...))
        self.add_attribute("SlavesStates", AttrR(datatype=Waveform(Int()), ...))
        self.add_attribute("SlavesCrcCounters", AttrR(datatype=Waveform(Int()), ...))
        ...
```

Key attributes exposed:

- `SlaveCount`: Number of slave terminals on the device
- `SlavesStates`: Array of EtherCAT states for all slaves
- `SlavesCrcCounters`: CRC error counters for diagnostics
- `FrameCounters`: Cyclic/acyclic frame statistics

### CATioTerminalController

Represents individual EtherCAT slave terminals:

```python
class CATioTerminalController(CATioController):
    io_function: str = "Generic terminal on an EtherCAT device"

    async def get_io_attributes(self) -> None:
        """Create terminal-specific FastCS attributes."""
        await self.get_generic_attributes()
        
        self.add_attribute("EcatState", AttrR(datatype=Int(), ...))
        self.add_attribute("LinkStatus", AttrR(datatype=Int(), ...))
        self.add_attribute("CrcErrorSum", AttrR(datatype=Int(), ...))
        ...
```

## Hardware-Specific Controllers

The `catio_hardware.py` module defines controllers for specific Beckhoff terminal types:

### EtherCATMasterController

```python
class EtherCATMasterController(CATioDeviceController):
    io_function: str = "EtherCAT Master Device"
    num_ads_streams: int = 1

    async def get_io_attributes(self) -> None:
        # Frame state attributes
        self.add_attribute(f"InFrm{i}State", AttrR(...))
        self.add_attribute(f"InFrm{i}WcState", AttrR(...))
        self.add_attribute(f"OutFrm{i}Ctrl", AttrR(...))
        
        # ADS name mapping for complex symbol names
        self.ads_name_map[f"InFrm{i}State"] = f"Inputs.Frm{i}State"
```

### Coupler Controllers (EK1100, EK1101, EK1110)

```python
class EK1100Controller(CATioTerminalController):
    io_function: str = "EtherCAT coupler at the head of a segment"

class EK1101Controller(CATioTerminalController):
    io_function: str = "EtherCAT coupler with three ID switches"
    
    async def get_io_attributes(self) -> None:
        self.add_attribute("ID", AttrR(datatype=Int(), ...))
```

### I/O Terminal Controllers

Various controllers for different terminal types:

- **EL10xxController**: Digital input terminals
- **EL20xxController**: Digital output terminals
- **EL30xxController**: Analog input terminals
- **EL40xxController**: Analog output terminals
- **EL50xxController**: Serial communication terminals
- **ELM3xxxController**: High-precision measurement terminals

## Attribute I/O System

### CATioControllerAttributeIORef

References an attribute's connection to the CATio API:

```python
@dataclass
class CATioControllerAttributeIORef(AttributeIORef):
    name: str           # API attribute name
    update_period: float | None = 0.2  # Polling period
```

### CATioControllerAttributeIO

Handles the actual I/O operations for attributes:

```python
class CATioControllerAttributeIO(AttributeIO[AnyT, CATioControllerAttributeIORef]):
    def __init__(
        self,
        connection: CATioConnection,
        subsystem: str,
        controller_id: int,
    ):
        self._connection = connection
        self.subsystem = subsystem
        self.controller_id = controller_id

    async def update(self, attr: AttrR[AnyT, CATioControllerAttributeIORef]) -> None:
        """Poll the attribute value and update if changed."""
        # Handle initial startup poll
        if attr.io_ref.update_period is ONCE:
            await attr.update(self._value[attr.name])
            return
        
        # Regular polling via API query
        query = f"{self.subsystem.upper()}_{attr_name.upper()}_ATTR"
        response = await self._connection.send_query(
            CATioFastCSRequest(command=query, controller_id=self.controller_id)
        )
        
        if response is not None and response != self._value[attr.name]:
            await attr.update(response)
```

## Controller Tree Generation

The system automatically generates a controller hierarchy matching the physical EtherCAT topology:

```python
async def _get_subcontroller_object(
    self,
    node: IOTreeNode,
    subcontrollers: list[CATioController],
) -> CATioController | None:
    from catio.catio_hardware import SUPPORTED_CONTROLLERS

    match node.data.category:
        case IONodeType.Server:
            ctlr = self
            
        case IONodeType.Device:
            key = "ETHERCAT" if node.data.type == DeviceType.IODEVICETYPE_ETHERCAT else node.data.name
            ctlr = SUPPORTED_CONTROLLERS[key](
                name=node.data.get_type_name(),
                ecat_name=node.data.name,
            )
            
        case IONodeType.Coupler | IONodeType.Slave:
            ctlr = SUPPORTED_CONTROLLERS[node.data.type](
                name=node.data.get_type_name(),
                ecat_name=node.data.name,
            )

    await ctlr.add_subcontrollers(subcontrollers)
    return ctlr
```

The `SUPPORTED_CONTROLLERS` dictionary maps terminal type strings to controller classes:

```python
SUPPORTED_CONTROLLERS: dict[str, type[CATioController]] = {
    "ETHERCAT": EtherCATMasterController,
    "EK1100": EK1100Controller,
    "EK1101": EK1101Controller,
    "EL1008": EL10xxController,
    "EL2008": EL20xxController,
    "EL3064": EL30xxController,
    ...
}
```

## PV Naming Convention

CATio generates EPICS PV names following a hierarchical pattern:

```
<PREFIX>:<Server>:<Device>:<Coupler>:<Terminal>:<Attribute>
```

For example:
```
CATIO:IOServer:ETH1:RIO1:MOD5:Value
CATIO:IOServer:ETH1:RIO1:MOD5:EcatState
CATIO:IOServer:ETH1:SlaveCount
```

The naming is derived from:

- **ecat_name**: The EtherCAT system name (e.g., "Device1", "Term145")
- **get_type_name()**: Translates Beckhoff names to PV-friendly format
- **attr_group_name**: Groups related attributes

## Notification-Based Updates

For high-frequency updates, CATio supports ADS device notifications:

```python
async def setup_notifications(self) -> None:
    """Configure notification monitoring for a device."""
    await self.connection.add_notifications(device_id)
    self.connection.enable_notification_monitoring(True, flush_period=0.5)

@scan(NOTIFICATION_UPDATE_PERIOD)
async def _process_notifications(self) -> None:
    """Process received notification data."""
    notifications = await self.connection.get_notification_streams()
    changes = get_notification_changes(notifications, self.attribute_map)
    for attr_name, new_value in changes.items():
        await self.attributes[attr_name].update(new_value)
```

## Lifecycle Management

### Initialization

```python
async def initialise(self) -> None:
    """Initialize the CATio controller system."""
    # Establish TCP connection
    await self.create_tcp_connection(self._tcp_settings)
    
    # Discover and register hardware
    await self.register_subcontrollers()
    
    # Build attribute map
    await self.get_complete_attribute_map()
```

### Connection

```python
async def connect(self) -> None:
    """Establish FastCS connection."""
    if self.sub_controllers:
        for name, subctlr in self.sub_controllers.items():
            await subctlr.connect()
```

### Disconnection

```python
async def disconnect(self) -> None:
    """Clean shutdown of the CATio system."""
    self.connection.enable_notification_monitoring(False)
    await self.connection.close()
```

## See Also

- [Architecture Overview](architecture-overview.md) - High-level system architecture
- [ADS Client Implementation](ads-client.md) - Details of the ADS protocol layer
- [API Decoupling Analysis](api-decoupling.md) - API design discussion
