# CLAUDE.md

Project-specific context for AI coding agents working on `fastcs-catio`.

## What this repo is

An EPICS IOC built with [FastCS] that talks to Beckhoff EtherCAT I/O
terminals via the ADS protocol over TwinCAT.

- `fastcs-catio` — the IOC.
- `catio-terminals` — YAML/GUI tool that generates terminal-type
  definitions from Beckhoff ESI XML.

## Tools

Everything runs through `uv`:

- `uv run pytest` — unit tests in `tests/`, doctests in `src/` and
  `docs/*.rst` (all three are wired into the pytest run).
- `uv run ruff check --fix && uv run pyright src tests` — after edits.
- `uv run catio-terminals update-cache` — refresh cached Beckhoff XML.
- `uv run catio-terminals edit [file]` — GUI editor for terminal YAML.

Ruff with line-length 88; pyright in standard mode. Both configured
in `pyproject.toml`.

## Project-specific rules

- **Never run `fastcs-catio ioc` yourself.** It needs real hardware on
  the network. Ask the user to run it and report errors back.
- **Never hand-edit YAMLs in `src/catio_terminals/terminals/`.** They
  are generated from Beckhoff XML by `src/catio_terminals/xml/`. Fix
  the parser, then regenerate with
  `uv run catio-terminals clean-yaml <file>`. See the `beckhoff-xml`
  skill for the details.
- **Port 48898 in use during `test_system.py`?** VS Code's "Ports"
  panel has auto-forwarded it — delete the forward and retry.

## Documentation

The docs use Sphinx + MyST with a Diátaxis four-way split. New doc
files must be added to the matching toctree:

| Kind | Toctree |
|------|---------|
| Explanation | `docs/explanations.md` |
| How-to | `docs/how-to.md` |
| Reference | `docs/reference.md` |
| Tutorial | `docs/tutorials.md` |

Don't embed Python source in doc files — link to the file and briefly
describe what's there.

## Skills

Project-specific skills live in [.claude/skills/](.claude/skills/) and
surface automatically when relevant:

- **beckhoff-xml** — ESI XML schema, terminal YAML structure, the
  generated-not-edited rule, XML-to-YAML field mapping.
- **ads-simulator-testing** — `EtherCATChain` usage, symbol-count
  debugging, hardware-vs-simulator comparison.
- **mermaid-diagrams** — Mermaid in MyST docs, and when ASCII art is
  the better choice.

[FastCS]: https://github.com/DiamondLightSource/FastCS
