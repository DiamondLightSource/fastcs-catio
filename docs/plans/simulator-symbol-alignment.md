---
orphan: true
---

# Plan: Align Simulator Symbols with Real Hardware

**Created:** 2026-01-27
**Status:** In Progress
**Related files:**
- [tests/ads_sim/ethercat_chain.py](../../tests/ads_sim/ethercat_chain.py) - Symbol generation logic
- [tests/ads_sim/server_config.yaml](../../tests/ads_sim/server_config.yaml) - Device/slave configuration
- [hardware-output.txy](../../hardware-output.txy) - Real hardware symbol dump
- [simulator-output.txy](../../simulator-output.txy) - Simulator symbol dump

## Problem Summary

The ADS simulator generates symbols that differ from real TwinCAT hardware in:
1. Symbol naming convention
2. Missing device-level symbols
3. Missing per-terminal WcState symbols
4. Extra/different symbols per terminal type
5. Index group assignments

| Metric | Simulator | Hardware |
|--------|-----------|----------|
| Total Symbols | 1091 | 550 |
| Naming Format | `TIID^Device 1 (EtherCAT)^Term X^...` | `Term X (type).Channel Y` |

---

## Issues and Tasks

### Issue 1: Symbol Naming Convention
**Priority:** High
**Status:** [ ] Not Started

**Problem:**
- Simulator uses: `TIID^Device 1 (EtherCAT)^Term 4 (EL2024)^Channel 1`
- Hardware uses: `Term 10 (EL2024).Channel 1`

**Tasks:**
- [ ] 1.1 Update `SymbolDefinition.expand_symbols()` in `ethercat_chain.py` to use dot-separated format
- [ ] 1.2 Remove `TIID^Device {device_id} (EtherCAT)^` prefix
- [ ] 1.3 Change `^` separator to `.` separator
- [ ] 1.4 Update tests to expect new format

**Files to modify:**
- `tests/ads_sim/ethercat_chain.py` (lines 24-77)

---

### Issue 2: Missing Device-Level Symbols
**Priority:** High
**Status:** [ ] Not Started

**Problem:**
Real hardware exposes EtherCAT master device symbols that simulator doesn't generate:
```
Device 1 (EtherCAT).Inputs.Frm0State
Device 1 (EtherCAT).Inputs.Frm0WcState
Device 1 (EtherCAT).Inputs.Frm0InputToggle
Device 1 (EtherCAT).Inputs.SlaveCount
Device 1 (EtherCAT).Inputs.DevState
Device 1 (EtherCAT).Outputs.Frm0Ctrl
Device 1 (EtherCAT).Outputs.Frm0WcCtrl
Device 1 (EtherCAT).Outputs.DevCtrl
```

**Tasks:**
- [ ] 2.1 Add device-level symbol generation to `EtherCATDevice` class
- [ ] 2.2 Define standard device input symbols (Frm0State, Frm0WcState, etc.)
- [ ] 2.3 Define standard device output symbols (Frm0Ctrl, Frm0WcCtrl, DevCtrl)
- [ ] 2.4 Use correct index groups: `0xF030` for inputs, `0xF020` for outputs

**Files to modify:**
- `tests/ads_sim/ethercat_chain.py` - Add `get_device_symbols()` method to `EtherCATDevice`

---

### Issue 3: Missing Per-Terminal WcState Symbols
**Priority:** Medium
**Status:** [ ] Not Started

**Problem:**
Each terminal on real hardware has WcState symbols:
```
Term 10 (EL2024).WcState.WcState
Term 100 (EL1502).WcState.InputToggle
Term 100 (EL1502).WcState.WcState
```

**Tasks:**
- [ ] 3.1 Add WcState symbol generation for all terminal types
- [ ] 3.2 Add InputToggle symbol for terminals that have it (EL1502, EL9410, etc.)
- [ ] 3.3 Use index group `0xF031` for WcState symbols

**Files to modify:**
- `tests/ads_sim/ethercat_chain.py`
- Terminal YAML definitions in `src/catio_terminals/terminals/`

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

---

## Notes

- The `diagnose_hardware.py` script can be used to compare simulator and hardware outputs
- Symbol alignment is important for tests in `test_system.py` to pass against real hardware
- The simulator should produce symbols that match hardware format exactly for proper testing
