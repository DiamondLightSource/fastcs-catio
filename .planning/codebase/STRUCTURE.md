# Structure

## Directory Layout

```
fastcs-catio/
├── src/
│   ├── fastcs_catio/              # Main package — EtherCAT control system
│   │   ├── __init__.py
│   │   ├── __main__.py            # Typer CLI entry point
│   │   ├── _constants.py          # Constants (encoding, defaults)
│   │   ├── _types.py              # Type aliases
│   │   ├── _version.py            # Auto-generated version (setuptools_scm)
│   │   ├── catio_attribute_io.py  # FastCS attribute ↔ ADS I/O bridge
│   │   ├── catio_connection.py    # Connection management
│   │   ├── catio_controller.py    # Core controller hierarchy (~1200 lines)
│   │   ├── catio_controller.yaml  # Controller configuration
│   │   ├── catio_dynamic_coe.py   # Dynamic CoE object controllers
│   │   ├── catio_dynamic_controller.py  # Dynamic terminal controllers
│   │   ├── catio_dynamic_symbol.py      # Dynamic symbol controllers
│   │   ├── catio_dynamic_types.py       # Dynamic type definitions
│   │   ├── catio_hardware.py      # Hardware-specific controllers (EL series)
│   │   ├── client.py              # ADS async client (~2500 lines, largest file)
│   │   ├── devices.py             # Device/slave data models
│   │   ├── logging.py             # Custom VERBOSE logging level
│   │   ├── messages.py            # AMS/TCP protocol messages
│   │   ├── symbols.py             # ADS symbol handling
│   │   ├── terminal_config.py     # YAML terminal type configuration
│   │   └── utils.py               # Network/data utilities
│   │
│   └── catio_terminals/           # Second package — terminal config web UI
│       ├── __init__.py
│       ├── __main__.py            # NiceGUI web app entry point
│       ├── ads_types.py           # ADS type definitions
│       ├── beckhoff.py            # Beckhoff ESI XML catalog client
│       ├── models.py              # Pydantic data models
│       ├── service_config.py      # Configuration service
│       ├── service_file.py        # File management service
│       ├── service_terminal.py    # Terminal service
│       ├── ui_app.py              # Main NiceGUI application
│       ├── utils.py               # Utility functions
│       ├── config/
│       │   └── runtime_symbols.yaml
│       ├── terminals/
│       │   └── terminal_types.yaml
│       ├── ui_components/         # NiceGUI components
│       │   ├── details_pane.py
│       │   ├── symbol_details.py
│       │   ├── terminal_details.py
│       │   ├── tree_data_builder.py
│       │   ├── tree_view.py
│       │   └── utils.py
│       ├── ui_dialogs/            # NiceGUI dialogs
│       │   ├── confirmation_dialogs.py
│       │   ├── database_dialogs.py
│       │   ├── delete_dialogs.py
│       │   ├── file_dialogs.py
│       │   └── terminal_dialogs.py
│       └── xml/                   # ESI XML parsing
│           ├── cache.py
│           ├── catalog.py
│           ├── coe.py
│           ├── constants.py
│           ├── parser.py
│           ├── pdo_groups.py
│           └── pdo.py
│
├── tests/
│   ├── conftest.py                # Shared fixtures
│   ├── mock_server.py             # Mock ADS server for unit tests
│   ├── ads_sim/                   # Full ADS simulation server
│   │   ├── __main__.py            # Standalone entry point
│   │   ├── ethercat_chain.py      # Simulated EtherCAT device chains
│   │   └── server.py              # Async TCP/UDP ADS server
│   ├── test_async_client.py       # ADS client tests
│   ├── test_catio_system.py       # System tests (currently skipped)
│   ├── test_catio_performance.py  # Performance tests (currently skipped)
│   ├── test_catio_dynamic.py      # Dynamic controller tests
│   ├── test_catio_terminals.py    # Terminal package tests
│   ├── test_catio_units.py        # Unit tests
│   ├── test_cli.py                # CLI tests
│   └── ... (13 more test files)
│
├── docs/                          # Sphinx documentation
├── pyproject.toml                 # Project configuration
├── uv.lock                        # Dependency lockfile
└── renovate.json                  # Dependency automation
```

## Key Locations

| What | Where |
|------|-------|
| Main controller logic | `src/fastcs_catio/catio_controller.py` |
| ADS protocol client | `src/fastcs_catio/client.py` |
| Hardware controllers | `src/fastcs_catio/catio_hardware.py` |
| Dynamic controllers | `src/fastcs_catio/catio_dynamic_*.py` |
| Terminal web UI | `src/catio_terminals/ui_app.py` |
| Test fixtures | `tests/conftest.py` |
| ADS simulator | `tests/ads_sim/` |

## Naming Conventions

- **Files:** snake_case, prefixed with `catio_` for core module files
- **Classes:** PascalCase, prefixed with `CATio` for controllers
- **Hardware classes:** Named after Beckhoff part numbers (e.g., `EL3104Controller`)
- **Dynamic prefixes:** `catio_dynamic_` for runtime-generated controller modules
- **UI organization:** `ui_components/` and `ui_dialogs/` sub-packages
- **Test files:** `test_` prefix, descriptive names
