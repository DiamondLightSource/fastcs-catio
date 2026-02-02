# Using the Terminal Editor

The `catio-terminals` GUI editor allows you to create and edit terminal description YAML files used in the fastcs-catio project.

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

## Launching the Editor

Launch the terminal editor:

```bash
# Open GUI without a file (choose Open or Create New at startup)
catio-terminals edit

# Open GUI with a specific file
catio-terminals edit path/to/terminals.yaml
```

Or run as a Python module:

```bash
python -m catio_terminals
```

## Getting Started

1. **At Startup**: Choose to open an existing YAML file or create a new one
2. **Tree View**: Browse terminal types in the left panel
3. **Details Panel**: Click on a terminal or symbol to view/edit details in the right panel
4. **Add Terminal**: Click "Add Terminal" to search Beckhoff's catalog or create manually
5. **Save**: Click "Save" to write changes back to the YAML file

## Main Interface

The editor has three main sections:

1. **Header**: Contains Save and Add Terminal buttons
2. **Left Panel**: Tree view of terminal types and their symbols
3. **Right Panel**: Details and editing interface for selected items

## Adding a Terminal

1. Click **"Add Terminal"** button in the header
2. Choose one of two methods:

   **Method 1: Search Beckhoff Catalog**
   - Enter search terms in the search box
   - Click "Search"
   - Browse results and click "Add" on your chosen terminal
   - The terminal information will be populated automatically

   **Method 2: Create Manually**
   - Scroll to the bottom of the dialog
   - Enter Terminal ID (e.g., "EL4004")
   - Enter Description
   - Click "Create Manually"
   - Edit the default values as needed

## Editing Terminal Details

1. **Select a Terminal** in the tree view
2. View terminal information in the right panel:
   - Description
   - Identity (Vendor ID, Product Code, Revision)
   - List of symbols
3. Click **"Delete Terminal"** to remove it

## Editing Symbol Details

1. **Expand a terminal** in the tree view
2. **Click on a symbol** to edit it
3. Modify the fields:
   - **Name Template**: Pattern for symbol names (use `{channel}` for channel number)
   - **FastCS Name**: The PascalCase attribute name for FastCS (use `{channel}` for multi-channel)
   - **Index Group**: ADS index group (hex format)
   - **Size**: Data size in bytes
   - **ADS Type**: ADS data type code
   - **Channels**: Number of channels for this symbol
   - **Type Name**: The type name string
   - **Access**: Read-only, write-only, or read-write
   - **Tooltip**: Description for the symbol

4. Changes are saved automatically in memory

## YAML File Structure

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
        fastcs_name: "AoOutputChannel{channel}"
        index_group: 0xF030
        size: 2
        ads_type: 65
        type_name: "AO Output Channel 1_TYPE"
        channels: 4
        access: "read-write"
        tooltip: "Analog output channel value"
        selected: true
      - name_template: "WcState^WcState"
        fastcs_name: "WcState"
        index_group: 0xF021
        size: 0
        ads_type: 33
        type_name: "BIT"
        channels: 1
        access: "read-only"
        selected: true
```

## Tips

- **Use meaningful Terminal IDs**: Follow Beckhoff naming conventions (e.g., EL4004, EL2008)
- **Channels**: Set the channels field to generate multiple instances of a symbol
- **Hex Values**: Index groups are displayed and entered in hexadecimal (0xF030)
- **Name Templates**: Use `{channel}` placeholder for channel-based naming in both `name_template` and `fastcs_name`
- **FastCS Names**: Use PascalCase for FastCS attribute names (e.g., `AoOutputChannel{channel}`)
- **Selection**: The `selected` field controls which symbols are included in dynamic controllers
- **Auto-save**: The app doesn't auto-save; remember to click Save before closing

## Saving Your Work

1. Click **"Save"** in the header
2. The file is written to disk in YAML format
3. A notification confirms the save

## Integration with fastcs-catio

The YAML files created by this tool are designed to work with the fastcs-catio project. Place them in:

```
src/catio_terminals/terminals/
```

These files are automatically loaded by the dynamic controller system to generate FastCS controllers at runtime.

## Architecture

The `catio_terminals` package consists of several modules:

- **models.py**: Pydantic data models for YAML structure
- **beckhoff.py**: Client for fetching Beckhoff terminal information
- **xml_cache.py**: Caching system for Beckhoff XML files
- **xml_parser.py**: Parser for Beckhoff ESI XML files
- **app.py**: Main NiceGUI application
- **__main__.py**: Entry point for the application

## Troubleshooting

### File Not Loading
- Ensure the YAML file is valid YAML format
- Check file permissions
- View error message in notification

### Terminal Not Saving
- Ensure file path is writable
- Check disk space
- View error in notification

### Beckhoff Search Not Working
- The app downloads and caches Beckhoff XML files on first use
- Check internet connectivity
- View cache status in `~/.cache/catio_terminals/`
