# Integrations

## External Protocols

### ADS (Automation Device Specification) — Primary
- **Protocol:** TwinCAT ADS over TCP (port 48898) and UDP (port 48899)
- **Implementation:** Custom async client in `src/fastcs_catio/client.py` (~2500 lines)
- **Purpose:** Communicate with Beckhoff TwinCAT PLCs and EtherCAT I/O devices
- **Key operations:** Read/write symbols, device introspection, notification subscriptions, route management
- **Message layer:** `src/fastcs_catio/messages.py` — AMS/TCP and AMS headers, request/response framing

### EPICS — Control System Backend
- **Protocol:** Channel Access (CA) / PVAccess (PVA) via softioc
- **Integration:** FastCS handles EPICS backend automatically via `fastcs[epics]`
- **Purpose:** Expose EtherCAT I/O as EPICS Process Variables

### HTTP — Beckhoff XML Catalog
- **Client:** httpx in `src/catio_terminals/beckhoff.py`
- **Purpose:** Download EtherCAT Slave Information (ESI) XML files from Beckhoff's online catalog
- **Endpoint:** Beckhoff's public ESI XML repository

## Internal Services

### ADS Simulation Server
- **Location:** `tests/ads_sim/`
- **Purpose:** Test harness simulating a TwinCAT ADS server with configurable EtherCAT chains
- **Entry point:** `tests/ads_sim/__main__.py` — standalone async TCP/UDP server
- **Protocol:** Full ADS/AMS protocol simulation

### NiceGUI Web Application
- **Location:** `src/catio_terminals/ui_app.py`
- **Purpose:** Web-based terminal configuration and browsing tool
- **Components:** `src/catio_terminals/ui_components/` — tree views, detail panes, symbol details
- **Dialogs:** `src/catio_terminals/ui_dialogs/` — confirmation, file, database, terminal dialogs

## Data Stores

### YAML Configuration Files
- Terminal type definitions: `src/catio_terminals/terminals/terminal_types.yaml`
- Runtime symbols: `src/catio_terminals/config/runtime_symbols.yaml`
- Controller config: `src/fastcs_catio/fastcs.yaml`

### ESI XML Files
- Parsed by `src/catio_terminals/xml/` package
- Contains: PDO definitions, CoE objects, device descriptions
- Cached locally after download from Beckhoff catalog

## Authentication

- ADS routes use password-based authentication (default password: `"1"` in `RemoteRoute`)
- No other auth mechanisms (no OAuth, no API keys)
