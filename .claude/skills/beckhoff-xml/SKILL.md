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
- ADS offsets — computed at runtime.
- Some symbols like `WcState` are ADS runtime symbols, not XML-defined.

## Supporting a new terminal struct type needs two things

YAML alone is not enough. The runtime symbol-lookup table in
`src/fastcs_catio/symbols.py` is a parallel requirement:

1. **YAML entry** in `src/catio_terminals/terminals/terminal_types.yaml`
   (regenerated from XML).
2. **Regex pattern** in `AdsSymbolTypePattern` (~line 40 of
   `src/fastcs_catio/symbols.py`) matching the structured-symbol type
   name the live ADS server reports for that terminal.
3. **`case` arm** in `symbol_lookup` (same file, ~line 157) returning
   the right `SymbolGroupParam` for the value field.

If the regex is missing, `symbol_lookup` falls into the `case _`
default and logs `Definition for the structured symbol node type
'<TypeName>' ... is missing. Symbol node will be ignored.` The parent
struct (which carries the actual value field) is silently dropped at
startup. When you see that warning, add the pattern — don't just
regenerate the YAML.

See [terminal-yaml-definitions.md](../../../docs/explanations/terminal-yaml-definitions.md)
for the distinction between XML-defined symbols and ADS runtime
symbols.

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
