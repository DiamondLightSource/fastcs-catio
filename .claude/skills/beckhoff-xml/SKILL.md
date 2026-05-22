---
name: beckhoff-xml
description: Reference for Beckhoff ESI XML (EtherCAT Slave Information) files and the terminal YAML files this repo generates from them. Surface when working with ESI XML, terminal YAML, composite types, ADS symbol nodes vs runtime symbols, CoE objects, or the XML-to-YAML mapping in `src/catio_terminals/xml/`. Also surface before editing files in `src/catio_terminals/terminals/` — those YAMLs are generated and must not be hand-edited.
---

# beckhoff-xml

Working with Beckhoff ESI XML files and the terminal YAML files this
repo generates from them.

## Critical rule — terminal YAMLs are generated

**Never manually edit** YAML files in `src/catio_terminals/terminals/`.
They are generated from Beckhoff ESI XML by code in
`src/catio_terminals/xml/`. If a YAML has wrong values:

1. Fix the XML parsing code that produced it.
2. Regenerate with `uv run catio-terminals clean-yaml <file>` (default
   target: `src/catio_terminals/terminals/terminal_types.yaml`).
3. Manual edits are lost on next regeneration.

Group-specific logic lives in `process_pdo_entries()` in
`src/catio_terminals/xml/pdo.py`. Special cases:

- Index groups default to `0xF031` / `0xF021` for standard I/O.
- Counter terminals (`group_type="Measuring"`) use `0xF030` / `0xF020`.

## Where the XML lives

- Cached at `~/.cache/catio_terminals/beckhoff_xml/`.
- Refresh with `catio-terminals update-cache`.
- Edit YAMLs with the GUI via `catio-terminals edit [filename]` (but
  remember: regenerate, don't hand-edit).
- ESI files are grouped by series, e.g. `Beckhoff EL31xx.xml` contains
  EL3104, EL3124, …; `Beckhoff EL32xx.xml` contains EL3202, EL3204, …

## Audit scope: only terminals currently deployed at DLS

When scanning the ESI cache for patterns (e.g. auditing PDO naming
quirks, channel-numbering anomalies, identity-revision drift), **scope
the scan to the terminal types listed in
`src/catio_terminals/terminals/terminal_types.yaml`**. That YAML is
the authoritative list of terminals deployed at DLS and will be
updated as new terminals are deployed. The wider ESI cache contains
hundreds of products (axis controllers, drives, etc.) that aren't on
any rig — flagging issues in those is noise.

Override only if the user explicitly asks for a broader scan.

## XML → YAML field mapping

| XML | YAML |
|-----|------|
| `Type@ProductCode` | `identity.product_code` |
| `Type@RevisionNo` | `identity.revision_number` |
| `TxPdo/Entry` | `symbol_nodes[]` (inputs) |
| `RxPdo/Entry` | `symbol_nodes[]` (outputs) |
| `Profile/Dictionary/Objects` | `coe_objects[]` |

## What the XML does NOT contain

- Composite type names — assigned by our XML parser.
- Some symbols like `WcState` are ADS runtime symbols, not XML-defined.

## Supporting a new terminal: YAML is the source of truth

Since issue #54 there is only one thing to do: regenerate the YAML.

`src/fastcs_catio/symbols.py` no longer hosts a hardcoded LUT. The
bus-side expander finds the matching terminal in
`terminal_types.yaml` by identity (vendor / product / revision) and
emits ADS symbols for every `selected: true` row, at offsets it reads
from each row's `bit_offset` (populated by the XML parser).

So:

1. Run `uv run catio-terminals clean-yaml <file>` so the parser picks
   up the new terminal and writes `bit_offset` for each row.
2. Use the editor (`uv run catio-terminals edit`) to set `selected:
   true` on rows that should produce PVs.

If a row's symbol isn't produced at runtime, the most likely cause is
that no bus node provides the parent struct's offset — check the
slave's name prefix and the row's `name_template`.

See [terminal-yaml-definitions.md](../../../docs/explanations/terminal-yaml-definitions.md)
for the distinction between XML-defined symbols and ADS runtime
symbols.

## Selection-state round-trip and merge idempotency

`merge_xml_for_terminal` is **called repeatedly** on the same terminal
in normal use — the GUI's tree-view lazy-load fires it once, and the
revision dropdown fires it again on every change. So the merge **must
be idempotent**: running it N times on a terminal already in its
merged state must not change selection state.

The trap: `to_yaml` filters CoE objects by `selected=True` (only
selected CoEs survive to disk), so on load every CoE in the YAML is
implicitly selected — but `CoEObject.selected` defaults to `False`.
`TerminalConfig.from_yaml` compensates by stamping `selected=True` on
every loaded CoE. If you add a new place that constructs
`TerminalConfig` from a YAML dict, replicate that stamp or merges
will silently mark all your CoE entries unselected next time around.

Conversely, `merge_xml_for_terminal` itself must **not** force
`selected = True` on entries that survived the merge — that's what
broke the rig in 2026-05-21 (every re-merge promoted XML-only rows
the prior merge had added unselected, including CoE 0x1011 "Restore
default parameters", which crashed the IOC at startup on a 0-byte
read). The current code preserves existing selection state.

If you touch the merge or YAML round-trip, run
`tests/test_new_terminal_coe_selection.py::test_merge_preserves_selection_on_remerge`
to make sure the invariant still holds.

## Bus-side expansion rules (post-#54)

`expand_symbols_for_slave` in `src/fastcs_catio/symbols.py` is fussy
about which YAML rows actually become ADS subscriptions. The rules,
in priority order:

1. **`selected: false` → skipped.** YAML drives subscription.
2. **Non-leaf rows → skipped.** If a row's `name_template` is a
   strict prefix of any other row's template, it's a bare struct
   parent (e.g. `TC Inputs Channel {channel}` with children
   `.Value`, `.Limit 1`). TwinCAT reports the full struct size for
   the bare name, which then mismatches the YAML row's primitive
   type and the `symbol.nbytes == sample.size` assertion fires at
   notification flush time.
3. **Sub-byte bit-field rows → skipped.** ADS addresses are
   byte-granular; rows with `bit_offset % 8 != 0` represent bit
   fields within a parent byte (e.g. EL3104's `.Status__Limit 1`
   at bit 2). Trying to subscribe gets
   `ADSERR_DEVICE_SYMBOLVERSIONINVALID` at startup.
4. **No bus parent → emit warning, skip.** A YAML row whose
   resolved name has no matching bus node (or ancestor bus node)
   gets a startup warning. Most common cause: the rig is in a
   different dynamic PDO group than `selected_pdo_group` in the YAML
   (see #58 for the per-slave-instance problem).

## PDO groups can share PDOs

A single TxPDO/RxPDO can appear in more than one `AlternativeSmMapping`.
EL3314's `TC Inputs Channel N` TxPDOs (`#x1a00..#x1a03`) are listed in
both `Inputs only` (default) and `with ColdJunction Compensation` — the
CJC group is the inputs group plus four output RxPDOs. After the
XML→YAML merge, a single symbol index therefore appears in *every*
`pdo_groups[].symbol_indices` list whose `pdo_indices` contains its
source PDO. Treat PDO ↔ group as many-to-many, not one-to-one.

`assign_symbols_to_groups` in `src/catio_terminals/xml/pdo_groups.py`
was last-writer-wins until 8eb4247. The shared PDOs were claimed
exclusively by the last-iterated group, leaving the *default* group
with an empty `symbol_indices` — the GUI showed no rows when the
default group was selected, and `clean-yaml` left every row
unselected. If you ever rewrite that mapping, the test
`tests/test_pdo_groups.py::test_assign_symbols_to_groups_shared_pdo`
nails the invariant.

## `clean-yaml` selection contract

`uv run catio-terminals clean-yaml <file>`:

- Re-merges from XML. For each terminal, sets `symbol.selected = True`
  on rows in the **active** PDO group (`selected_pdo_group`, or the
  `is_default` group if unset). Rows outside that group end up
  `selected: false`. Set `selected_pdo_group` *before* running it.
- Default: keeps CoE objects in the settings range `0x8000-0x8FFF`,
  drops the rest. `--include-all-coe` keeps every CoE from XML.
  `--remove-coe` strips them all and prints a loud warning at start.

To verify a regen is a no-op, re-run with the same flags and confirm
`git diff --stat` is empty.

## Type-name → `(numpy dtype, count)` resolution

`_dtype_for_type_name` in `symbols.py` maps a YAML `type_name` to the
numpy dtype and element count for the AdsSymbol. The element-size in
`_DTYPE_MAP` is **bytes per element, not count**: scalar primitives
always return `count=1`. Only `ARRAY [a..b] OF X` returns
`count = b - a + 1`. Mixing those up makes `AdsSymbol.nbytes` come
out double the real symbol size and trips the notification-stream
assertion.

## Identity matching: revision is loose

Beckhoff bumps the `revision_number` on backward-compatible firmware
/ silicon updates while keeping the PDO layout identical.
`terminal_config.get_terminal_type_by_identity` prefers an exact
`(vendor, product, revision)` match but falls back to
`(vendor, product)` if the rig's revision differs from the cached
XML's. Don't pin matching to all three components without a fallback.

## Subscription gating

`CATioConnection.set_wanted_attribute_keys(...)` (called from the
server controller after `attribute_map` is built) restricts ADS
notification subscriptions to symbols whose `f"_{symbol.name}"` is in
the supplied key set. This closes the seam #53 papered over:
bus-only housekeeping like `_SyncUnits._default_._unreferenced_.*` is
discovered but never subscribed, so no warning spam at notification
arrival. If you ever skip the wiring at the server-controller level,
the connection falls back to subscribing every discovered symbol
(pre-#54 behaviour).

## Reference documents

Read these when context isn't already loaded:

- [docs/reference/beckhoff-xml-format.md](../../../docs/reference/beckhoff-xml-format.md)
  — ESI XML schema (Device, TxPdo, RxPdo, Entry, CoE objects), file
  naming conventions, what's NOT in XML.
- [docs/explanations/terminal-yaml-definitions.md](../../../docs/explanations/terminal-yaml-definitions.md)
  — Terminal YAML structure (identity, symbol_nodes, coe_objects),
  SymbolNode fields, computed properties, channel templating.
- [docs/explanations/composite-types.md](../../../docs/explanations/composite-types.md)
  — Composite type definitions.

## Related skill

- [[ads-simulator-testing]] — terminal YAMLs feed the ADS simulator;
  symbol-count mismatches usually trace back to XML parsing bugs.
