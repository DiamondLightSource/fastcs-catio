---
orphan: true
---

# Plan: Align Simulator Symbols with Real Hardware

**Created:** 2026-01-27
**Updated:** 2026-01-28
**Status:** In Progress (Issues 1-3 Complete)
**Related files:**
- [tests/ads_sim/ethercat_chain.py](../../tests/ads_sim/ethercat_chain.py) - Symbol generation logic
- [tests/ads_sim/server_config.yaml](../../tests/ads_sim/server_config.yaml) - Device/slave configuration
- [hardware-output.txy](../../hardware-output.txy) - Real hardware symbol dump
- [simulator-output.txy](../../simulator-output.txy) - Simulator symbol dump

## Problem Summary

The ADS simulator generates symbols that differ from real TwinCAT hardware in:
1. ~~Symbol naming convention~~ ✅ Fixed
2. ~~Missing device-level symbols~~ ✅ Fixed
3. ~~Missing per-terminal WcState symbols~~ ✅ Fixed
4. Extra/different symbols per terminal type
5. Index group assignments

| Metric | Simulator (Before) | Simulator (After) | Hardware |
|--------|-----------|-----------|----------|
| Total Symbols | 1091 | 1239 | 550 |
| Naming Format | `TIID^Device 1 (EtherCAT)^Term X^...` | `Term X (type).Channel Y` ✅ | `Term X (type).Channel Y` |

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
**Status:** [ ] Not Started

**Problem:**
Simulator uses `0xF030` for most symbols. Hardware uses:
- `0xF030` - Device inputs, terminal inputs
- `0xF020` - Device outputs, terminal outputs
- `0xF021` - Terminal channel outputs (e.g., EL2024 channels)
- `0xF031` - WcState symbols

**Tasks:**
- [ ] 4.1 Document index group meanings and usage
- [ ] 4.2 Update `SymbolDefinition` to support input vs output distinction
- [ ] 4.3 Update terminal YAML files with correct index groups
- [ ] 4.4 Update `expand_symbols()` to use appropriate index groups

**Files to modify:**
- `tests/ads_sim/ethercat_chain.py`
- Terminal YAML files

---

### Issue 5: EL1502 Counter Terminal Symbol Mismatch
**Priority:** Medium
**Status:** [ ] Not Started

**Problem:**
Simulator generates extra symbols per EL1502:
- `CNT Outputs Output 1` through `Output 8`
- `CNT Outputs Set output`

Hardware only exposes:
- `CNT Inputs` + `CNT Inputs.Counter value`
- `CNT Outputs` + `CNT Outputs.Set counter value`

**Tasks:**
- [ ] 5.1 Review EL1502 terminal definition in `counter.yaml`
- [ ] 5.2 Remove extra output bit symbols
- [ ] 5.3 Verify symbol names match hardware exactly
- [ ] 5.4 Test EL1502 symbol generation

**Files to modify:**
- `src/catio_terminals/terminals/counter.yaml` (if exists)
- Terminal type definitions

---

### Issue 6: SyncUnits Symbol
**Priority:** Low
**Status:** [ ] Not Started

**Problem:**
Hardware has a `SyncUnits._default_._unreferenced_.WcState.WcState` symbol that simulator doesn't generate.

**Tasks:**
- [ ] 6.1 Investigate what SyncUnits symbol represents
- [ ] 6.2 Add SyncUnits symbol generation if needed

---

## Testing Strategy

After each issue is addressed:
1. Run `./tests/diagnose_hardware.py --dump-symbols > simulator-output.txy` against simulator
2. Compare with `hardware-output.txy`
3. Verify symbol count approaches 550 (hardware count)
4. Run existing system tests to ensure no regressions

## Verification Commands

```bash
# Generate simulator output
cd /workspaces/CATio
python -m tests.ads_sim &  # Start simulator
./tests/diagnose_hardware.py --ip 127.0.0.1 --dump-symbols > simulator-output.txy

# Generate hardware output (when available)
./tests/diagnose_hardware.py --ip 172.23.242.42 --dump-symbols > hardware-output.txy

# Compare symbol counts
grep -c "^  [A-Za-z]" simulator-output.txy
grep -c "^  [A-Za-z]" hardware-output.txy

# Compare symbol patterns
diff <(grep -oE "^  [A-Za-z][^\n]+" simulator-output.txy | sort -u) \
     <(grep -oE "^  [A-Za-z][^\n]+" hardware-output.txy | sort -u)
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

---

## Notes

- The `diagnose_hardware.py` script can be used to compare simulator and hardware outputs
- Symbol alignment is important for tests in `test_system.py` to pass against real hardware
- The simulator should produce symbols that match hardware format exactly for proper testing
- Client's `symbol_lookup` limitation documented in [todo.md](todo.md) - doesn't handle `ADS_TYPE_UINT16`
