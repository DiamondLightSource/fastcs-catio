# TODO

Outstanding tasks and improvements for CATio.

---

## 1. Client symbol_lookup should handle ADS_TYPE_UINT16

**Priority:** Medium
**Status:** Not Started

### Background

The client's `symbol_lookup` function in `src/fastcs_catio/symbols.py` only handles a limited set of ADS data types:

- `ADS_TYPE_BIT` (33)
- `ADS_TYPE_BIGTYPE` (65)
- `ADS_TYPE_UINT8` (17)

Symbols with other ADS types (e.g., `ADS_TYPE_UINT16 = 18`) are silently ignored with a warning log message.

### Problem

Real TwinCAT hardware returns symbols with `ADS_TYPE_UINT16` for:
- Device-level symbols: `Device 1 (EtherCAT).Inputs.Frm0State`, `SlaveCount`, `DevState`, etc.
- Runtime symbols: `InfoData.State` (device state from EtherCAT state machine)

These symbols are currently filtered out by the client, meaning they cannot be read or monitored.

### Current Workaround

In the simulator (`tests/ads_sim/ethercat_chain.py`):
1. Device-level symbols use `ADS_TYPE_BIT` (33) instead of `ADS_TYPE_UINT16` (18)
2. `total_symbol_count` property filters out symbols with unhandled ADS types to match client behavior

### Proposed Fix

Add handling for `ADS_TYPE_UINT16` (and potentially other integer types) in `symbol_lookup`:

```python
# In src/fastcs_catio/symbols.py, add case for UINT16:
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

### Files to Modify

- `src/fastcs_catio/symbols.py` - Add cases for `ADS_TYPE_UINT16`, `ADS_TYPE_INT16`, etc.

### After Implementation

1. Update simulator device-level symbols to use correct `ADS_TYPE_UINT16`
2. Remove `ADS_TYPE_BIT` workaround from `get_device_symbols()` in `tests/ads_sim/ethercat_chain.py`
3. Update `total_symbol_count` to include UINT16 symbols
4. Verify with real hardware that UINT16 symbols are readable

### Related

- Simulator symbol alignment plan: [simulator-symbol-alignment.md](simulator-symbol-alignment.md)
- Runtime symbols config: `src/catio_terminals/config/runtime_symbols.yaml`
