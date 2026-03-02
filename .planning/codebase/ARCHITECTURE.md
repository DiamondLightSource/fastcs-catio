# Architecture

## Pattern

**Layered controller architecture** built on FastCS framework.

The system follows a hierarchical controller pattern where a top-level `CATioController` discovers EtherCAT hardware via ADS, creates sub-controllers for each device/terminal, and exposes their attributes as EPICS PVs through FastCS.

## Layers

```
┌─────────────────────────────────────────────┐
│  EPICS / NiceGUI (Presentation)             │
│  FastCS backends: softioc, nicegui          │
├─────────────────────────────────────────────┤
│  FastCS Framework (Attribute Layer)         │
│  AttrR, AttrRW, AttrW → PV mapping         │
├─────────────────────────────────────────────┤
│  CATio Controllers (Domain Layer)           │
│  CATioController → Device/Terminal subs     │
│  Hardware-specific controllers (EL3xxx etc) │
├─────────────────────────────────────────────┤
│  CATio Dynamic Layer                        │
│  Dynamic CoE, Symbol, Type controllers      │
│  YAML-driven terminal configuration         │
├─────────────────────────────────────────────┤
│  ADS Client (Transport Layer)               │
│  Async TCP/UDP, AMS protocol, routing       │
├─────────────────────────────────────────────┤
│  TwinCAT PLC / EtherCAT Hardware            │
└─────────────────────────────────────────────┘
```

## Key Abstractions

### Controllers (`src/fastcs_catio/catio_controller.py`)
- `CATioController` — Base controller with ADS connection management, attribute creation, notification handling
- `CATioDeviceController` — Sub-controller for EtherCAT master devices
- `CATioTerminalController` — Sub-controller for EtherCAT slave terminals

### Hardware Controllers (`src/fastcs_catio/catio_hardware.py`)
- Terminal-specific controllers: `EL1xxx`, `EL2xxx`, `EL3xxx`, `EL4xxx`, `EL3702` (oversampling)
- Each defines channel counts, I/O functions, attribute mappings

### Dynamic Controllers (`src/fastcs_catio/catio_dynamic_controller.py`, `catio_dynamic_coe.py`, `catio_dynamic_symbol.py`)
- Runtime-generated controllers from YAML terminal type definitions
- CoE (CANopen over EtherCAT) object discovery and attribute creation
- Symbol-based dynamic attribute creation

### ADS Client (`src/fastcs_catio/client.py`)
- `CatioClient` — Full async ADS client with TCP/UDP transport
- Connection management, route creation/deletion
- Symbol table reading, notification subscriptions
- Device/slave introspection

### Attribute I/O (`src/fastcs_catio/catio_attribute_io.py`)
- `CATioControllerAttributeIO` — Bridge between FastCS attributes and ADS read/write
- Handles polling periods, notification-based updates, value caching

## Data Flow

1. **Startup:** CLI creates `CATioController` → connects via ADS → discovers devices/terminals
2. **Introspection:** For each device/terminal, creates sub-controllers → reads attributes from ADS
3. **Dynamic:** Loads YAML terminal configs → creates dynamic CoE/symbol controllers
4. **Runtime:** FastCS runs scan loop → polls ADS for attribute updates → pushes to EPICS PVs
5. **Notifications:** ADS notifications stream → update controller attributes → propagate to EPICS

## Entry Points

- `src/fastcs_catio/__main__.py` — Typer CLI app with `run` command, connects to ADS and starts FastCS
- `src/catio_terminals/__main__.py` — NiceGUI web app for terminal configuration browsing
- `tests/ads_sim/__main__.py` — ADS simulation server for testing

## Second Package: catio-terminals

Separate package in `src/catio_terminals/` providing a web-based tool for:
- Browsing Beckhoff ESI XML terminal catalogs
- Viewing PDO mappings, CoE objects, symbol definitions
- Managing terminal type YAML configuration files
- Tree-view navigation of terminal hierarchies
