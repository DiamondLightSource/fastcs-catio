---
orphan: true
---

# Plan: Align Simulator Symbols with Real Hardware

**Created:** 2026-01-27
**Updated:** 2026-01-28
**Status:** ✅ **Complete** - Simulator symbol count matches hardware (550 symbols)
**Related files:**
- [tests/ads_sim/ethercat_chain.py](../../tests/ads_sim/ethercat_chain.py) - Symbol generation logic
- [tests/ads_sim/server_config.yaml](../../tests/ads_sim/server_config.yaml) - Device/slave configuration
- [tests/diagnose_hardware.py](../../tests/diagnose_hardware.py) - Hardware comparison tool

## Problem Summary

The ADS simulator now generates symbols that exactly match real TwinCAT hardware:
1. ~~Symbol naming convention~~ ✅ Fixed
2. ~~Missing device-level symbols~~ ✅ Fixed
3. ~~Missing per-terminal WcState symbols~~ ✅ Fixed
4. ~~Index group assignments~~ ✅ Fixed
5. ~~Extra/different symbols per terminal type~~ ✅ Fixed (resolved by fixes 1-4, 6)
6. ~~Missing SyncUnits global symbol~~ ✅ Fixed

| Metric | Simulator (Before) | Simulator (After) | Hardware |
|--------|-----------|-----------|----------|
| Total Symbols | 1091 | 550 ✅ | 550 |
| Naming Format | `TIID^Device 1 (EtherCAT)^Term X^...` | `Term X (type).Channel Y` ✅ | `Term X (type).Channel Y` |
| Device Symbols | 0 | 8 ✅ | 8 |
| Global Symbols | 0 | 1 ✅ | 1 (SyncUnits) |
| Per-Terminal Runtime | 0 | 140+ ✅ | 140+ (WcState, InputToggle) |

---

## Issues and Tasks

### Issue 1: Symbol Naming Convention
**Priority:** High
**Status:** [x] Complete (2026-01-28)

**Problem:**
- Simulator used: `TIID^Device 1 (EtherCAT)^Term 4 (EL2024)^Channel 1`
- Hardware uses: `Term 10 (EL2024).Channel 1`

**Solution:**
Updated `SymbolDefinition.expand_symbols()` in `ethercat_chain.py` to:
- Remove `TIID^Device {device_id} (EtherCAT)^` prefix
- Change `^` separator to `.` separator
- Use format: `{terminal_name}.{symbol_name}`

**Files modified:**
- `tests/ads_sim/ethercat_chain.py` - `expand_symbols()` method

---

### Issue 2: Missing Device-Level Symbols
**Priority:** High
**Status:** [x] Complete (2026-01-28)

**Problem:**
Real hardware exposes EtherCAT master device symbols that simulator didn't generate.

**Solution:**
Added `get_device_symbols()` method to `EtherCATDevice` class that returns 8 device-level symbols:
- `Device 1 (EtherCAT).Inputs.Frm0State`
- `Device 1 (EtherCAT).Inputs.Frm0WcState`
- `Device 1 (EtherCAT).Inputs.Frm0InputToggle`
- `Device 1 (EtherCAT).Inputs.SlaveCount`
- `Device 1 (EtherCAT).Inputs.DevState`
- `Device 1 (EtherCAT).Outputs.Frm0Ctrl`
- `Device 1 (EtherCAT).Outputs.Frm0WcCtrl`
- `Device 1 (EtherCAT).Outputs.DevCtrl`

**Note:** Used `ADS_TYPE_BIT` (33) instead of `ADS_TYPE_UINT16` (18) because client's `symbol_lookup` doesn't handle UINT16. See [todo.md](todo.md) for follow-up task.

**Files modified:**
- `tests/ads_sim/ethercat_chain.py` - Added `get_device_symbols()` method, updated `get_all_symbols()`

---

### Issue 3: Missing Per-Terminal WcState Symbols
**Priority:** Medium
**Status:** [x] Complete (2026-01-28)

**Problem:**
Each terminal on real hardware has WcState symbols that simulator didn't generate.

**Solution:**
Integrated with `catio_terminals` runtime symbols system:
- Load `RuntimeSymbolsConfig` from `src/catio_terminals/config/runtime_symbols.yaml`
- Apply runtime symbols to each slave based on terminal type and group
- Symbols added: `WcState.WcState`, `WcState.InputToggle`, `InfoData.State`

Runtime symbols are filtered by terminal group (DigIn, DigOut, AnaIn, etc.) as defined in the YAML config.

**Note:** `InfoData.State` uses `ADS_TYPE_UINT16` which client doesn't handle - these symbols are generated but filtered by client. See [todo.md](todo.md).

**Files modified:**
- `tests/ads_sim/ethercat_chain.py`:
  - Added `_load_runtime_symbols()` method to `EtherCATChain`
  - Added `group_type` field to `TerminalType`
  - Updated `EtherCATSlave.get_symbols()` to include runtime symbols
  - Updated `total_symbol_count` to filter unhandled ADS types

---

### Issue 4: Index Group Assignments
**Priority:** Medium
**Status:** [x] Complete (2026-01-28)

**Problem:**
Simulator was using wrong index groups. Hardware uses:
- `0xF020` (61472) - Device-level inputs (Frm0State, SlaveCount, DevState)
- `0xF021` (61473) - Terminal OUTPUT channels (EL2024, etc.)
- `0xF030` (61488) - (Not observed in hardware)
- `0xF031` (61489) - Terminal INPUT channels (EL1014, etc.) and WcState symbols

**Solution:**
Fixed default index group assignments in XML parser:
- TxPdo (inputs from device) → `0xF031` (61489)
- RxPdo (outputs to device) → `0xF021` (61473)
- WcState runtime symbols → `0xF031` (61489)

**Files modified:**
- `src/catio_terminals/xml_pdo.py` - Fixed line 404: Changed `0xF020/0xF030` to `0xF031/0xF021`
- `src/catio_terminals/config/runtime_symbols.yaml` - Fixed WcState and InputToggle to use 61489
- Regenerated `src/catio_terminals/terminals/terminal_types.yaml` with corrected values

---

### Issue 5: EL1502 Counter Terminal Symbol Mismatch
**Priority:** Medium
**Status:** [x] Complete (2026-01-28)

**Problem:**
Simulator was generating extra symbols per terminal that hardware didn't have.

**Root Cause:**
Issues 1-4 and 6 collectively resolved this:
- Issue 1 fixed naming to match hardware format
- Issue 2 added missing device-level symbols
- Issue 3 added per-terminal WcState symbols
- Issue 4 corrected index group assignments
- Issue 6 added the global SyncUnits symbol

With all these fixes, the simulator now generates exactly the same symbols as hardware with no extras.

**Verification:**
```bash
$ tests/diagnose_hardware.py --compare tests/ads_sim/server_config.yaml
Hardware Symbols: 550
Simulator Total:  550
Difference: +0
✓ Hardware matches simulator
```

**Files modified:**
- Same files as Issues 1-4, 6 (no additional changes needed)

---

### Issue 6: SyncUnits Symbol
**Priority:** Low
**Status:** [x] Complete (2026-01-28)

**Problem:**
Hardware has a `SyncUnits._default_._unreferenced_.WcState.WcState` symbol that simulator didn't generate.

**Solution:**
Added SyncUnits as a global runtime symbol in `runtime_symbols.yaml`:
- Single global symbol (not per-terminal)
- Index group: `0xF031` (61489)
- Offset: `0x00002FB0` (matches hardware)
- Type: BIT (ADS_TYPE_BIT = 33)

Global runtime symbols are filtered out from per-terminal application via `is_global` field in `RuntimeSymbol` model.

**Files modified:**
- `src/catio_terminals/config/runtime_symbols.yaml` - Added SyncUnits global symbol definition
- `src/catio_terminals/models.py` - Added `is_global` field to `RuntimeSymbol`, updated `applies_to_terminal()`
- `tests/ads_sim/ethercat_chain.py` - Updated `get_all_symbols()` to add global runtime symbols

---

## Testing Strategy

✅ **Complete** - All issues resolved and verified.

Testing approach used:
1. Ran `./tests/diagnose_hardware.py --compare tests/ads_sim/server_config.yaml` against real hardware
2. Compared symbol counts and verified exact match (550 symbols)
3. Verified all symbol names match hardware format
4. Confirmed system tests pass with no regressions

## Verification Commands

```bash
# Compare simulator against hardware in real-time
./tests/diagnose_hardware.py --ip 172.23.242.42 \
  --compare tests/ads_sim/server_config.yaml

# Expected output:
# Hardware Symbols: 550
# Simulator Total:  550
# Difference: +0
# ✓ Hardware matches simulator
```

## Progress Log

| Date | Issue | Action | Result |
|------|-------|--------|--------|
| 2026-01-27 | - | Initial analysis and plan created | Identified 6 issues |
| 2026-01-28 | 1 | Updated `expand_symbols()` naming format | Symbols now use `Term.Symbol` format |
| 2026-01-28 | 2 | Added `get_device_symbols()` to EtherCATDevice | 8 device-level symbols added |
| 2026-01-28 | 3 | Integrated runtime symbols from catio_terminals | WcState symbols added (140+ new symbols) |
| 2026-01-28 | - | Fixed relative import in server.py | Tests pass |
| 2026-01-28 | - | Updated `total_symbol_count` to filter unhandled types | Test assertion fixed |
| 2026-01-28 | 4 | Fixed index group assignments in XML parser | TxPdo→0xF031, RxPdo→0xF021, regenerated YAML |
| 2026-01-28 | 6 | Added SyncUnits global runtime symbol | 1 global symbol added |
| 2026-01-28 | 5 | All fixes combined resolved symbol mismatch | Symbol count now matches: 550 = 550 ✅ |
| 2026-01-28 | - | Added `--compare` flag to diagnose_hardware.py | Real-time comparison tool |
| 2026-01-28 | - | **Plan Complete** | **Simulator matches hardware exactly** |

---

## Notes

- The `diagnose_hardware.py` script can be used to compare simulator and hardware outputs
- Symbol alignment is important for tests in `test_system.py` to pass against real hardware
- The simulator should produce symbols that match hardware format exactly for proper testing
- Client's `symbol_lookup` limitation documented in [todo.md](todo.md) - doesn't handle `ADS_TYPE_UINT16`
