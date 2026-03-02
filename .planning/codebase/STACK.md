# Stack

## Language & Runtime

| Property | Value |
|----------|-------|
| Language | Python |
| Version | >=3.11 (3.11, 3.12, 3.13) |
| Build System | setuptools + setuptools_scm |
| Package Manager | uv (lockfile: `uv.lock`) |

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastcs | 0.12.0a1 (with `[epics]` extra) | Control system framework — provides `Controller`, `SubController`, `AttrR`, `AttrRW`, `AttrW` and backend runners |
| softioc | >=4.7.0 | EPICS IOC server (Channel Access / PVAccess) |
| numpy | (latest) | Numeric data handling, array operations for oversampling |
| pvi | (latest) | Process Variable Interface generation |
| nicegui | >=3.6.1 | Web UI framework for `catio-terminals` tool |
| typer | (latest) | CLI framework for both entry points |

## Optional Dependencies (`[terminals]`)

| Package | Version | Purpose |
|---------|---------|---------|
| nicegui | >=2.0.0 | Web UI (also core dep) |
| pydantic | >=2.0.0 | Data models for terminal configuration |
| pyyaml | >=6.0 | YAML parsing |
| ruamel.yaml | >=0.18.0 | YAML read/write with comment preservation |
| httpx | >=0.27.0 | HTTP client for Beckhoff XML catalog downloads |

## Dev Dependencies

| Package | Purpose |
|---------|---------|
| pytest + pytest-asyncio + pytest-cov | Testing |
| ruff | Linting & formatting |
| pyright | Type checking |
| pre-commit | Git hooks |
| sphinx + extensions | Documentation |
| tox-uv | Test automation |

## Entry Points

| Command | Module | Purpose |
|---------|--------|---------|
| `fastcs-catio` | `fastcs_catio.__main__:app` | Main control system application (Typer CLI) |
| `catio-terminals` | `catio_terminals.__main__:main` | Terminal configuration web UI |

## Configuration

- `pyproject.toml` — project metadata, dependencies, tool config
- `src/fastcs_catio/catio_controller.yaml` — controller configuration
- `src/catio_terminals/config/runtime_symbols.yaml` — runtime symbol definitions
- `src/catio_terminals/terminals/terminal_types.yaml` — terminal type definitions
- `renovate.json` — dependency update automation
- `ruff` — line-length 88, rules: B, C4, E, F, N, W, I, UP, SLF
- `pyright` — standard mode, `reportMissingImports = false`
- `pytest` — asyncio auto mode, doctest enabled
