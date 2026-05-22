# API Decoupling Analysis

This document analyzes the current API design that separates the FastCS EPICS IOC layer from the ADS client layer in CATio, identifies potential flaws in the decoupling, and proposes improvements.

## Current API Architecture

### The Bridge Layer

The API bridge between FastCS and the ADS client consists of three main components:

```
┌───────────────────────────────────────────┐
│           CATioConnection                 │
│  • Singleton pattern for connection       │
│  • Manages CATioStreamConnection          │
│  • Provides send_query/send_command       │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│         CATioStreamConnection             │
│  • Async context manager                  │
│  • Wraps AsyncioADSClient                 │
│  • Handles notifications                  │
└───────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────┐
│           AsyncioADSClient                │
│  • query() / command() dispatch           │
│  • get_* / set_* API methods              │
│  • Direct ADS protocol operations         │
└───────────────────────────────────────────┘
```

### Current Request/Response Pattern

```python
# FastCS Layer
class CATioFastCSRequest:
    def __init__(self, command: str, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs

@dataclass
class CATioFastCSResponse:
    value: Any

# Connection Layer
async def send_query(self, message: CATioFastCSRequest) -> Any:
    async with self._connection as connection:
        response = await connection.query(message)
        return response.value

# ADS Client Layer
async def query(self, message: str, *args, **kwargs) -> Any:
    get = f"get_{message.lower()}"
    if hasattr(self, get) and callable(func := getattr(self, get)):
        return await func(*args, **kwargs)
    raise ValueError(f"No API method found for query '{message}'")
```

## Identified Flaws

### 1. String-Based API Dispatch

**Problem**: The current API uses string-based method dispatch:

```python
# Current approach
query = f"{self.subsystem.upper()}_{function_name.upper()}_ATTR"
response = await self._connection.send_query(
    CATioFastCSRequest(command=query, controller_id=self._identifier)
)
```

**Issues**:
- No compile-time type checking
- Typos in string names only caught at runtime
- Difficult to discover available API methods
- IDE auto-completion doesn't work
- Refactoring is error-prone

**Example of fragility**:
```python
# This typo won't be caught until runtime:
await client.query("DEVICE_FRAMECOUNTERS_ATTR")  # Should be FRAMECOUNTERS
```

### 2. Tight Coupling via Controller ID

**Problem**: The FastCS layer passes controller IDs through the API:

```python
# FastCS layer knows too much about ADS client internals
response = await self.connection.send_query(
    CATioFastCSRequest(command=query, controller_id=self._identifier)
)

# ADS client maintains a mapping
self.fastcs_io_map: dict[int, IOServer | IODevice | IOSlave] = {}
```

**Issues**:
- The API leaks implementation details (controller identifiers)
- ADS client must maintain state about FastCS controllers
- Creates circular dependency conceptually
- Makes unit testing more difficult

### 3. Mixed Concerns in AsyncioADSClient

**Problem**: The `AsyncioADSClient` class handles too many responsibilities:

```python
class AsyncioADSClient:
    # Protocol handling
    async def _send_ams_message(...)
    async def _recv_ams_message(...)

    # I/O introspection
    async def _get_device_count(...)
    async def _get_ethercat_devices(...)

    # Symbol management
    async def get_all_symbols(...)
    async def add_notifications(...)

    # State monitoring
    async def poll_states(...)
    async def check_slave_states(...)

    # API layer
    async def query(...)
    async def command(...)
    async def get_device_framecounters_attr(...)
    async def get_terminal_states_attr(...)
```

**Issues**:
- 3000+ lines in a single file
- Difficult to test individual components
- Changes to protocol affect API methods
- No clear separation of concerns

### 4. Notification Handling Coupling

**Problem**: Notification processing spans multiple layers:

```python
# Connection layer knows about symbols
async def add_notifications(self, device_id: int) -> None:
    subscription_symbols = self.notification_symbols[device_id]
    await self.client.add_notifications(subscription_symbols)

# Controller layer processes notification data
@scan(NOTIFICATION_UPDATE_PERIOD)
async def _process_notifications(self) -> None:
    notifications = await self.connection.get_notification_streams()
    changes = get_notification_changes(notifications, self.attribute_map)
```

**Issues**:
- Notification logic spread across layers
- Raw byte streams bubble up to controller layer
- Difficult to change notification strategy

### 5. Error Handling Inconsistency

**Problem**: Error handling varies across the API:

```python
# Some methods raise ValueError
async def query(self, message: str, *args, **kwargs) -> Any:
    raise ValueError(f"No API method found for query '{message}'")

# Some methods use assertions
async def get_device_framecounters_attr(self, controller_id: int | None) -> ...:
    assert isinstance(device, IODevice)

# Some catch and log
try:
    response = await self.client.query(...)
except ValueError as err:
    logging.debug(f"API call failed: {err}")
```

**Issues**:
- Unpredictable error behavior
- Some errors silently logged, others raised
- Difficult to implement consistent error recovery

### 6. Lack of Abstract Interface Definition

**Problem**: No formal interface contract between layers:

```python
# The API contract is implicit, defined by method naming convention
async def query(self, message: str, *args, **kwargs) -> Any:
    get = f"get_{message.lower()}"
    if hasattr(self, get) and callable(func := getattr(self, get)):
        ...
```

**Issues**:
- API discovery requires reading implementation
- No guaranteed method signatures
- Difficult to create mock implementations

## Proposed Improvements

### 1. Define Explicit Interface Protocol

Create a formal protocol (abstract base class) defining the API contract:

```python
from typing import Protocol

class ICATioClient(Protocol):
    """Interface for CATio client operations."""

    async def get_system_tree(self) -> IOTreeNode: ...

    async def get_device_frame_counters(
        self, device_id: int
    ) -> DeviceFrameCounters: ...

    async def get_device_slave_count(
        self, device_id: int
    ) -> int: ...

    async def get_terminal_state(
        self, device_id: int, terminal_address: int
    ) -> TerminalState: ...

    async def subscribe_to_symbol(
        self, symbol: AdsSymbol, callback: Callable[[Any], None]
    ) -> SubscriptionHandle: ...
```

**Benefits**:
- Clear contract between layers
- Type checking at development time
- Easy to create test mocks
- Self-documenting API

### 2. Use Data Transfer Objects

Replace controller IDs with proper DTOs:

```python
@dataclass(frozen=True)
class DeviceReference:
    """Immutable reference to an EtherCAT device."""
    device_id: int
    device_name: str

@dataclass(frozen=True)
class TerminalReference:
    """Immutable reference to a terminal."""
    device_id: int
    terminal_address: int
    terminal_type: str

# API methods accept references
async def get_terminal_state(
    self, ref: TerminalReference
) -> TerminalState: ...
```

**Benefits**:
- Type safety for references
- No leaked implementation details
- Immutable, hashable for caching

### 3. Separate Concerns into Modules

Split the monolithic client into focused components:

```python
# ads_protocol.py - Low-level ADS protocol handling
class AdsProtocolHandler:
    async def send_request(self, request: AdsRequest) -> AdsResponse: ...
    async def receive_response(self) -> AdsResponse: ...

# io_introspection.py - Hardware discovery
class IoIntrospectionService:
    def __init__(self, protocol: AdsProtocolHandler): ...
    async def discover_devices(self) -> list[IODevice]: ...
    async def discover_terminals(self, device: IODevice) -> list[IOSlave]: ...

# symbol_service.py - Symbol management
class SymbolService:
    def __init__(self, protocol: AdsProtocolHandler): ...
    async def get_symbols(self, device_id: int) -> list[AdsSymbol]: ...
    async def read_symbol(self, symbol: AdsSymbol) -> Any: ...

# notification_service.py - Notification handling
class NotificationService:
    def __init__(self, protocol: AdsProtocolHandler): ...
    async def subscribe(
        self, symbol: AdsSymbol, callback: Callable
    ) -> SubscriptionHandle: ...

# catio_client.py - High-level client facade
class CATioClient:
    def __init__(
        self,
        protocol: AdsProtocolHandler,
        introspection: IoIntrospectionService,
        symbols: SymbolService,
        notifications: NotificationService,
    ): ...
```

**Benefits**:
- Single responsibility per class
- Easier testing of individual components
- Clearer dependencies
- Manageable file sizes

### 4. Implement Observer Pattern for Notifications

Decouple notification consumers from producers:

```python
class NotificationObserver(Protocol):
    """Protocol for notification consumers."""
    def on_value_changed(self, symbol_name: str, new_value: Any) -> None: ...

class NotificationService:
    def __init__(self):
        self._observers: dict[str, list[NotificationObserver]] = {}

    def add_observer(
        self, symbol_name: str, observer: NotificationObserver
    ) -> None:
        self._observers.setdefault(symbol_name, []).append(observer)

    async def _process_notification(self, data: bytes) -> None:
        symbol_name, value = self._parse_notification(data)
        for observer in self._observers.get(symbol_name, []):
            observer.on_value_changed(symbol_name, value)
```

**Benefits**:
- Clean separation of notification production and consumption
- Multiple observers per symbol
- Easy to add new notification consumers

### 5. Standardize Error Handling

Create a consistent error hierarchy:

```python
class CATioError(Exception):
    """Base exception for CATio errors."""
    pass

class ConnectionError(CATioError):
    """Raised when connection to TwinCAT fails."""
    pass

class DeviceNotFoundError(CATioError):
    """Raised when referenced device doesn't exist."""
    def __init__(self, device_id: int):
        super().__init__(f"Device {device_id} not found")
        self.device_id = device_id

class ProtocolError(CATioError):
    """Raised on ADS protocol errors."""
    def __init__(self, error_code: ErrorCode):
        super().__init__(f"ADS error: {error_code.name}")
        self.error_code = error_code
```

**Benefits**:
- Predictable error behavior
- Rich error information
- Easy to catch specific error types

### 6. Add Dependency Injection

Enable flexible composition and testing:

```python
class CATioServerController(Controller):
    def __init__(
        self,
        client: ICATioClient,  # Inject interface, not implementation
        config: CATioConfiguration,
    ):
        self._client = client
        self._config = config

    async def initialise(self) -> None:
        tree = await self._client.get_system_tree()
        await self._build_controller_hierarchy(tree)
```

**Benefits**:
- Easy to inject mock client for testing
- Clear dependencies
- Flexible configuration

## Migration Path

A phased approach to implementing these improvements:

### Phase 1: Interface Definition
1. Define `ICATioClient` protocol
2. Create data transfer objects
3. Standardize error types
4. Update existing code to use new types

### Phase 2: Component Separation
1. Extract `AdsProtocolHandler`
2. Extract `IoIntrospectionService`
3. Extract `SymbolService`
4. Create `CATioClient` facade

### Phase 3: Notification Refactoring
1. Implement observer pattern
2. Move notification logic to `NotificationService`
3. Update controllers to use observers

### Phase 4: Testing Infrastructure
1. Create mock implementations
2. Add unit tests for each component
3. Add integration tests for API contract

## Conclusion

The current CATio architecture successfully separates the FastCS EPICS layer from the ADS protocol layer, but the API between them has several areas for improvement:

1. **String-based dispatch** should be replaced with explicit method definitions
2. **Controller ID coupling** should be replaced with proper DTOs
3. **Monolithic client** should be separated into focused services
4. **Notification handling** should use observer pattern
5. **Error handling** should be standardized
6. **Dependencies** should be injected for testability

These improvements would make the codebase more maintainable, testable, and easier to extend while preserving the fundamental two-layer architecture.

## See Also

- [Architecture Overview](../architecture-overview.md) - High-level system architecture
- [FastCS EPICS IOC Implementation](../fastcs-epics-ioc.md) - Details of the EPICS layer
- [ADS Client Implementation](../ads-client.md) - Details of the ADS protocol layer
