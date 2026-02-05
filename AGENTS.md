# Agent Guidelines for Python Code Quality

This document provides guidelines for maintaining high-quality Python code. These rules MUST be followed by all AI coding agents and contributors.

(adapted from https://gist.githubusercontent.com/minimaxir/c274d7cc12f683d93df2b1cc5bab853c/raw/807e282d6580b37bafb3051ddbc5be909e82cdd2/CLAUDE.md)

## Your Core Principles

All code you write MUST be fully optimized.

"Fully optimized" includes:

- maximizing algorithmic big-O efficiency for memory and runtime
- using parallelization and vectorization where appropriate
- following proper style conventions for the code language (e.g. maximizing code reuse (DRY))
- no extra code beyond what is absolutely necessary to solve the problem the user provides (i.e. no technical debt)
- check all code for repeated functionality that can be factored out
- (I know I've said this 3 ways but DRY seems to be agent's weakest area)

## Preferred Tools

- Use `uv` for Python package management and to create a `.venv` if it is not present.
- also use `uv` to run tests and other commands (e.g. `uv pytest`, `uv ruff check`, etc.)
- Use `ruff` for code formatting and linting
- Use `pyright` for static type checking
- When reporting error to the console, use `logger.error` instead of `print`.
- For data science:
  - **ALWAYS** use `polars` instead of `pandas` for data frame manipulation.
  - If a `polars` dataframe will be printed, **NEVER** simultaneously print the number of entries in the dataframe nor the schema as it is redundant.
  - **NEVER** ingest more than 10 rows of a data frame at a time. Only analyze subsets of code to avoid overloading your memory context.

## Terminal Tool Usage

When using the `run_in_terminal` tool:

- The tool result may show only a minimal acknowledgment (e.g., `#` with a timestamp) rather than the actual command output
- **ALWAYS** use `terminal_last_command` tool afterward to retrieve the actual output if the `run_in_terminal` result appears empty or truncated
- Check the exit code in the context to determine if the command succeeded before assuming failure

**CRITICAL: Avoid repeating commands**

- The `<context>` block at the start of each user message contains terminal state including:
  - `Last Command`: The command that was run
  - `Exit Code`: Whether it succeeded (0) or failed
- **BEFORE** running a command, check if the context already shows it ran successfully
- **NEVER** re-run a command that the context shows already completed with exit code 0
- If you need the output and the context doesn't show it, use `terminal_last_command` once - do not re-run the command

**Common mistake to avoid:**
- ❌ Run command → Get minimal output → Try to run same command again
- ✅ Run command → Get minimal output → Check context for exit code → Use `terminal_last_command` to get full output
- The `run_in_terminal` tool often returns minimal acknowledgment, but the command still executed successfully
- Always check the context in the next turn - if Exit Code: 0, the command succeeded; just get the output with `terminal_last_command`

## Code Style and Formatting

- **MUST** use meaningful, descriptive variable and function names
- **MUST** follow PEP 8 style guidelines
- **MUST** place all imports at the top of the file (after module docstring)
  - Group imports: standard library, third-party, local application imports
  - **NEVER** place imports inside functions or conditional blocks unless absolutely necessary
  - If a lazy import is needed (e.g., to avoid circular imports), document why
- **NEVER** use emoji, or unicode that emulates emoji (e.g. ✓, ✗). The only exception is when writing tests and testing the impact of multibyte characters.
- Limit line length to 88 characters (ruff formatter standard)

## Documentation

- **MUST** include docstrings for all public functions, classes, and methods
- **MUST** document function parameters, return values, and exceptions raised
- Keep comments up-to-date with code changes
- Include examples in docstrings for complex functions

Example docstring:

```python
def calculate_total(items: list[dict], tax_rate: float = 0.0) -> float:
    """Calculate the total cost of items including tax.

    Args:
        items: List of item dictionaries with 'price' keys
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)

    Returns:
        Total cost including tax

    Raises:
        ValueError: If items is empty or tax_rate is negative
    """
```

## Type Hints

- **MUST** use type hints for all function signatures (parameters and return values)
- **NEVER** use `Any` type unless absolutely necessary
- **MUST** run pyright and resolve all type errors
- Use `T | None` for nullable types

## Error Handling

- **NEVER** silently swallow exceptions without logging
- **MUST** never use bare `except:` clauses
- **MUST** catch specific exceptions rather than broad exception types
- **MUST** use context managers (`with` statements) for resource cleanup
- Provide meaningful error messages

## Function Design

- **MUST** keep functions focused on a single responsibility
- **NEVER** use mutable objects (lists, dicts) as default argument values
- Limit function parameters to 5 or fewer
- Return early to reduce nesting

## Class Design

- **MUST** keep classes focused on a single responsibility
- **MUST** keep `__init__` simple; avoid complex logic
- Use dataclasses for simple data containers
- Use Pydantic for data validation models and serializing/deserializing data to yaml
- Prefer composition over inheritance
- Avoid creating additional class functions if they are not necessary
- Use `@property` for computed attributes

## Testing

- **MUST** write unit tests for all new functions and classes
- **MUST** include doctests in docstrings with realistic examples that pass
- **MUST** ensure doctest examples use correct types matching function signatures
- **MUST** mock external dependencies (APIs, databases, file systems)
- **MUST** use pytest as the testing framework
- **NEVER** run tests you generate without first saving them as their own discrete file
- **NEVER** delete files created as a part of testing.
- Ensure the folder used for test outputs is present in `.gitignore`
- Follow the Arrange-Act-Assert pattern
- Do not commit commented-out tests
- Note: `pytest` runs unit/system tests in `tests/`, doctests in `src/` modules, and doctests in `docs/*.rst` files

## Imports and Dependencies

- **MUST** avoid wildcard imports (`from module import *`)
- **MUST** document dependencies in `pyproject.toml`
- Use `uv` for fast package management and dependency resolution
- Use `ruff` to automate import formatting

## Python Best Practices

- **NEVER** use mutable default arguments
- **MUST** use context managers (`with` statement) for file/resource management
- **MUST** use `is` for comparing with `None`, `True`, `False`
- **MUST** use f-strings for string formatting
- Use list comprehensions and generator expressions
- Use `enumerate()` instead of manual counter variables

## Security

- **NEVER** store secrets, API keys, or passwords in code. Only store them in `.env`.
  - Ensure `.env` is declared in `.gitignore`.
  - **NEVER** print or log URLs to console if they contain an API key.
- **MUST** use environment variables for sensitive configuration
- **NEVER** log sensitive information (passwords, tokens, PII)

## Version Control

- **MUST** write clear, descriptive commit messages
- **NEVER** commit commented-out code; delete it
- **NEVER** commit debug print statements or breakpoints
- **NEVER** commit credentials or sensitive data

## Tools


- **MUST** use `uv` for package management
- do `uv ruff check --fix; uv run pyright src tests` after code changes
- or `uv ruff check --fix; uv run mypy src tests` for projects that use mypy
- Use `uv run pytest` for testing (runs unit tests in `tests/`, doctests in `src/` and `docs/`)

## Before Committing

- [ ] All tests pass
- [ ] Type checking passes (mypy or pyright)
- [ ] Code formatter and linter pass (Ruff)
- [ ] All functions have docstrings and type hints
- [ ] No commented-out code or debug statements
- [ ] No hardcoded credentials

## Documentation

- **ALWAYS** add new documentation files to the appropriate index:
  - Explanations → `docs/explanations.md` toctree
  - How-to guides → `docs/how-to.md` toctree
  - Reference → `docs/reference.md` toctree
  - Tutorials → `docs/tutorials.md` toctree
- **NEVER** embed Python code from the repository in documentation files
  - Instead, reference the source file and briefly describe what the classes/functions provide
  - Example: "The data models are defined in [models.py](src/catio_terminals/models.py): `PdoGroup` stores the group name and PDO indices, `TerminalType` includes helper properties for PDO group selection."

## Domain Knowledge

This project interfaces with Beckhoff EtherCAT I/O terminals via the ADS protocol. Key concepts:

- **Testing with Hardware**: **NEVER** run `fastcs-catio ioc` commands yourself. Let the user run the IOC and report any errors back to you. The IOC requires network access to real hardware that may not be available or may have specific configuration requirements.

- **Terminal Definitions**: YAML files describing Beckhoff terminal types, their symbols, and CoE objects. See [docs/explanations/terminal-yaml-definitions.md](docs/explanations/terminal-yaml-definitions.md) for:
  - How to generate terminal YAML files using `catio-terminals`
  - Understanding ADS symbol nodes and index groups
  - The difference between XML-defined symbols and ADS runtime symbols (e.g., `WcState`)
  - CoE (CANopen over EtherCAT) object definitions

- **Beckhoff XML Files**: ESI (EtherCAT Slave Information) XML files from Beckhoff group terminals by series:
  - `Beckhoff EL31xx.xml` contains EL3104, EL3124, etc.
  - `Beckhoff EL32xx.xml` contains EL3202, EL3204, etc.
  - Cached at `~/.cache/catio_terminals/beckhoff_xml/`
  - Use `catio-terminals update-cache` to download/refresh

- **catio-terminals**: GUI editor for terminal YAML files. Use `catio-terminals update-cache` to fetch Beckhoff XML definitions, then use `catio-terminals edit [filename]` to edit files with the GUI.

- **Terminal YAML Files Are Generated**: **NEVER manually edit** terminal YAML files in `src/catio_terminals/terminals/`. These files are generated from Beckhoff XML by the code in `src/catio_terminals/xml/`. If the YAML has incorrect values:
  1. Fix the XML parsing code that generates the YAML
  2. Regenerate the YAML using `uv run catio-terminals clean-yaml <file>` (default is src/catio_terminals/terminals/terminal_types.yaml)
  3. Manual edits will be lost on next regeneration

  **Special cases:**
  - Index groups default to 0xF031/0xF021 for standard I/O
  - Counter terminals (group_type="Measuring") use 0xF030/0xF020 instead
  - Group-specific logic is in `process_pdo_entries()` in `xml/pdo.py`

## Agent Skills

Skills are specialized knowledge that can be loaded on demand. Use these prompts to activate a skill.

**Note:** Generic, reusable skills (not specific to this repo) are in [SKILLS.md](SKILLS.md). Repository-specific skills are below.

### Beckhoff XML Skill

**Activation prompts:**
- "Load Beckhoff XML skill"
- "I need to work with ESI XML files"
- "Help me understand the Beckhoff XML format"
- "Help me edit terminal YAML files"
- "I need to understand composite types"
- "Extract terminal data from XML"
- "Help me create a terminal YAML from XML"

**Skill context:** Read these documents:
- [beckhoff-xml-format.md](docs/reference/beckhoff-xml-format.md) - ESI XML schema (Device, TxPdo, RxPdo, Entry, CoE objects), XML file naming conventions (terminals grouped by series: EL31xx.xml, EL32xx.xml, etc.), what information is NOT in XML (composite type names, ADS offsets)
- [terminal-yaml-definitions.md](docs/explanations/terminal-yaml-definitions.md) - Terminal YAML structure (identity, symbol_nodes, coe_objects), SymbolNode fields, computed properties, channel templating
- [composite-types.md](docs/explanations/composite-types.md) - Composite type definitions
- XML files cached at `~/.cache/catio_terminals/beckhoff_xml/` - Actual Beckhoff ESI files grouped by series

**Key mappings from XML to YAML:**
- `Type@ProductCode` → `identity.product_code`
- `Type@RevisionNo` → `identity.revision_number`
- `TxPdo/Entry` → `symbol_nodes[]` (inputs)
- `RxPdo/Entry` → `symbol_nodes[]` (outputs)
- `Profile/Dictionary/Objects` → `coe_objects[]`

---

### ADS Simulator Testing Skill

**Activation prompts:**
- "Load simulator testing skill"
- "Help me test the ADS simulator"
- "How do I check simulator symbol count"
- "Test simulator against hardware"
- "Debug simulator symbols"

**Skill context:** Testing and validating the ADS simulator in `tests/ads_sim/`

**Key patterns:**

1. **Import the simulator correctly:**
   ```python
   import sys
   sys.path.insert(0, 'tests')  # Required for imports to work
   from ads_sim.ethercat_chain import EtherCATChain
   from pathlib import Path
   ```

2. **Instantiate and load configuration:**
   ```python
   chain = EtherCATChain()  # Create instance first
   chain.load_config(Path('tests/ads_sim/server_config.yaml'))  # Instance method, not class method
   ```

3. **Check symbol counts:**
   ```python
   print(f'Total symbols: {chain.total_symbol_count}')
   print(f'Hardware count: 550')
   print(f'Difference: {chain.total_symbol_count - 550}')
   ```

4. **Inspect devices and slaves:**
   ```python
   for dev_id, device in chain.devices.items():
       print(f'Device {dev_id}: {device.name}')
       for slave in device.slaves:
           print(f'  {slave.name} ({slave.type})')
           symbols = slave.get_symbols(dev_id, chain.runtime_symbols)
           print(f'    Symbols: {len(symbols)}')
   ```

5. **Debug specific terminal symbols (useful for PDO filtering issues):**
   ```python
   # Check which symbols are generated for a specific terminal type
   for dev_id, device in chain.devices.items():
       for slave in device.slaves:
           if 'EL1502' in slave.type:  # Replace with terminal type to debug
               symbols = slave.get_symbols(dev_id, chain.runtime_symbols)
               print(f'{slave.name} ({slave.type}): {len(symbols)} symbols')
               for sym in symbols:
                   print(f'  - {sym["name"]}')
   ```

**Common gotchas:**
- ❌ `from ads_sim...` without adding 'tests' to path → ModuleNotFoundError
- ❌ `EtherCATChain.load_config(path)` → TypeError (it's an instance method)
- ❌ `EtherCATChain.from_config(path)` → AttributeError (method doesn't exist)
- ✅ Create instance first, then call `load_config()` on it

**Testing against hardware and simulator:**
- Simulator or hardware output can be generated: `./tests/diagnose_hardware.py --ip 127.0.0.1 --dump-symbols`
- A YAML representation can be generated and compared
  - `./tests/diagnose_hardware.py --ip 127.0.0.1 --dump-symbols --output /tmp/sim.yaml`
  - `./tests/diagnose_hardware.py --ip 172.23.242.42 --dump-symbols --compare /tmp/sim.yaml`
  -


**Related files:**
- `tests/ads_sim/ethercat_chain.py` - Chain and device/slave models
- `tests/ads_sim/server.py` - ADS protocol server
- `tests/ads_sim/server_config.yaml` - default YAML representation of the Simulator
- `tests/test_system.py` - Integration tests against simulator

---

### Mermaid Diagrams in Documentation Skill

See [SKILLS.md](SKILLS.md#mermaid-diagrams-in-documentation-skill) for the full generic skill.

**Repo-specific notes:**

- Mermaid is already configured in this project (`docs/conf.py`, `docs/_static/custom.css`)
- Example Mermaid diagrams: `docs/explanations/architecture-overview.md`
- Do NOT convert TwinCAT device tree views (nomenclature.md) - keep as ASCII art

---

**Remember:** Prioritize clarity and maintainability over cleverness.
