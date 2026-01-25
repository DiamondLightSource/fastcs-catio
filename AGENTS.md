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

## Code Style and Formatting

- **MUST** use meaningful, descriptive variable and function names
- **MUST** follow PEP 8 style guidelines
- **NEVER** use emoji, or unicode that emulates emoji (e.g. ✓, ✗). The only exception is when writing tests and testing the impact of multibyte characters.
- Limit line length to 88 characters (ruff formatter standard)
- **ALWAYS** run `uv ruff check` to format and validated code before committing

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
- **MUST** mock external dependencies (APIs, databases, file systems)
- **MUST** use pytest as the testing framework
- **NEVER** run tests you generate without first saving them as their own discrete file
- **NEVER** delete files created as a part of testing.
- Ensure the folder used for test outputs is present in `.gitignore`
- Follow the Arrange-Act-Assert pattern
- Do not commit commented-out tests

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

- **MUST** use uv to run all the tools below
- **MUST** use Ruff for code formatting and linting
- **MUST** use pyright for static type checking
- **MUST** use `uv` for package management
- Use pytest for testing

## Before Committing

- [ ] All tests pass
- [ ] Type checking passes (mypy)
- [ ] Code formatter and linter pass (Ruff)
- [ ] All functions have docstrings and type hints
- [ ] No commented-out code or debug statements
- [ ] No hardcoded credentials

## Domain Knowledge

This project interfaces with Beckhoff EtherCAT I/O terminals via the ADS protocol. Key concepts:

- **Terminal Definitions**: YAML files describing Beckhoff terminal types, their symbols, and CoE objects. See [docs/explanations/terminal-definitions.md](docs/explanations/terminal-definitions.md) for:
  - How to generate terminal YAML files using `catio-terminals`
  - Understanding ADS symbol nodes and index groups
  - The difference between XML-defined symbols and ADS runtime symbols (e.g., `WcState`)
  - CoE (CANopen over EtherCAT) object definitions

- **Beckhoff XML Files**: ESI (EtherCAT Slave Information) XML files from Beckhoff group terminals by series:
  - `Beckhoff EL31xx.xml` contains EL3104, EL3124, etc.
  - `Beckhoff EL32xx.xml` contains EL3202, EL3204, etc.
  - Cached at `~/.cache/catio_terminals/beckhoff_xml/`
  - Use `catio-terminals --update-cache` to download/refresh

- **Composite Types**: TwinCAT BIGTYPE structures (ads_type=65) that group primitive fields:
  - Defined in `src/catio_terminals/config/composite_types.yaml`
  - Example: `"AI Standard Channel 1_TYPE"` contains Status (UINT) + Value (INT)
  - Used by simulator for accurate symbol table responses
  - Used by FastCS generator to create controller attributes

- **catio-terminals**: GUI editor for terminal YAML files. Use `catio-terminals --update-cache` to fetch Beckhoff XML definitions, then edit files with the GUI.

## Agent Skills

Skills are specialized knowledge that can be loaded on demand. Use these prompts to activate a skill:

### Beckhoff XML Format Skill

**Activation prompts:**
- "Load Beckhoff XML skill"
- "I need to work with ESI XML files"
- "Help me understand the Beckhoff XML format"

**Skill context:** Read [docs/reference/beckhoff-xml-format.md](docs/reference/beckhoff-xml-format.md) for:
- XML file naming conventions (terminals grouped by series: EL31xx.xml, EL32xx.xml, etc.)
- ESI schema structure (Device, TxPdo, RxPdo, Entry, CoE objects)
- Mapping between XML elements and terminal YAML fields
- What information is NOT in XML (composite type names, ADS offsets)

### Terminal Definitions Skill

**Activation prompts:**
- "Load terminal definitions skill"
- "Help me edit terminal YAML files"
- "I need to understand composite types"
- "Help me with symbol grouping"

**Skill context:** Read these documents:
- [docs/explanations/terminal-yaml-definitions.md](docs/explanations/terminal-yaml-definitions.md) - Terminal YAML structure (identity, symbol_nodes, coe_objects), SymbolNode fields, computed properties, channel templating
- [src/catio_terminals/config/composite_types.yaml](src/catio_terminals/config/composite_types.yaml) - Composite type definitions (members, offsets, sizes)

---

**Remember:** Prioritize clarity and maintainability over cleverness.
