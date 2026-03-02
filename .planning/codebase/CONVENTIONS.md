# Conventions

## Code Style

- **Formatter/Linter:** ruff (line-length 88)
- **Lint rules:** B (bugbear), C4 (comprehensions), E (pycodestyle errors), F (pyflakes), N (naming), W (warnings), I (isort), UP (pyupgrade), SLF (private member access)
- **Type checking:** pyright in standard mode
- **Python:** 3.11+ features used (match statements, `str | None` unions)

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Files | snake_case, `catio_` prefix for core | `catio_controller.py` |
| Classes | PascalCase, `CATio` prefix | `CATioController`, `CATioDeviceController` |
| Hardware classes | Part number + Controller | `EL3104Controller` |
| Functions/methods | snake_case | `get_io_attributes()`, `read_configuration()` |
| Constants | UPPER_SNAKE_CASE | `OVERSAMPLING_FACTOR`, `TWINCAT_STRING_ENCODING` |
| Private | Leading underscore | `_recv_forever()`, `_ecdevices` |
| Test files | `test_` prefix | `test_catio_units.py` |

## Patterns

### Controller Hierarchy
Controllers follow FastCS `SubController` pattern:
```python
class CATioDeviceController(CATioController):
    async def get_io_attributes(self) -> None:
        await self.get_device_generic_attributes()
```

### Attribute Registration
Attributes are added via `self.add_attribute()` with FastCS types:
```python
self.add_attribute(
    "Name",
    AttrR(
        datatype=String(),
        io_ref=CATioControllerAttributeIORef("name", update_period=ONCE),
        group=self.attr_group_name,
        initial_value=self.io.name,
        description="I/O device name",
    ),
)
```

### Async Throughout
All I/O operations are async. Uses `asyncio` event loops, `asyncio.Task`, `asyncio.Event` for coordination.

### Dataclass-style Config
Hardware controllers use class-level attributes for configuration:
```python
class EL3104Controller(CATioTerminalController):
    io_function: str = "4-channel analog input, +/-10V, 16-bit, differential"
    num_channels: int = 4
```

## Error Handling

- `assert isinstance(...)` used for type narrowing in controller methods
- `logger.exception()` for caught errors in async loops
- `logger.warning()` for degraded but functional states
- Bare `except Exception` in some notification/receive loops (flagged as concern)

## Logging

- Custom `VERBOSE` level (below DEBUG) defined in `src/fastcs_catio/logging.py`
- `VerboseLogger` subclass with `logger.verbose()` method
- Standard `getLogger(__name__)` pattern throughout

## Documentation

- Sphinx with MyST parser, pydata theme
- Docstrings use reStructuredText (`:param:`, `:returns:`)
- Doctest enabled in pytest config
