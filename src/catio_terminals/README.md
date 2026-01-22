# catio_terminals

A GUI editor for terminal description YAML files used in the fastcs-catio project.

## Features

- **File Management**: Open existing YAML files or create new ones
- **Tree View**: Navigate terminal types and their symbols in an intuitive tree structure
- **Terminal Management**:
  - Add new terminal types by searching Beckhoff's catalog
  - Delete existing terminal types
  - Edit terminal properties and symbol definitions
- **Beckhoff Integration**:
  - Search for Beckhoff terminal types
  - Automatically populate terminal information from XML descriptions
- **Live Editing**: Edit symbol properties with immediate feedback

## Installation

Install the package with the terminals extra:

```bash
uv pip install -e ".[terminals]"
```

Or install the required dependencies separately:

```bash
uv pip install nicegui pydantic pyyaml httpx
```

## Usage

Launch the terminal editor:

```bash
catio-terminals
```

Or run as a Python module:

```bash
python -m catio_terminals
```

### Getting Started

1. **At Startup**: Choose to open an existing YAML file or create a new one
2. **Tree View**: Browse terminal types in the left panel
3. **Details Panel**: Click on a terminal or symbol to view/edit details in the right panel
4. **Add Terminal**: Click "Add Terminal" to search Beckhoff's catalog or create manually
5. **Save**: Click "Save" to write changes back to the YAML file

### YAML File Structure

Terminal YAML files follow this structure:

```yaml
terminal_types:
  EL4004:
    description: "4-channel Analog Output 0..10V 12-bit"
    identity:
      vendor_id: 2
      product_code: 0x0FA43052
      revision_number: 0x00100000
    symbol_nodes:
      - name_template: "AO Output Channel {channel}"
        index_group: 0xF030
        size: 2
        ads_type: 65
        type_name: "AO Output Channel 1_TYPE"
        channels: 4
      - name_template: "WcState^WcState"
        index_group: 0xF021
        size: 0
        ads_type: 33
        type_name: "BIT"
        channels: 1
```

## Architecture

The package consists of several modules:

- **models.py**: Pydantic data models for YAML structure
- **beckhoff.py**: Client for fetching Beckhoff terminal information
- **app.py**: Main NiceGUI application
- **__main__.py**: Entry point for the application

## Development

### Requirements

- Python >= 3.11
- NiceGUI >= 2.0.0
- Pydantic >= 2.0.0
- PyYAML >= 6.0
- httpx >= 0.27.0

### Running from Source

```bash
# Install in development mode
uv pip install -e ".[terminals]"

# Run the application
python -m catio_terminals
```

### Code Quality

This package follows the same code quality standards as the main fastcs-catio project:

```bash
# Format and lint
uv ruff check --fix src/catio_terminals

# Type checking
uv pyright src/catio_terminals

# Run tests
uv pytest tests/
```

## Future Enhancements

- **Real Beckhoff Integration**: Currently uses placeholder data; could be enhanced to:
  - Parse actual ESI XML files from TwinCAT installation
  - Scrape Beckhoff website for terminal information
  - Download XML descriptions automatically
- **Validation**: Add validation for terminal configurations
- **Templates**: Provide templates for common terminal types
- **Import/Export**: Support importing from other formats
- **Symbol Editor**: Enhanced symbol editing with validation

## License

Apache License 2.0 - see LICENSE file for details
