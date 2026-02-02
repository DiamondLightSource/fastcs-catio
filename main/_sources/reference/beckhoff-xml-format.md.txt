# Beckhoff ESI XML File Format

This document describes the structure and naming conventions of Beckhoff EtherCAT Slave Information (ESI) XML files, which are used by `catio-terminals` to extract terminal definitions.

## XML File Organization

Beckhoff distributes ESI files as a single ZIP archive (`Beckhoff_EtherCAT_XML.zip`) containing multiple XML files. Each file groups terminals by series:

| XML Filename | Terminal Series | Examples |
|--------------|-----------------|----------|
| `Beckhoff EL1xxx.xml` | Digital Input | EL1004, EL1008, EL1124 |
| `Beckhoff EL2xxx.xml` | Digital Output | EL2004, EL2008, EL2124 |
| `Beckhoff EL31xx.xml` | Analog Input (basic) | EL3104, EL3124 |
| `Beckhoff EL32xx.xml` | Analog Input (thermocouple) | EL3202, EL3204 |
| `Beckhoff EL4xxx.xml` | Analog Output | EL4002, EL4004 |
| `Beckhoff EL5xxx.xml` | Position Measurement | EL5001, EL5101 |
| `Beckhoff EL6xxx.xml` | Communication | EL6001, EL6021 |
| `Beckhoff EL9xxx.xml` | Power Supply | EL9100, EL9410 |

### Cache Location

The `catio-terminals` tool caches downloaded XML files at:
```
~/.cache/catio_terminals/beckhoff_xml/
```

Use `catio-terminals update-cache` to download or refresh the cache.

## XML Schema Overview

Each ESI XML file follows the EtherCAT standard schema. The key elements relevant to terminal definitions are:

### Root Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<EtherCATInfo>
  <Vendor>
    <Id>#x0002</Id>
    <Name>Beckhoff Automation GmbH</Name>
  </Vendor>
  <Descriptions>
    <Groups>...</Groups>
    <Devices>
      <Device>...</Device>
      <Device>...</Device>
    </Devices>
  </Descriptions>
</EtherCATInfo>
```

### Device Element

Each terminal is represented as a `<Device>` element:

```xml
<Device>
  <Type ProductCode="#x0C203052" RevisionNo="#x00100000">EL3104</Type>
  <Name LcId="1033">EL3104 4-channel Analog Input +/-10V 16-bit</Name>
  <GroupType>AnaIn</GroupType>

  <!-- Process Data Objects (PDOs) -->
  <TxPdo>...</TxPdo>  <!-- Inputs to controller -->
  <RxPdo>...</RxPdo>  <!-- Outputs from controller -->

  <!-- CoE Objects (CANopen over EtherCAT) -->
  <Profile>
    <Dictionary>
      <DataTypes>...</DataTypes>
      <Objects>...</Objects>
    </Dictionary>
  </Profile>
</Device>
```

### Identity Attributes

The `<Type>` element contains critical identity information:

| Attribute | Format | Description |
|-----------|--------|-------------|
| `ProductCode` | `#x0C203052` | Unique product identifier (hex) |
| `RevisionNo` | `#x00100000` | Firmware revision (hex) |

These map directly to the `identity` section in terminal YAML files.

### PDO Entries

Process Data Objects define the I/O structure. Each PDO contains entries:

```xml
<TxPdo Fixed="1" Sm="3">
  <Index>#x1a02</Index>
  <Name>AI Standard Channel 1</Name>
  <Entry>
    <Index>#x6000</Index>
    <SubIndex>1</SubIndex>
    <BitLen>1</BitLen>
    <Name>Status__Underrange</Name>
    <DataType>BOOL</DataType>
  </Entry>
  <Entry>
    <Index>#x6000</Index>
    <SubIndex>17</SubIndex>
    <BitLen>16</BitLen>
    <Name>Value</Name>
    <DataType DScale="+/-10">INT</DataType>
  </Entry>
</TxPdo>
```

Key observations:
- **PDO Name**: `"AI Standard Channel 1"` - this becomes the composite type base name
- **Entry Names**: Individual fields like `Status__Underrange`, `Value`
- **DataType**: Primitive types (BOOL, INT, UINT, etc.)
- **BitLen**: Size in bits

### Data Types Section

The `<DataTypes>` section defines primitive and complex types:

```xml
<DataTypes>
  <DataType>
    <Name>BOOL</Name>
    <BitSize>1</BitSize>
  </DataType>
  <DataType>
    <Name>INT</Name>
    <BitSize>16</BitSize>
  </DataType>
  <DataType>
    <Name>DT0800EN03</Name>
    <BaseType>USINT</BaseType>
    <BitSize>3</BitSize>
    <EnumInfo>
      <Text>Signed</Text>
      <Value>0</Value>
    </EnumInfo>
  </DataType>
</DataTypes>
```

### CoE Objects

CANopen over EtherCAT objects provide configuration parameters:

```xml
<Objects>
  <Object>
    <Index>#x8000</Index>
    <Name>AI Settings Channel 1</Name>
    <Type>DT8000</Type>
    <SubItem>
      <SubIdx>1</SubIdx>
      <Name>Enable user scale</Name>
      <Type>BOOL</Type>
      <BitSize>1</BitSize>
      <Flags><Access>rw</Access></Flags>
    </SubItem>
  </Object>
</Objects>
```

## Mapping to Terminal YAML

The XML parser (`xml_parser.py`) transforms ESI data into terminal YAML:

| XML Element | YAML Field |
|-------------|------------|
| `Type@ProductCode` | `identity.product_code` |
| `Type@RevisionNo` | `identity.revision_number` |
| `Name` (device) | `description` |
| `GroupType` | `group_type` |
| PDO entries | `symbol_nodes[]` |
| CoE objects | `coe_objects[]` |

### Channel Pattern Detection

The parser detects channel patterns in PDO names:
- `"AI Standard Channel 1"` → template: `"AI Standard Channel {channel}"`, channels: 4
- `"Value 1"` → template: `"Value {channel}"`, channels: N

## What XML Does NOT Contain

The ESI XML files do **not** include:

1. **Composite type names**: TwinCAT generates names like `"AI Standard Channel 1_TYPE"` at compile time
2. **ADS index offsets**: Runtime memory layout is determined by TwinCAT
3. **Symbol table structure**: ADS symbols are TwinCAT constructs, not EtherCAT standard

These must be obtained from a live TwinCAT system or defined in `composite_types.yaml`.

## Related Documentation

- [Terminal Definitions](../explanations/terminal-definitions.md) - YAML file structure
- [Composite Types](../explanations/composite-types.md) - TwinCAT type generation
- [catio-terminals README](https://github.com/DiamondLightSource/fastcs-catio/tree/main/src/catio_terminals) - Tool usage
