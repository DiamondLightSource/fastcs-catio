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

## 3. Limitation: XML Does Not Determine Active PDO Configuration

### The Problem

The ESI XML files define **all possible** PDO configurations for a terminal, but TwinCAT may use a **different configuration** than what we infer from the XML. This means we cannot reliably determine the actual ADS symbol names just from the terminal type.

### Example: EL1502 Counter Terminal

The EL1502 is a 2-channel counter terminal. Its ESI XML defines multiple PDO options:

```xml
<!-- Per-channel PDOs -->
<TxPdo>
  <Name>CNT Inputs Channel 1</Name>
  <Entry><Name>Output functions enabled</Name>...</Entry>
  <Entry><Name>Counter value</Name>...</Entry>
</TxPdo>
<TxPdo>
  <Name>CNT Inputs Channel 2</Name>
  ...
</TxPdo>

<!-- Combined PDO (no channel number) -->
<TxPdo>
  <Name>CNT Inputs</Name>
  <Entry><Name>Output functions enabled</Name>...</Entry>
  <Entry><Name>Counter value</Name>...</Entry>
</TxPdo>
```

Our XML parser sees "Channel 1" and "Channel 2" PDOs and infers symbols like:
```
CNT Inputs Channel {channel}.Output functions enabled
```

But TwinCAT may be configured to use the **combined PDO**, resulting in actual symbols like:
```
Term 92 (EL1502).CNT Inputs.Output functions enabled
```

### Why This Happens

1. **ESI XML is a capability description** - It lists all PDO configurations the terminal *supports*
2. **TwinCAT project chooses the configuration** - The actual PDO mapping is determined by the TwinCAT project settings
3. **Default configurations vary** - Different terminals may default to different PDO variants

### Implications for catio-terminals

This limitation means:

1. **Symbol names from XML may not match TwinCAT** - The symbols we generate may not exist in the actual TwinCAT symbol table
2. **Per-terminal verification needed** - Users may need to verify/adjust symbol names against their actual TwinCAT configuration
3. **Future enhancement needed** - A more robust solution would query the actual TwinCAT symbol table at runtime rather than inferring from XML

### Example: EL3702 Oversampling Terminal

The EL3702 is a 2-channel analog input terminal that supports **oversampling** - capturing multiple samples per cycle. The ESI XML reveals extensive configurability:

```xml
<TxPdo OSFac="20" OSMin="1" OSMax="100" OSIndexInc="16">
  <Name>AI Inputs Channel 1</Name>
  <Entry>
    <Name>Value</Name>
    <DataType>INT</DataType>
  </Entry>
</TxPdo>
```

The XML attributes indicate:
- **OSMin="1"** - Minimum 1 sample per cycle
- **OSMax="100"** - Maximum 100 samples per cycle
- **OSFac="20"** - Oversampling factor (internal timing)

Additionally, the XML defines multiple **Operation Modes**:

```xml
<OpMode>
  <Name>DcSync</Name>
  <Desc>DC-Synchronous with variable Oversampling</Desc>
</OpMode>
<OpMode>
  <Name>DcSync2</Name>
  <Desc>DC-Synchronous 2x Oversampling</Desc>
</OpMode>
<!-- DcSync3, DcSync4, DcSync5, DcSync8, DcSync10 also defined -->
```

And TwinCAT-specific vendor extensions:

```xml
<Oversampling DefaultFactor="10" MinCycleTime="10000"/>
```

**The problem**: Our XML parser only sees the template PDO with a single `Value` entry. But at runtime, TwinCAT will create symbols based on the configured sample count:

| Configuration | Actual Symbols Created |
|---------------|----------------------|
| 1x (no oversampling) | `Term 60 (EL3702).AI Inputs Channel 1.Value` |
| 10x oversampling | `Term 60 (EL3702).AI Inputs Channel 1.Samples[0..9]` (or similar) |
| 100x oversampling | 100 sample values per channel |

The XML defines **capabilities** (1-100 samples), but the TwinCAT project determines **actual configuration**.

### Workarounds

1. **Manual verification** - Compare generated YAML against TwinCAT's symbol browser
2. **Runtime symbol discovery** - Query TwinCAT's symbol table to discover actual symbols
3. **User override** - Allow users to manually edit symbol names in the YAML files

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
