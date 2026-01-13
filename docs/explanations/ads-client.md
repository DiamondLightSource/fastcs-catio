# ADS Client Implementation

This document provides a detailed explanation of the ADS (Automation Device Specification) client layer in CATio, which communicates with TwinCAT ADS servers on Beckhoff PLCs.

## Overview

The ADS client ([client.py](../../src/catio/client.py)) implements the Beckhoff ADS protocol for communication with TwinCAT systems. The implementation follows the [ADS specification](https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html).

## ADS Protocol Fundamentals

### AMS/ADS Architecture

The ADS protocol operates over the AMS (Automation Message Specification) transport layer:

```
┌─────────────────────────────────────────┐
│          ADS Commands                    │
│  (Read, Write, Notification, etc.)       │
├─────────────────────────────────────────┤
│          AMS Header                      │
│  (NetId, Port, CommandId, InvokeId)      │
├─────────────────────────────────────────┤
│       TCP/IP Transport                   │
│  (Port 48898 for unencrypted ADS)       │
└─────────────────────────────────────────┘
```

### Key ADS Ports

```python
ADS_TCP_PORT: int = 48898      # Standard ADS TCP port
ADS_MASTER_PORT: int = 65535   # EtherCAT Master device port
IO_SERVER_PORT: int = 300      # I/O server device port
SYSTEM_SERVICE_PORT: int = 10000  # System services
REMOTE_UDP_PORT: int = 48899   # UDP for route management
```

## Route Management

Before TCP communication, the client must establish a route to the TwinCAT server.

### RemoteRoute Class

```python
class RemoteRoute:
    """Define a remote route to a Beckhoff TwinCAT server via UDP."""

    def __init__(
        self,
        remote: str,
        route_name: str = "",
        user_name: str = "Administrator",
        password: str = "1",
    ):
        self.remote = remote
        self.routename = route_name or get_localhost_name()
        self.hostnetid = AmsNetId.from_string(get_local_netid_str())
        self.username = user_name
        self.password = password
        self.hostname = get_localhost_ip()

    def add(self) -> bool:
        """Add this machine to the TwinCAT server's routing table."""
        UDPMessage.invoke_id += 1
        request = AdsUDPMessage.add_remote_route(
            UDPMessage.invoke_id, self._get_route_info_as_bytes()
        )
        return UDPMessage(self.remote).add_route(request)

    def delete(self) -> bool:
        """Remove this machine from the routing table."""
        ...
```

### UDPMessage Class

Handles UDP communication for route discovery and management:

```python
class UDPMessage:
    """UDP communication with Beckhoff TwinCAT server."""
    
    invoke_id: int = 0
    UDP_COOKIE: bytes = b"\x71\x14\x66\x03"

    def get_netid(self, message: AdsUDPMessage) -> AmsNetId:
        """Get the AmsNetId of the remote TwinCAT server."""
        response = AdsUDPResponseStream.from_bytes(self._send_recv(message))
        return AmsNetId.from_bytes(response.netid.tobytes())
```

## AsyncioADSClient

The main ADS client class providing asynchronous communication:

### Connection Management

```python
class AsyncioADSClient:
    def __init__(
        self,
        target_ams_net_id: str,
        target_ams_port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.__local_ams_net_id = AmsNetId.from_string(get_local_netid_str())
        self.__local_ams_port = 8000
        self.__target_ams_net_id = AmsNetId.from_string(target_ams_net_id)
        self.__target_ams_port = target_ams_port
        self.__reader = reader
        self.__writer = writer
        self.__current_invoke_id = 0
        self.__response_events: dict[SupportsInt, ResponseEvent] = {}
        ...

    @classmethod
    async def connected_to(
        cls,
        target_ip: str,
        target_ams_net_id: str,
        target_ams_port: int,
        ads_port: int = ADS_TCP_PORT,
    ) -> AsyncioADSClient:
        """Create an asynchronous ADS client connection."""
        reader, writer = await asyncio.open_connection(target_ip, ads_port)
        return cls(target_ams_net_id, target_ams_port, reader, writer)
```

### AMS Message Handling

```python
async def _send_ams_message(
    self, command: CommandId, message: Message, **kwargs
) -> ResponseEvent:
    """Send an AMS message to the ADS server."""
    self.__current_invoke_id += 1
    payload = message.to_bytes()
    
    ams_header = AmsHeader(
        target_net_id=ams_netid.to_bytes(),
        target_port=ams_port,
        source_net_id=self.__local_ams_net_id.to_bytes(),
        source_port=self.__local_ams_port,
        command_id=command,
        state_flags=StateFlag.AMSCMDSF_ADSCMD,
        length=len(payload),
        error_code=ErrorCode.ERR_NOERROR,
        invoke_id=np.uint32(self.__current_invoke_id),
    )
    
    header_raw = ams_header.to_bytes()
    total_length = len(header_raw) + len(payload)
    length_bytes = total_length.to_bytes(4, byteorder="little", signed=False)
    
    self.__writer.write(b"\x00\x00" + length_bytes + header_raw + payload)
    await self.__writer.drain()
    
    response_ev = ResponseEvent()
    self.__response_events[self.__current_invoke_id] = response_ev
    return response_ev
```

### Response Handling

A background task continuously monitors for incoming messages:

```python
async def _recv_forever(self) -> None:
    """Receive ADS messages asynchronously until disconnection."""
    while True:
        try:
            header, body = await self._recv_ams_message()
            
            if header.command_id == CommandId.ADSSRVID_DEVICENOTE:
                await self._handle_notification(header, body)
            else:
                cls = RESPONSE_CLASS[CommandId(header.command_id)]
                response = cls.from_bytes(body)
                self.__response_events[header.invoke_id].set(response)
                
        except ConnectionAbortedError:
            break
```

## ADS Commands

### Command Types

```python
class CommandId(np.uint16, Enum):
    ADSSRVID_READDEVICEINFO = 0x1  # Read device name and version
    ADSSRVID_READ = 0x2            # Read data
    ADSSRVID_WRITE = 0x3           # Write data
    ADSSRVID_READSTATE = 0x4       # Read ADS/device status
    ADSSRVID_WRITECTRL = 0x5       # Change ADS/device status
    ADSSRVID_ADDDEVICENOTE = 0x6   # Create notification
    ADSSRVID_DELETEDEVICENOTE = 0x7  # Delete notification
    ADSSRVID_DEVICENOTE = 0x8      # Notification data
    ADSSRVID_READWRITE = 0x9       # Combined read/write
```

### Generic Command Execution

```python
async def _ads_command(
    self,
    request: MessageRequest,
    **kwargs: AmsNetId | int,
) -> MessageResponse:
    """Send an ADS Command request and return the response."""
    response_event = await self._send_ams_message(
        REQUEST_CLASS[type(request)], request, **kwargs
    )
    cls = MESSAGE_CLASS[type(request)]
    response = await response_event.get(cls)
    assert response.result == ErrorCode.ERR_NOERROR
    return response
```

## I/O Server Introspection

The client introspects the TwinCAT I/O server to discover hardware:

### Server Information

```python
async def _get_io_server(self) -> IOServer:
    """Get I/O server information."""
    info_response = await self._read_io_info()
    
    return IOServer(
        name=bytes_to_string(info_response.device_name.tobytes()),
        version=f"{info_response.major_version}-{info_response.minor_version}",
        build=info_response.version_build,
        num_devices=await self._get_device_count(),
    )
```

### Device Discovery

```python
async def _get_ethercat_devices(self) -> dict[SupportsInt, IODevice]:
    """Get information about registered EtherCAT devices."""
    dev_ids, dev_types = await self.get_ethercat_master_device()
    dev_names = await self._get_device_names(dev_ids)
    dev_netids = await self._get_device_netids(dev_ids)
    dev_identities = await self._get_device_identities(dev_netids)
    dev_frames = await self._get_device_frame_counters(dev_netids)
    dev_slave_counts = await self._get_slave_count(dev_netids)
    ...
    
    for params in zip(dev_ids, dev_types, dev_names, ...):
        device = IODevice(*params)
        devices[device.id] = device
    
    return devices
```

### Slave Terminal Discovery

```python
async def _get_slave_identities(
    self,
    dev_netids: Sequence[AmsNetId],
    dev_slave_addresses: Sequence[Sequence[np.uint16]],
) -> Sequence[Sequence[IOIdentity]]:
    """Get CANopen identity of all slave terminals."""
    slave_identities: Sequence[Sequence[IOIdentity]] = []
    
    for netid, addresses in zip(dev_netids, dev_slave_addresses):
        identities = []
        for address in addresses:
            response = await self._ads_command(
                AdsReadRequest.read_slave_identity(address),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            identities.append(IOIdentity.from_bytes(response.data))
        slave_identities.append(identities)
    
    return slave_identities
```

## Symbol Management

### Symbol Discovery

ADS symbols provide named access to device parameters:

```python
async def get_all_symbols(self) -> dict[SupportsInt, Sequence[AdsSymbol]]:
    """Get all subscribable symbols for each device."""
    symbols: dict[SupportsInt, Sequence[AdsSymbol]] = {}
    
    for device_id in self._ecdevices:
        device_symbols = await self._get_device_symbols(device_id)
        symbols[device_id] = device_symbols
    
    return symbols
```

### Symbol Data Structure

```python
@dataclass
class AdsSymbol:
    parent_id: SupportsInt    # Device the symbol belongs to
    name: str                  # Symbol name
    dtype: npt.DTypeLike      # Data type
    size: int                  # Number of elements
    group: SupportsInt        # ADS index group
    offset: SupportsInt       # ADS index offset
    comment: str              # Optional description
    handle: SupportsInt | None = None  # Notification handle
```

## Notification System

For efficient updates, CATio uses ADS device notifications instead of polling:

### Adding Notifications

```python
async def add_notifications(
    self,
    symbols: Sequence[AdsSymbol],
    max_delay_ms: int = 100,
    cycle_time_ms: int = 100,
) -> None:
    """Register symbol notifications with the server."""
    for symbol in symbols:
        request = AdsAddDeviceNotificationRequest(
            index_group=symbol.group,
            index_offset=symbol.offset,
            length=symbol.nbytes,
            transmission_mode=TransmissionMode.ADSTRANS_SERVERCYCLE,
            max_delay=max_delay_ms * 10000,  # Convert to 100ns units
            cycle_time=cycle_time_ms * 10000,
        )
        
        response = await self._ads_command(request)
        symbol.handle = response.notification_handle
        self.__device_notification_handles[response.notification_handle] = symbol
```

### Processing Notifications

```python
async def _handle_notification(self, header: AmsHeader, body: bytes) -> None:
    """Process notification message data."""
    if self.__buffer is not None:
        id = int(header.invoke_id)
        
        # Store template for multi-stream notifications
        if id not in self.__notif_templates:
            self.__notif_templates[id] = body
            self.__num_notif_streams += 1
        
        # Accumulate notification data
        self.__buffer += body
```

### Notification Monitoring

```python
def start_notification_monitor(self, flush_period: float = 0.5) -> None:
    """Start background task for notification processing."""
    self.__buffer = bytearray()
    self.__notification_task = asyncio.create_task(
        self._monitor_notifications(flush_period)
    )

async def _monitor_notifications(self, flush_period: float) -> None:
    """Periodically flush notification buffer to queue."""
    while True:
        await asyncio.sleep(flush_period)
        if self.__buffer:
            await self.__notification_queue.put(bytes(self.__buffer))
            self.__buffer.clear()
```

## API Layer

The client exposes a clean API for the FastCS layer:

### Query Method

```python
async def query(self, message: str, *args, **kwargs) -> Any:
    """Call API method for a query."""
    get = f"get_{message.lower()}"
    if hasattr(self, get) and callable(func := getattr(self, get)):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    raise ValueError(f"No API method found for query '{message}'")
```

### Command Method

```python
async def command(self, command: str, *args, **kwargs) -> Any:
    """Call API method for a command."""
    set = f"set_{command.lower()}"
    if hasattr(self, set) and callable(func := getattr(self, set)):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    raise ValueError(f"No API method found for command '{command}'")
```

### Example API Methods

```python
def get_system_tree(self) -> IOTreeNode:
    """Get tree representation of the EtherCAT system."""
    return self._generate_system_tree()

def get_io_from_map(
    self, identifier: int, io_group: str, io_name: str = ""
) -> IOServer | IODevice | IOSlave:
    """Get I/O object by identifier."""
    ...

async def get_device_framecounters_attr(
    self, controller_id: int | None = None
) -> npt.NDArray[np.uint32]:
    """Get frame counters for an EtherCAT device."""
    device = self.fastcs_io_map.get(controller_id)
    await self.get_device_frames(device.id)
    return np.array([
        device.frame_counters.time,
        device.frame_counters.cyclic_sent,
        device.frame_counters.cyclic_lost,
        ...
    ])
```

## Message Framework

### Message Base Class

All ADS messages inherit from a common base:

```python
@dataclass_transform(kw_only_default=True)
class Message:
    """Generic ADS message type."""
    
    def to_bytes(self) -> bytes:
        """Serialize message to bytes."""
        ...
    
    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """Deserialize message from bytes."""
        ...
```

### Request/Response Mapping

```python
REQUEST_CLASS: dict[type[MessageRequest], CommandId] = {
    AdsReadDeviceInfoRequest: CommandId.ADSSRVID_READDEVICEINFO,
    AdsReadRequest: CommandId.ADSSRVID_READ,
    AdsWriteRequest: CommandId.ADSSRVID_WRITE,
    AdsReadWriteRequest: CommandId.ADSSRVID_READWRITE,
    ...
}

RESPONSE_CLASS: dict[CommandId, type[MessageResponse]] = {
    CommandId.ADSSRVID_READDEVICEINFO: AdsReadDeviceInfoResponse,
    CommandId.ADSSRVID_READ: AdsReadResponse,
    ...
}
```

## Error Handling

```python
class ErrorCode(np.uint32, Enum):
    ERR_NOERROR = 0x0
    ADSERR_DEVICE_ERROR = 0x700
    ADSERR_DEVICE_SRVNOTSUPP = 0x701
    ADSERR_DEVICE_INVALIDGRP = 0x702
    ADSERR_DEVICE_INVALIDOFFSET = 0x703
    ADSERR_DEVICE_INVALIDACCESS = 0x704
    ADSERR_DEVICE_INVALIDSIZE = 0x705
    ADSERR_DEVICE_INVALIDDATA = 0x706
    ADSERR_DEVICE_NOTREADY = 0x707
    ADSERR_DEVICE_BUSY = 0x708
    ...
```

## See Also

- [Architecture Overview](architecture-overview.md) - High-level system architecture
- [FastCS EPICS IOC Implementation](fastcs-epics-ioc.md) - Details of the EPICS layer
- [API Decoupling Analysis](api-decoupling.md) - API design discussion
- [Beckhoff ADS Documentation](https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html) - Official ADS specification
