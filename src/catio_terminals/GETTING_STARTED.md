# Getting Started with catio_terminals

## Quick Start

1. **Install the dependencies:**
   ```bash
   uv pip install -e ".[terminals]"
   ```

2. **Launch the application:**
   ```bash
   # Open GUI without a file
   catio-terminals

   # Or open GUI with a specific file
   catio-terminals edit path/to/terminals.yaml
   ```

   Or:
   ```bash
   python -m catio_terminals
   ```

3. **Choose your workflow:**
   - Click "Open" to edit an existing YAML file
   - Click "Create New" to start a new configuration

## Using the Editor

### Main Interface

The editor has three main sections:

1. **Header**: Contains Save and Add Terminal buttons
2. **Left Panel**: Tree view of terminal types and their symbols
3. **Right Panel**: Details and editing interface for selected items

### Adding a Terminal

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

### Editing Terminal Details

1. **Select a Terminal** in the tree view
2. View terminal information in the right panel:
   - Description
   - Identity (Vendor ID, Product Code, Revision)
   - List of symbols
3. Click **"Delete Terminal"** to remove it

### Editing Symbol Details

1. **Expand a terminal** in the tree view
2. **Click on a symbol** to edit it
3. Modify the fields:
   - **Name Template**: Pattern for symbol names (use `{channel}` for channel number)
   - **Index Group**: ADS index group (hex format)
   - **Size**: Data size in bytes
   - **ADS Type**: ADS data type code
   - **Channels**: Number of channels for this symbol
   - **Type Name**: The type name string

4. Changes are saved automatically in memory

### Saving Your Work

1. Click **"Save"** in the header
2. The file is written to disk in YAML format
3. A notification confirms the save

## Example Workflow

Let's create a configuration for analog output terminals:

1. **Start the application**
   ```bash
   catio-terminals
   ```

2. **Create a new file**
   - File Path: `/path/to/my_terminals.yaml`
   - Click "Create New"

3. **Add EL4004 terminal**
   - Click "Add Terminal"
   - Search for "EL4004"
   - Click "Add" on the result

4. **Verify the terminal**
   - Click on "EL4004" in the tree
   - Check description and identity
   - Expand to see symbols

5. **Edit a symbol if needed**
   - Click on a symbol under EL4004
   - Modify fields as needed

6. **Save**
   - Click "Save"
   - File is written to disk

## Tips

- **Use meaningful Terminal IDs**: Follow Beckhoff naming conventions (e.g., EL4004, EL2008)
- **Channels**: Set the channels field to generate multiple instances of a symbol
- **Hex Values**: Index groups are displayed and entered in hexadecimal (0xF030)
- **Name Templates**: Use `{channel}` placeholder for channel-based naming
- **Auto-save**: The app doesn't auto-save; remember to click Save before closing

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
- Currently returns common terminals (placeholder implementation)
- Future versions will integrate with actual Beckhoff catalog

## Advanced Usage

### Manual YAML Editing

You can also edit the YAML files directly. They follow this structure:

```yaml
terminal_types:
  TERMINAL_ID:
    description: "Terminal description"
    identity:
      vendor_id: 2
      product_code: 0x12345678
      revision_number: 0x00100000
    symbol_nodes:
      - name_template: "Symbol Name {channel}"
        index_group: 0xF030
        size: 2
        ads_type: 65
        type_name: "TYPE_NAME"
        channels: 4
```

### Integration with fastcs-catio

The YAML files created by this tool are designed to work with the fastcs-catio project. Place them in:

```
src/catio_terminals/terminals/
```

## Next Steps

- Explore existing YAML files in `src/catio_terminals/terminals/`
- Try creating configurations for your specific terminals
- Integrate with your fastcs-catio setup
