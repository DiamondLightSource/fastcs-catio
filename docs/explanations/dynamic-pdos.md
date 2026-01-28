# Dynamic PDOs in EtherCAT Terminals

This document explains the concept of dynamic PDO (Process Data Object) configurations in Beckhoff EtherCAT terminals, why they exist, and how `catio-terminals` handles them.

## Background: Static vs Dynamic PDOs

Most EtherCAT terminals have a **static PDO configuration** - the process data structure is fixed and predictable. For example, an EL2024 (4-channel digital output) always has exactly 4 boolean outputs, and an EL3202 (2-channel PT100 input) always has the same structure per channel.

However, some terminals have **dynamic PDO configurations** that depend on:

- TwinCAT project settings
- Selected operation mode
- Oversampling factor
- PDO assignment choices

For these terminals, the exact PDO layout cannot be determined from the ESI XML alone - it varies based on how the terminal is configured in the TwinCAT project.

## Types of Dynamic PDO Configurations

### Type 1: Configuration Variants

Some terminals offer alternative PDO structures for the same function. For example, the EL1502 (2-channel up/down counter) can be configured as:

| Configuration | PDO Names | Symbol Pattern |
|---------------|-----------|----------------|
| Per-channel | `CNT Inputs Channel 1`, `CNT Inputs Channel 2` | `CNT Inputs Channel {n}.Counter value` |
| Combined | `CNT Inputs` | `CNT Inputs.Counter value` |

The XML defines **both** configurations, but only one will be active at runtime.

### Type 2: Standard vs Compact PDO Selection

Analog input terminals like EL3104, EL3124, EP3174-0002, and EP4374-0002 offer two PDO formats per channel:

| Format | PDO Name Pattern | Contents |
|--------|------------------|----------|
| Standard | `AI Standard Channel {n}` | Status word (underrange, overrange, limits, error) + Value |
| Compact | `AI Compact Channel {n}` | Value only (no status) |

The TwinCAT project selects one format per channel. Both are defined in XML as optional.

### Type 3: Multi-Format Terminals

Terminals like the EL3356-0010 (precision resistor bridge) offer multiple data formats:

| Format | PDO Name | Data Type |
|--------|----------|-----------|
| INT32 | `RMB Value (INT32)` | DINT (32-bit signed) |
| Real | `RMB Value (Real)` | REAL (32-bit float) |
| Standard Ch1/Ch2 | `AI Standard Channel {n}` | Status + DINT value |
| Compact Ch1/Ch2 | `AI Compact Channel {n}` | DINT value only |

Additionally, there are optional PDOs for `RMB Status`, `RMB Timestamp`, and `RMB Control`.

### Type 4: Oversampling Terminals

Oversampling terminals like EL3702, EL4732, and ELM3704-0000 have a configurable number of samples per channel (1-100). The XML shows only a template, but the actual symbol count depends on the configured oversampling factor.

The ELM3704-0000 is particularly complex - each of its 4 channels can have:
- Different data formats: INT16, INT32 (DINT), or REAL32
- Different oversampling factors: 1, 2, 4, 5, 8, 10, 16, 20, 25, 32, 40, 50, 64, 80, or 100 samples

The XML defines 192 TxPDOs (48 per channel) to cover all combinations.

## How Dynamic PDOs are Defined in ESI XML

Beckhoff's ESI XML files indicate dynamic PDO configurations using the `<AlternativeSmMapping>` element within the `<VendorSpecific>/<TwinCAT>` section.

### The AlternativeSmMapping Element

Each `<AlternativeSmMapping>` element defines a mutually exclusive PDO configuration. The `Default="1"` attribute marks which configuration is active by default.

**Example from EL3104:**

```xml
<VendorSpecific>
  <TwinCAT>
    <AlternativeSmMapping Default="1">
      <Name>Standard</Name>
      <Sm No="3">
        <Pdo>#x1a00</Pdo> <!-- AI Standard Channel 1 -->
        <Pdo>#x1a02</Pdo> <!-- AI Standard Channel 2 -->
        <Pdo>#x1a04</Pdo> <!-- AI Standard Channel 3 -->
        <Pdo>#x1a06</Pdo> <!-- AI Standard Channel 4 -->
      </Sm>
    </AlternativeSmMapping>
    <AlternativeSmMapping>
      <Name>Compact</Name>
      <Sm No="3">
        <Pdo>#x1a01</Pdo> <!-- AI Compact Channel 1 -->
        <Pdo>#x1a03</Pdo> <!-- AI Compact Channel 2 -->
        <Pdo>#x1a05</Pdo> <!-- AI Compact Channel 3 -->
        <Pdo>#x1a07</Pdo> <!-- AI Compact Channel 4 -->
      </Sm>
    </AlternativeSmMapping>
  </TwinCAT>
</VendorSpecific>
```

This structure indicates that:
1. The terminal has two exclusive modes: "Standard" and "Compact"
2. "Standard" is the default (marked with `Default="1"`)
3. Each mode uses different PDO indices

### PDO Exclude Elements

Some terminals (like EL1502) use a different approach to define mutually exclusive PDOs - the `<Exclude>` element within each PDO. This is more commonly used for per-channel vs combined mode selection.

**Example from EL1502:**

```xml
<TxPdo>
  <Index>#x1a00</Index>
  <Name>CNT Inputs Channel 1</Name>
  <Exclude>#x1a02</Exclude>  <!-- Excludes the combined PDO -->
</TxPdo>
<TxPdo>
  <Index>#x1a01</Index>
  <Name>CNT Inputs Channel 2</Name>
  <Exclude>#x1a02</Exclude>  <!-- Excludes the combined PDO -->
</TxPdo>
<TxPdo>
  <Index>#x1a02</Index>
  <Name>CNT Inputs</Name>
  <Exclude>#x1a00</Exclude>  <!-- Excludes channel 1 -->
  <Exclude>#x1a01</Exclude>  <!-- Excludes channel 2 -->
</TxPdo>
```

This exclusion graph defines two groups:
- **Per-Channel**: `#x1a00` + `#x1a01` (each channel separate)
- **Combined**: `#x1a02` (both channels in one PDO)

### Sync Manager Assignment

The `<Sm No="3">` element indicates which Sync Manager the PDOs are assigned to:
- SM2 (Sm No="2"): RxPDO outputs
- SM3 (Sm No="3"): TxPDO inputs

## Terminals at Diamond Light Source

The following table categorizes terminals used at Diamond Light Source by their PDO type:

| Terminal | Description | PDO Type |
|----------|-------------|----------|
| EK1100 | EtherCAT Coupler | None |
| EK1122 | 2 Port EtherCAT Junction | None |
| EL1014 | 4Ch Digital Input 24V, 10us | Static |
| EL1084 | 4Ch Digital Input 24V, 3ms, negative | Static |
| EL1124 | 4Ch Digital Input 5V, 10us | Static |
| EL1502 | 2Ch Up/Down Counter 24V, 100kHz | **Dynamic Type 1** |
| EL2024 | 4Ch Digital Output 24V, 2A | Static |
| EL2124 | 4Ch Digital Output 5V, 20mA | Static |
| EL3104 | 4Ch Analog Input +/-10V Diff | **Dynamic Type 2** |
| EL3124 | 4Ch Analog Input 4-20mA Diff | **Dynamic Type 2** |
| EL3202 | 2Ch Analog Input PT100 (RTD) | Static |
| EL3314 | 4Ch Analog Input Thermocouple | Static |
| EL3356-0010 | 1Ch Resistor Bridge, 16bit High Precision | **Dynamic Type 3** |
| EL3602 | 2Ch Analog Input +/-10V Diff, 24bit | Static |
| EL3702 | 2Ch Analog Input +/-10V Oversample | **Dynamic Type 4** |
| EL4134 | 4Ch Analog Output +/-10V, 16bit | Static |
| EL4732 | 2Ch Analog Output +/-10V Oversample | **Dynamic Type 4** |
| ELM3704-0000 | 4Ch Universal Analog Input, 24bit | **Dynamic Type 4** |
| EP3174-0002 | 4Ch Analog Input configurable | **Dynamic Type 2** |
| EP4374-0002 | 2Ch AI + 2Ch AO configurable | **Dynamic Type 2** |

## Runtime Discovery

For terminals with dynamic PDOs, the actual configuration must be queried from the TwinCAT symbol table at runtime:

```python
async with CatioClient(target_ip="192.168.1.100") as client:
    # Discover EtherCAT devices
    await client.get_ethercat_devices()

    # Get all symbols from the symbol table
    all_symbols = await client.get_all_symbols()

    # Symbols are keyed by device ID
    for device_id, symbols in all_symbols.items():
        for symbol in symbols:
            print(f"{symbol.name}: {symbol.type_name}")
```

## Implementation in catio-terminals

The `catio-terminals` tool supports dynamic PDO configurations through a grouping mechanism that:

1. **Parses AlternativeSmMapping** from the ESI XML to identify PDO groups
2. **Falls back to PDO Exclude elements** for terminals like EL1502 that use exclusion-based grouping
3. **Tracks which symbols belong to which PDO group**
4. **Provides a GUI selector** to choose the active PDO group
5. **Filters symbols** based on the selected group

### Data Model

The data models for PDO groups are defined in [models.py](../../src/catio_terminals/models.py):

- `PdoGroup`: Represents a group of mutually exclusive PDOs, storing the group name, default flag, PDO indices, and corresponding symbol indices.
- `TerminalType`: Extended with `pdo_groups` and `selected_pdo_group` fields, plus helper properties like `has_dynamic_pdos` and `get_active_symbol_indices()`.

### XML Parsing

The `xml_pdo_groups.py` module handles parsing of PDO group definitions using two methods:

**Method 1: AlternativeSmMapping (preferred)**

```python
def parse_pdo_groups(device: _Element) -> list[PdoGroup]:
    """Parse PDO groups from device XML.
    
    Tries AlternativeSmMapping first, then falls back to Exclude elements.
    """
    # Find VendorSpecific/TwinCAT/AlternativeSmMapping elements
    # Extract group name, default flag, and PDO indices
    # Return list of PdoGroup instances
```

**Method 2: PDO Exclude Elements (fallback)**

For terminals like EL1502 that use `<Exclude>` elements instead of `AlternativeSmMapping`, the parser:

1. Builds an exclusion graph from all PDO Exclude elements
2. Identifies "Combined" PDOs (those that exclude 2+ other PDOs)
3. Identifies "Per-Channel" PDOs (those excluded by Combined PDOs)
4. Creates two PDO groups: "Per-Channel" (default) and "Combined"

```python
def assign_symbols_to_groups(
    pdo_groups: list[PdoGroup],
    symbol_pdo_mapping: dict[int, int],
) -> None:
    """Assign symbol indices to their corresponding PDO groups."""
    # Maps each symbol to its source PDO index
    # Updates PdoGroup.symbol_indices accordingly
```

The PDO index is tracked during symbol node creation, allowing each symbol to be associated with its source PDO and thus its PDO group.

### GUI Integration

When a terminal has dynamic PDOs, the `catio-terminals` editor displays:

1. **A PDO Configuration dropdown** showing available groups (e.g., "Standard", "Compact")
2. **Filtered symbol tree** showing only symbols in the selected group
3. **Visual indicator** of the default group

Changing the selected group updates which symbols are displayed and available for selection.

### YAML Serialization

PDO groups are serialized in the terminal YAML when present:

```yaml
EL3104:
  description: 4Ch Analog Input +/-10V Diff
  identity:
    vendor_id: 2
    product_code: 203427920
    revision_number: 1114112
  pdo_groups:
    - name: Standard
      is_default: true
      pdo_indices: [0x1a00, 0x1a02, 0x1a04, 0x1a06]
      symbol_indices: [0, 1, 2, 3]
    - name: Compact
      is_default: false
      pdo_indices: [0x1a01, 0x1a03, 0x1a05, 0x1a07]
      symbol_indices: [4, 5, 6, 7]
  selected_pdo_group: Standard
  symbol_nodes:
    # ... symbols for all groups, filtered by selected_pdo_group
```

### Default Group Selection

When loading a new terminal from XML:
1. Parse AlternativeSmMapping to find PDO groups
2. Identify the default group (marked with `Default="1"`)
3. Set `selected_pdo_group` to the default group name
4. Pre-select only symbols belonging to the default group

This ensures new terminals start with a sensible default configuration matching what TwinCAT would use.

## See Also

- [Terminal YAML Definitions](terminal-yaml-definitions.md) - How terminal definitions are structured
- [Useful Notes on ADS and TwinCAT](useful_notes_ads_twincat.md) - Details on ADS access methods
