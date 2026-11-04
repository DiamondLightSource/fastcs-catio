# Documentation Plan

This document outlines remaining documentation tasks and suggested agent prompts for improving the documentation.

## Outstanding Tasks

### High Priority

- [ ] **Add Getting Started tutorial**: Create a step-by-step guide for first-time users covering installation, connection to TwinCAT, and running the IOC
- [ ] **Document CoE parameter write support**: If/when implemented, document how to write CoE configuration parameters

### Medium Priority

- [ ] **Add troubleshooting guide**: Common connection issues, ADS errors, and their solutions
- [ ] **Document notification subscriptions**: How to subscribe to high-frequency data updates using ADS notifications
- [ ] **Add configuration reference**: Document all CLI options and environment variables

### Low Priority

- [ ] **Add example scripts**: Python examples showing common use cases
- [ ] **Expand DLS terminals reference**: Add more detail on each terminal type's capabilities

## Agent Prompts for Documentation Improvement

Use these prompts to get AI assistance with documentation tasks:

### Architecture and Design

```
Review the architecture-overview.md and suggest improvements to make the Mermaid diagrams clearer and more informative.
```

```
Compare fastcs-epics-ioc.md and ads-client.md for consistency in terminology and cross-references.
```

### Terminal Definitions

```
Load Beckhoff XML skill and help me document a new terminal type [terminal-id].
```

```
Review terminal-yaml-definitions.md and identify any information that is out of date with the current code.
```

### Code Documentation

```
Review the docstrings in src/fastcs_catio/client.py and suggest improvements for clarity and completeness.
```

### User Guides

```
Write a troubleshooting guide covering common ADS connection errors and their solutions.
```

```
Create a getting-started tutorial that walks through connecting to a TwinCAT PLC and reading analog input values.
```

## Documentation Structure

The documentation follows the [Diátaxis](https://diataxis.fr/) framework:

| Section | Purpose | Files |
|---------|---------|-------|
| **Tutorials** | Learning-oriented | `tutorials/installation.md` |
| **How-to** | Task-oriented | `how-to/` directory |
| **Explanations** | Understanding-oriented | `explanations/` directory |
| **Reference** | Information-oriented | `reference/` directory, `_api/` |

When adding new documentation, place it in the appropriate section based on its purpose.
