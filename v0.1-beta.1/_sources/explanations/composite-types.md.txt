# Composite Types in TwinCAT

This document explains how TwinCAT generates composite type names and how they are implemented in the catio-terminals codebase. It complements the [Terminal YAML Definitions](terminal-yaml-definitions.md) document.

## What Are Composite Types?

In TwinCAT's ADS (Automation Device Specification) protocol, a **composite type** (also called BIGTYPE, ads_type=65) is a structured data type that groups multiple primitive fields together. When you introspect an EtherCAT terminal's symbol table, some symbols return these composite types instead of primitives.

For example, an analog input channel on an EL3104 terminal returns a composite type containing:
- `Status` (UINT, 2 bytes) - Status flags for the channel
- `Value` (INT, 2 bytes) - The actual analog value

## XML vs TwinCAT Runtime

### What Beckhoff's XML Contains

Beckhoff's ESI (EtherCAT Slave Information) XML files define **PDO entries** as individual fields:

```xml
<TxPdo Fixed="1">
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
        <DataType>INT</DataType>
    </Entry>
</TxPdo>
```

The XML does **NOT** contain:
- Composite type names (e.g., `"AI Standard Channel 1_TYPE"`)
- How fields are grouped into structures
- ADS symbol table layout

### What TwinCAT Generates

When TwinCAT compiles an EtherCAT configuration, it creates composite types by:

1. Taking the PDO name (e.g., `"AI Standard Channel 1"`)
2. Appending `"_TYPE"` to create the type name
3. Grouping the PDO entries into a structure

**PDO Name** → **Type Name**
- `"AI Standard Channel 1"` → `"AI Standard Channel 1_TYPE"`
- `"CNT Inputs Channel 1"` → `"CNT Inputs Channel 1_TYPE"`
- `"AO Output Channel 1"` → `"AO Output Channel 1_TYPE"`

## Implementation in catio-terminals

### composite_types.yaml

Since the XML doesn't contain composite type definitions, we maintain them in a shared configuration file:

```yaml
# src/catio_terminals/config/composite_types.yaml

composite_types:
  "AI Standard Channel 1_TYPE":
    description: "16-bit analog input channel (status + value)"
    ads_type: 65  # BIGTYPE
    size: 4
    members:
      - name: Status
        offset: 0
        type_name: UINT
        size: 2
        fastcs_attr: Status
        access: read-only
      - name: Value
        offset: 2
        type_name: INT
        size: 2
        fastcs_attr: Value
        access: read-only
```

### Pydantic Models

The composite types are represented by Pydantic models in `models.py`:

```python
class CompositeTypeMember(BaseModel):
    """A member field within a composite type."""
    name: str
    offset: int
    type_name: str
    size: int
    fastcs_attr: str
    access: str = "read-only"

class CompositeType(BaseModel):
    """A composite type definition (TwinCAT BIGTYPE structure)."""
    description: str
    ads_type: int = 65
    size: int
    members: list[CompositeTypeMember]

class CompositeTypesConfig(BaseModel):
    """Configuration for composite type definitions."""
    composite_types: dict[str, CompositeType]

    @classmethod
    def get_default(cls) -> "CompositeTypesConfig":
        """Load the default composite types from the package."""
        ...
```

### Usage in the Codebase

#### 1. ADS Simulator

The simulator uses composite types to generate accurate symbol table responses. When a test queries the symbol table, it returns the correct TwinCAT type name:

```python
composite_types = CompositeTypesConfig.get_default()
if composite_types.is_composite(symbol.type_name):
    # Return the TwinCAT type name for the symbol
    ...
```

#### 2. FastCS Controller Generation

The FastCS generator uses composite type members to create controller attributes:

```python
composite_type = composite_types.get_type(symbol.type_name)
if composite_type:
    for member in composite_type.members:
        # Create a FastCS attribute for each member
        # e.g., Channel1_Status, Channel1_Value
        ...
```

#### 3. UI Display

The catio-terminals GUI displays composite types with their members nested:

```
▼ AI Standard Channel {channel} (Composite)
    Type: AI Standard Channel 1_TYPE
    Total Size: 4 bytes
    ▼ Members (2)
        ▼ Status (UINT)
            Offset: 0 bytes
            Size: 2 bytes
        ▼ Value (INT)
            Offset: 2 bytes
            Size: 2 bytes
```

## Type Name Patterns

TwinCAT follows consistent patterns for type names:

| PDO Category | PDO Name Pattern | Type Name Pattern |
|--------------|------------------|-------------------|
| Analog Input | `AI Standard Channel N` | `AI Standard Channel 1_TYPE` |
| Analog Input (24-bit) | `AI Inputs Channel N` | `AI Inputs Channel 1_TYPE` |
| Analog Output | `AO Output Channel N` | `AO Output Channel 1_TYPE` |
| Counter | `CNT Inputs Channel N` | `CNT Inputs Channel 1_TYPE` |
| Digital I/O | `Inputs Channel N` | `Inputs Channel 1_TYPE` |

Note that the type name always uses `1` (or the first channel number) regardless of which channel is being accessed. This is because TwinCAT creates one type definition that's shared across all channels.

## Adding New Composite Types

When adding support for a new terminal type:

1. **Check the XML** - Look at the PDO entries to understand the structure
2. **Inspect a live system** - If possible, query a TwinCAT system to get exact type names
3. **Add to composite_types.yaml** - Define the type with all members, offsets, and sizes
4. **Test** - Verify the simulator returns correct responses

### Example: Adding a New Type

```yaml
# For a hypothetical EL9999 with custom structure
"Custom Data Channel 1_TYPE":
  description: "Custom data channel for EL9999"
  ads_type: 65
  size: 8
  members:
    - name: Flags
      offset: 0
      type_name: UINT
      size: 2
      fastcs_attr: Flags
      access: read-only
    - name: Value1
      offset: 2
      type_name: INT
      size: 2
      fastcs_attr: Value1
      access: read-only
    - name: Value2
      offset: 4
      type_name: DINT
      size: 4
      fastcs_attr: Value2
      access: read-only
```

## Related Documentation

- [Terminal YAML Definitions](terminal-yaml-definitions.md) - YAML file structure and symbol nodes
- [Beckhoff XML Format](../reference/beckhoff-xml-format.md) - ESI XML schema reference
- [Architecture Overview](architecture-overview.md) - Overall system design
