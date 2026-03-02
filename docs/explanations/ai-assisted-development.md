# AI-Assisted Architectural Transformation of CATio

A single developer, working with Claude as an AI pair programmer over approximately
two weeks, transformed CATio from a system requiring hand-written Python for each
terminal type into one driven entirely by YAML definitions. The result: 29 terminal
types across two packages, roughly 17,000 lines of Python, and over 14,000 lines of
YAML terminal definitions -- delivered through 154 non-merge commits between
mid-December 2025 and early February 2026.

## The Transformation

### Before

CATio's original architecture required a dedicated Python class for every
EtherCAT (a real-time industrial fieldbus protocol) terminal type. The file
`catio_hardware.py` contained 20 such classes across 1,204 lines, each one
manually defining I/O attributes through repetitive `add_attribute()` calls.
Adding support for a new Beckhoff terminal meant writing 30 to 60 lines of
Python boilerplate -- copying an existing class, adjusting channel counts and
attribute names, and hoping the pattern stayed consistent.

### After

A single factory function, `get_terminal_controller_class()`, now reads YAML
definitions at runtime and generates FastCS controller classes dynamically. Terminal
types are described declaratively in `terminal_types.yaml`, and a companion
`catio_terminals` package provides a NiceGUI web editor for managing those
definitions. Adding a new terminal type means editing a YAML file -- or using
the GUI.

### The Difference in Practice

**Before:** one Python class per terminal type (20 classes, 1,204 lines)

```python
class EL1004Controller(CATioTerminalController):
    io_function = "4-channel digital input, 24V DC, 3ms filter"
    num_channels = 4
    async def get_io_attributes(self):
        for i in range(1, self.num_channels + 1):
            self.add_attribute(f"DICh{i}Value", AttrR(datatype=Int(), ...))
```

**After:** one YAML block per terminal type (29 types, generated from vendor XML)

```yaml
EL1004:
  description: 4Ch. Dig. Input 24V, 3ms
  symbol_nodes:
    - name_template: Channel {channel}
      channels: 4
      access: Read-only
      selected: true
```

## By the Numbers

| Metric | Value | Quality Indicator |
|--------|-------|-------------------|
| Terminal types | 29 defined in YAML | Validated against Beckhoff ESI XML |
| Source files | 16 before, 56 after | Documented across 10 explanation pages |
| Python (fastcs_catio) | 11,424 lines across 19 files | Includes dynamic controller modules |
| Python (catio_terminals) | 6,256 lines across 31 files | GUI editor, XML parser, data models |
| YAML definitions | 14,276 lines | Machine-generated from vendor XML, human-editable |
| Legacy classes | 20 in catio_hardware.py | Retained as validated fallback for original set |
| Timeline | ~2 weeks core (Jan 22 -- Feb 5) | Within a broader Dec -- Feb development period |
| Commits | 128 by the developer, 154 total | Includes testing, documentation, and cleanup |

The transformation touched both packages: `fastcs_catio` grew from a monolithic
controller file into a set of dynamic modules (`catio_dynamic_controller.py`,
`catio_dynamic_symbol.py`, `catio_dynamic_coe.py`, `catio_dynamic_types.py`), while
`catio_terminals` was built from scratch as a standalone GUI tool for editing and
validating terminal definitions.

## How AI Accelerated Development

Giles Knap, the project's developer, brought deep domain expertise in EtherCAT,
TwinCAT ADS (Automation Device Specification -- Beckhoff's communication protocol),
and the FastCS framework. He directed the architectural vision throughout: the
decision to move from hard-coded classes to YAML-driven generation, the design of
the terminal definition schema, and the choice to create a separate GUI package. Claude
served as a pair programmer, handling the bulk implementation under that direction.

Concrete tasks Claude performed included: generating controller boilerplate for the
20 original terminal types, implementing protocol handler code for ADS communication,
parsing Beckhoff ESI XML files to extract terminal definitions into YAML, drafting
architecture documentation (commit `4dcc9d5`: 1,307 lines across 14 files), and
refactoring modules when complexity grew. The developer's workflow evolved during the
project -- he began writing feature documentation first, then directing Claude to
implement the code, using the docs as a specification.

Two AI model tiers were used via a GitHub Copilot subscription: Claude Sonnet handled
primary implementation tasks, while Claude Opus was brought in for analysis and
refactoring of larger modules. This division was practical -- when `catio_hardware.py`
exceeded 12,000 lines during development, Sonnet struggled with the context window,
so Opus analysed the file and proposed a decomposition into the smaller dynamic modules
that exist today.

This project was not the developer's first use of AI-assisted development. An earlier
project, builder2ibek, had explored AI pair programming for a simpler migration tool.
CATio's work predated the structured agent workflows and skill definitions that
builder2ibek later adopted, making it a more manual but foundational experience. The
trajectory from CATio to builder2ibek shows a practice maturing over successive
projects -- not a one-off experiment.

## What This Means Going Forward

The core payoff is maintainability. When new Beckhoff terminals enter the market,
adding support to CATio is now a configuration task rather than a coding task: add a
YAML block to `terminal_types.yaml` (or use the GUI editor), and the dynamic
controller factory handles the rest. This has already been demonstrated -- 10
additional terminal types were added after the initial set with zero Python changes
to the dynamic controller code.

For the project's long-term health, this means that contributors do not need to
understand the controller framework internals to add terminal support. The barrier
to entry dropped from "write a Python class that correctly implements the FastCS
attribute protocol" to "describe the terminal's channels and
CoE (CANopen over EtherCAT) parameters in YAML."

## Learn More

- [Architecture Overview](architecture-overview.md) -- full architecture with
  diagrams showing the dynamic controller generation pipeline
- [Terminal YAML Definitions](terminal-yaml-definitions.md) -- complete YAML schema,
  how to add new terminals, and GUI editor usage
- [FastCS EPICS IOC](fastcs-epics-ioc.md) -- dynamic controller generation details
  and runtime attribute creation
