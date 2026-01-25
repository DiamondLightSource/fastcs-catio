# Terminal Type Definitions

Terminal type definitions in CATio describe Beckhoff EtherCAT I/O terminals and their characteristics. These definitions are stored in YAML files organized by terminal class in `src/fastcs_catio/terminals/`.

## Purpose

Terminal type definitions serve two purposes:

1. **ADS Simulation**: The test ADS simulator uses these definitions to emulate terminal behavior and create accurate symbol tables
2. **FastCS Integration**: (Future) These definitions will be used to dynamically generate FastCS controller classes for each terminal type

## Generating Terminal Definitions with catio-terminals

The recommended way to create and maintain terminal definition files is using the `catio-terminals` GUI editor. This tool fetches terminal information from Beckhoff's XML descriptions (ESI files) and generates consistent YAML files.

### Installation

```bash
uv pip install -e ".[terminals]"
```

### Updating the XML Cache

Before generating terminal definitions, update the local XML cache from Beckhoff's servers:

```bash
# this command is also available in the terminal editor GUI
# you would only need to run it if ~/.cache/catio_terminals/ is outdated
catio-terminals --update-cache
```

This downloads and parses the latest ESI XML files from Beckhoff, storing them in `~/.cache/catio_terminals/terminals_cache.json`.

### Creating or Editing Terminal Files

Launch the GUI editor:

```bash
catio-terminals
```

Or open an existing file directly:

```bash
catio-terminals path/to/terminals.yaml
```

### Workflow

1. **Open or create** a YAML file when prompted
2. **Add terminals** by clicking "Add Terminal" and searching Beckhoff's catalog
3. **Select symbols** to include from the available PDO entries shown in the XML
4. **Save** the file - only selected symbols are written to YAML

The editor merges your YAML selections with the XML definitions, ensuring that:
- Symbols are derived from Beckhoff's official XML descriptions (TxPdo/RxPdo entries)
- Any symbols in the YAML that don't exist in the XML are dropped with a warning
- New symbols from XML updates can be discovered and added

## File Organization

Terminal definitions are organized by functional class:

- `bus_couplers.yaml` - EtherCAT couplers and extensions (EK1100, EK1110, etc.)
- `digital_input.yaml` - Digital input terminals (EL1004, EL1014, EL1084, etc.)
- `digital_output.yaml` - Digital output terminals (EL2004, EL2024, EL2809, etc.)
- `counter.yaml` - Counter and frequency input terminals (EL1502, etc.)
- `analog_input.yaml` - Analog input terminals (EL3004, EL3104, EL3602, etc.)
- `analog_output.yaml` - Analog output terminals (EL4004, EL4134, etc.)
- `power_supply.yaml` - Power supply and system terminals (EL9410, EL9512, etc.)

## Terminal Definition Structure

Each terminal type definition contains:

### Identity

CANopen identity information that uniquely identifies the terminal:

```yaml
identity:
  vendor_id: 2              # Vendor ID (2 = Beckhoff)
  product_code: 196882514   # Product code (decimal)
  revision_number: 1048576  # Revision number (decimal)
```

### Symbol Nodes

Symbol nodes define the Process Data Objects (PDOs) available on the terminal. These are extracted from the TxPdo (inputs) and RxPdo (outputs) entries in Beckhoff's XML descriptions.

```yaml
symbol_nodes:
  - name_template: "Value {channel}"
    index_group: 61472       # ADS index group (0xF020 = 61472)
    size: 2                  # Data size in bytes
    ads_type: 2              # ADS data type (2=INT, 3=DINT, etc.)
    type_name: "INT"         # Data type name
    channels: 4              # Number of channels
    access: "Read-only"      # Access mode
    fastcs_name: "Value{channel}"  # PascalCase name for FastCS
```

### Symbol Node Properties

| Property | Description |
|----------|-------------|
| `name_template` | Name pattern supporting `{channel}` placeholder |
| `index_group` | ADS index group (61472=0xF020 for inputs, 61488=0xF030 for outputs) |
| `size` | Data size in bytes |
| `ads_type` | ADS data type code |
| `type_name` | Data type name (BOOL, INT, DINT, UINT, etc.) |
| `channels` | Number of channels (for multi-channel terminals) |
| `access` | Access mode: "Read-only" or "Read/Write" |
| `fastcs_name` | PascalCase name used for FastCS attribute naming |

### ADS Index Groups

| Index Group | Hex | Name | Purpose |
|-------------|-----|------|---------|
| 61472 | 0xF020 | RWIB | Input bytes (read/write) |
| 61473 | 0xF021 | RWIX | Input bits (read/write) |
| 61488 | 0xF030 | RWOB | Output bytes (read/write) |
| 61489 | 0xF031 | RWOX | Output bits (read/write) |

### CoE Objects

CANopen over EtherCAT objects for terminal configuration (optional):

```yaml
coe_objects:
  - index: 0x8000
    name: "Settings"
    type_name: "USINT"
    bit_size: 8
    access: "rw"
```

### Group Type

The terminal's functional group from the XML:

```yaml
group_type: AnaIn  # AnaIn, AnaOut, DigIn, DigOut, etc.
```

## ADS Runtime Symbols vs XML Definitions

When introspecting real hardware via ADS, you may see additional symbols that don't appear in the XML definitions, such as `WcState^WcState` or `InputToggle`. These are **ADS runtime symbols** added by the EtherCAT master, not terminal-specific PDO data.

### What are Runtime Symbols?

The `WcState^WcState` and similar symbols come from the **ADS runtime symbol table** when you query actual hardware. These are **EtherCAT Working Counter** status bits that the TwinCAT/ADS runtime adds dynamically to indicate whether each terminal is responding correctly on the EtherCAT bus.

### Known Runtime Symbols

TwinCAT adds these standardized diagnostic symbols to terminals:

| Symbol | Type | Size | Description |
|--------|------|------|-------------|
| `WcState^WcState` | BIT | 1 bit | Working Counter State - indicates if terminal is communicating properly on the EtherCAT bus |
| `InfoData^State` | UINT16 | 2 bytes | Device state information (EtherCAT state machine) |
| `InputToggle` | BIT | 1 bit | Toggles on each EtherCAT cycle to indicate data freshness |

These symbols are:
- **Mostly standardized** - similar across terminal types, but not all terminals have all symbols
- **Generated at runtime** - not defined in ESI XML files
- **Diagnostic in nature** - used for monitoring bus health, not process data

### Why aren't they in the XML?

Runtime symbols are **not** in the Beckhoff XML terminal description files because:

1. The XML files describe the **static hardware capabilities** of each terminal type (PDO mappings, CoE objects)
2. The WcState symbols are **runtime diagnostics** added by the EtherCAT master when it configures the bus
3. These symbols are added dynamically based on bus configuration, not terminal capabilities

### Runtime Symbols Configuration

Runtime symbols are defined in `src/fastcs_catio/terminals/runtime_symbols.yaml` using a schema similar to terminal symbol nodes, with additional filtering capabilities:

```yaml
runtime_symbols:
  - name_template: WcState^WcState
    index_group: 61473  # 0xF021 - RWIX (input bits)
    size: 0
    ads_type: 33  # BIT
    type_name: BIT
    channels: 1
    access: Read-only
    fastcs_name: WcstateWcstate
    description: Working Counter State - indicates bus communication status
    # Filtering options:
    group_blacklist:
      - Coupler  # Couplers may not have WcState
```

#### Filtering Options

Each runtime symbol can specify which terminals it applies to:

| Field | Description |
|-------|-------------|
| `whitelist` | Only apply to these specific terminal IDs (e.g., `["EL3004", "EL3104"]`) |
| `blacklist` | Exclude these specific terminal IDs |
| `group_whitelist` | Only apply to terminals in these groups (e.g., `["AnaIn", "DigIn"]`) |
| `group_blacklist` | Exclude terminals in these groups (e.g., `["Coupler"]`) |

If no filters are specified, the symbol applies to all terminals. Whitelist takes precedence over blacklist.

### Data Sources

| Source | Availability | Contains |
|--------|--------------|----------|
| XML (ESI files) | Downloadable from Beckhoff, scrapable | Static terminal capabilities, PDO mappings |
| Runtime Symbols | Defined in `runtime_symbols.yaml` | Dynamic diagnostics from EtherCAT master |

The runtime symbols are documented in Beckhoff InfoSys but the content uses heavy JavaScript rendering that makes it difficult to scrape programmatically. The relevant documentation pages are:

- [TwinCAT I/O Variables](https://infosys.beckhoff.com/content/1033/tc3_io_intro/1257993099.html)
- [EtherCAT Diagnosis](https://infosys.beckhoff.com/content/1033/ethercatsystem/2469122443.html)

### Key Differences

| Source | Contains | Examples |
|--------|----------|----------|
| XML (ESI files) | Static terminal capabilities, PDO mappings | `Value {channel}`, `Status__Error {channel}` |
| Runtime Symbols | Dynamic diagnostics from EtherCAT master | `WcState^WcState`, `InputToggle`, `InfoData^State` |

### Handling in catio-terminals

The catio-terminals editor separates XML-defined symbols from runtime symbols:

- **XML symbols**: Derived from Beckhoff ESI files, shown in the terminal editor
- **Runtime symbols**: Loaded from `runtime_symbols.yaml`, filtered per terminal based on whitelist/blacklist rules
- When merging YAML files with XML data, symbols not in XML or runtime symbols are dropped with a warning

The symbol expansion logic in `src/fastcs_catio/symbols.py` handles runtime symbol types when reading from actual hardware.

## Adding New Terminal Types

To add a new terminal type:

1. Launch `catio-terminals` and open the appropriate YAML file
2. Click "Add Terminal" and search for the terminal ID (e.g., "EL3104")
3. Select the symbols you want to include from the XML definition
4. Save the file

The terminal will be automatically available to the ADS simulator and FastCS integration.

## See Also

- [ADS Client Architecture](ads-client.md)
- [Architecture Overview](architecture-overview.md)
- Terminal type source files: `src/fastcs_catio/terminals/`
- catio-terminals documentation: `src/catio_terminals/README.md`
