# Testing

## Framework

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | (latest) | Test runner |
| pytest-asyncio | >=1.3.0 | Async test support (auto mode) |
| pytest-cov | (latest) | Coverage reporting |
| tox-uv | (latest) | Test automation with uv |

## Configuration

```toml
# pyproject.toml
asyncio_mode = "auto"
testpaths = "docs src tests"
addopts = "--tb=native -vv --doctest-modules --doctest-glob='*.rst'"
```

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures, pytest configuration
├── mock_server.py                 # Mock ADS server for unit-level tests
├── ads_sim/                       # Full ADS simulation server
│   ├── __main__.py                # Standalone entry point
│   ├── ethercat_chain.py          # Configurable simulated EtherCAT chains
│   └── server.py                  # Async TCP/UDP ADS protocol server
├── test_async_client.py           # ADS client async tests
├── test_beckhoff_client.py        # Beckhoff XML catalog tests
├── test_catio_dynamic.py          # Dynamic controller tests
├── test_catio_performance.py      # Performance tests (SKIPPED)
├── test_catio_system.py           # System integration tests (SKIPPED)
├── test_catio_terminals.py        # Terminal package tests
├── test_catio_units.py            # Core unit tests
├── test_cli.py                    # CLI command tests
├── test_coe_readwrite.py          # CoE read/write tests
├── test_mock_server_example.py    # Mock server usage example
├── test_new_terminal_coe_selection.py  # Terminal CoE selection tests
├── test_pdo_groups.py             # PDO group tests
├── test_symbol_notifications.py   # Symbol notification tests
├── test_symbol_readwrite.py       # Symbol read/write tests
├── test_system.py                 # System-level tests
├── test_variable_polling.py       # Variable polling tests
└── test_xml_parser_pdo.py         # XML PDO parser tests
```

## Test Approaches

### ADS Simulation Server (`tests/ads_sim/`)
Full async ADS protocol simulator used for integration tests. Supports configurable EtherCAT device chains with simulated I/O. Runs as standalone process or within test fixtures.

### Mock Server (`tests/mock_server.py`)
Lighter-weight mock for unit tests that don't need full protocol simulation.

### Async Testing
All tests use `pytest-asyncio` in auto mode — async test functions and fixtures are automatically detected.

## Coverage

- Coverage via `pytest-cov`, reporting to `/tmp/fastcs_catio.coverage`
- Source mapping from installed packages back to `src/`
- XML report: `cov.xml`

## Known Gaps

- `test_catio_system.py` — **entirely skipped** (`pytest.skip(allow_module_level=True, reason="TODO these are all failing")`)
- `test_catio_performance.py` — **entirely skipped** (same reason)
- Error recovery paths in `_recv_forever` untested
- Symbol refresh flow untested
- Multi-stream notification paths untested
