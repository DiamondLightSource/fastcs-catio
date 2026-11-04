# TODO

Outstanding tasks and improvements for CATio.

## Client symbol_lookup should handle ADS_TYPE_UINT16

**Priority:** Medium
**Status:** Not Started

### Background

The `symbol_lookup` function in `src/fastcs_catio/symbols.py` only handles these ADS data types:

- `ADS_TYPE_BIT` (33)
- `ADS_TYPE_BIGTYPE` (65)
- `ADS_TYPE_UINT8` (17)

Symbols with other types (e.g., `ADS_TYPE_UINT16 = 18`) are silently ignored.

### Problem

Real TwinCAT hardware returns symbols with `ADS_TYPE_UINT16` for:
- Device-level symbols: `Device 1 (EtherCAT).Inputs.Frm0State`, `SlaveCount`, `DevState`
- Runtime symbols: `InfoData.State` (EtherCAT state machine)

### Proposed Fix

Add handling for `ADS_TYPE_UINT16` in `symbol_lookup`:

```python
case AdsDataType.ADS_TYPE_UINT16:
    symbols.append(
        AdsSymbol(
            parent_id=node.parent_id,
            name=node.name,
            dtype=np.uint16,
            size=2,
            group=node.index_group,
            offset=node.index_offset,
            comment=add_comment(
                "Value symbol for a 2 byte unsigned integer.",
                node.comment,
            ),
        )
    )
```

### Files

- `src/fastcs_catio/symbols.py` - Add cases for UINT16 and other integer types
