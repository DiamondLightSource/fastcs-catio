# Useful Notes on ADS and TwinCAT

This document collects important insights about the ADS (Automation Device Specification) protocol and TwinCAT systems, particularly as they relate to terminal configuration.

## 1. Two Ways ADS Accesses Data

### 1.1 By Symbol Name

ADS can read/write data using symbolic names that match entries in TwinCAT's symbol table. There are two ways to address symbols:

#### Full Name (using caret `^` separator)

The complete path from the TwinCAT I/O tree root:

```
TIID^Device 1 (EtherCAT)^Term 53 (EK1100)^Term 55 (EL1014)^Channel 1^Input
```

This includes the full hierarchy: `TIID` (TwinCAT I/O ID) → EtherCAT device → parent coupler → terminal → PDO → Entry.

#### Symbol Info (using port and dot `.` separator)

A shorter form using the AMS port number and a dot-separated path from the terminal:

```
Port: 27905, 'Term 55 (EL1014).Channel 1.Input'
```

This form uses:
- **Port number**: Identifies the EtherCAT master/device
- **Terminal name**: e.g., `Term 55 (EL1014)`
- **PDO name**: e.g., `Channel 1`
- **Entry name**: e.g., `Input`

**Requirements:**
- The symbol name must **exactly match** what TwinCAT has in its symbol table
- TwinCAT generates these names based on the project configuration

**Advantages:**
- Self-documenting code
- Easier to understand and maintain
- Symbol table provides type information

**Disadvantages:**
- Requires symbol table to be available
- Names must match exactly - no flexibility
- Symbol table lookup adds overhead

### 1.2 By Index Group + Offset

ADS can also access data directly using numeric addresses:

- **Index Group**: Identifies the memory region (e.g., `0xF020` for inputs, `0xF030` for outputs)
- **Index Offset**: Byte offset within that region

**Example:**
```python
# Read 2 bytes from input area at offset 0
client.read(index_group=0xF020, index_offset=0, length=2)
```

**Advantages:**
- No symbol table required
- Direct memory access - faster
- Works even without TwinCAT project symbols

**Disadvantages:**
- Harder to understand (magic numbers)
- Must know exact memory layout
- No automatic type checking

## 2. Constructing ADS Symbol Names from ESI XML

The Beckhoff ESI (EtherCAT Slave Information) XML files contain PDO (Process Data Object) definitions that can be used to construct valid ADS symbol names.

### XML Structure

```xml
<TxPdo>
  <Name>Channel 1</Name>
  <Entry>
    <Name>Input</Name>
    <DataType>BOOL</DataType>
  </Entry>
</TxPdo>
```

### Symbol Name Construction

The ADS symbol name (Symbol Info form) can be constructed as:

```
{terminal_name}.{PDO_name}.{Entry_name}
```

Where:
- **terminal_name**: Discovered at runtime from the EtherCAT chain (e.g., `Term 55 (EL1014)`)
- **PDO_name**: From XML `<TxPdo><Name>` or `<RxPdo><Name>` (e.g., `Channel 1`)
- **Entry_name**: From XML `<Entry><Name>` (e.g., `Input`)

**Example:**
```
Term 55 (EL1014).Channel 1.Input
```

### What catio-terminals Stores

The terminal YAML files store the **suffix** portion (PDO name + Entry name) that gets combined with the runtime-discovered terminal name:

```yaml
# The name_template stores: {PDO_name}.{Entry_name}
# with {channel} placeholder for multi-channel terminals
- name_template: Channel {channel}.Input
  type_name: BOOL
  channels: 4
```

At runtime, FastCS will:
1. Discover the EtherCAT chain and terminal names
2. Combine terminal name with the `name_template` to form the full symbol
3. Use the AMS port to address the correct EtherCAT master

### Why This Approach Works

1. **XML provides the suffix** - PDO name and Entry name are exactly what TwinCAT uses
2. **Runtime provides the prefix** - Terminal name comes from discovering the chain
3. **YAML filters what we scan** - Only selected symbols from XML end up in YAML
4. **No hardcoded offsets needed** - We use symbol-based ADS access exclusively

## Common Index Groups for EtherCAT I/O

| Index Group | Hex      | Description |
|-------------|----------|-------------|
| 61472       | 0xF020   | Input process data (bytes) |
| 61473       | 0xF021   | Input process data (bits) |
| 61488       | 0xF030   | Output process data (bytes) |
| 61489       | 0xF031   | Output process data (bits) |

## References

- [Beckhoff ADS Protocol Documentation](https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/index.html)
- [TwinCAT Symbol Access](https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_adssamples_python/index.html)
