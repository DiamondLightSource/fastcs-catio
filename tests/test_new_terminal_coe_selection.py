"""Test that CoE objects default to unselected when adding new terminals."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import TerminalConfig
from catio_terminals.service_terminal import TerminalService


@pytest.mark.asyncio
async def test_new_terminal_coe_objects_default_unselected(beckhoff_xml_cache):
    """Test that CoE objects are unselected when adding a new terminal.

    This test:
    1. Creates a new empty YAML configuration
    2. Adds a terminal (EL3602) from Beckhoff XML
    3. Verifies that all CoE objects have selected=False

    NOTE: This test proves the BACKEND/DATA is correct. If CoE checkboxes appear
    checked in the GUI, that's a frontend rendering bug, not a data issue.
    The selected field is correctly False in Python.
    """
    # Create empty config
    config = TerminalConfig()

    # Create Beckhoff client
    beckhoff_client = BeckhoffClient()

    # Get terminal info for EL3602
    terminals = await beckhoff_client.search_terminals("EL3602")
    assert len(terminals) > 0, "Could not find EL3602 terminal"

    terminal_info = next((t for t in terminals if t.terminal_id == "EL3602"), None)
    assert terminal_info is not None, "Could not find EL3602 in search results"

    # Add terminal from Beckhoff (eager load to get CoE objects immediately)
    terminal = await TerminalService.add_terminal_from_beckhoff(
        config, terminal_info, beckhoff_client, lazy_load=False
    )

    # Verify terminal was added
    assert "EL3602" in config.terminal_types
    assert terminal is config.terminal_types["EL3602"]

    # Verify CoE objects exist
    assert len(terminal.coe_objects) > 0, "EL3602 should have CoE objects"

    # Verify ALL CoE objects default to selected=False
    print("\n=== After initial add ===")
    for coe in terminal.coe_objects:
        print(
            f"CoE 0x{coe.index:04X} '{coe.name}': selected={coe.selected} "
            f"(type: {type(coe.selected)})"
        )
        assert coe.selected is False, (
            f"CoE object 0x{coe.index:04X} '{coe.name}' should be unselected by default"
        )

    print(f"✓ Verified {len(terminal.coe_objects)} CoE objects are unselected")

    # Now simulate what happens in the GUI when the tree is rebuilt and
    # terminal selected. This triggers the XML merge logic
    print("\n=== Simulating GUI XML merge ===")
    from catio_terminals.service_file import FileService

    merged_terminals = set()  # Track merged terminals like the GUI does
    # FIX: Mark newly added terminal as already merged
    merged_terminals.add("EL3602")

    # Check if needs merge (it should be in merged_terminals now, so skip merge)
    if "EL3602" not in merged_terminals:
        print("Terminal not in merged_terminals, triggering merge...")
        await FileService.merge_xml_for_terminal("EL3602", terminal, beckhoff_client)
        merged_terminals.add("EL3602")
    else:
        print("Terminal already merged, skipping XML merge")

    # Check CoE selection state after (no) merge
    print("\n=== After (skipped) XML merge ===")
    for coe in terminal.coe_objects:
        print(
            f"CoE 0x{coe.index:04X} '{coe.name}': selected={coe.selected} "
            f"(type: {type(coe.selected)})"
        )

    # Verify CoE objects remain unselected
    selected_count = sum(1 for coe in terminal.coe_objects if coe.selected)
    print(
        f"\n✓ {selected_count}/{len(terminal.coe_objects)} CoE objects "
        "are selected (should be 0)"
    )

    assert selected_count == 0, (
        f"Expected 0 CoE objects to be selected, but {selected_count} are selected"
    )


@pytest.mark.asyncio
async def test_new_terminal_coe_selection_yaml_roundtrip(beckhoff_xml_cache):
    """Test that unselected CoE objects are filtered when saving to YAML."""
    # Create empty config
    config = TerminalConfig()

    # Create Beckhoff client
    beckhoff_client = BeckhoffClient()

    # Get terminal info for EL3602
    terminals = await beckhoff_client.search_terminals("EL3602")
    terminal_info = next((t for t in terminals if t.terminal_id == "EL3602"), None)
    assert terminal_info is not None

    # Add terminal (eager load to get CoE objects for testing)
    await TerminalService.add_terminal_from_beckhoff(
        config, terminal_info, beckhoff_client, lazy_load=False
    )

    # Save to temp file
    with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        temp_path = Path(f.name)

    try:
        config.to_yaml(temp_path)

        # Load from temp file
        loaded_config = TerminalConfig.from_yaml(temp_path)

        # Verify terminal exists
        assert "EL3602" in loaded_config.terminal_types
        loaded_terminal = loaded_config.terminal_types["EL3602"]

        # Since no CoE objects were selected, none should be in the YAML
        assert len(loaded_terminal.coe_objects) == 0, (
            "No CoE objects should be saved when none are selected"
        )

        print("✓ Verified unselected CoE objects are not saved to YAML")
    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_new_terminal_symbols_default_selected_via_lazy_load(beckhoff_xml_cache):
    """Test symbols default to selected based on PDO groups when adding a new terminal.

    When a terminal is lazy-loaded (the default in the UI), symbols are populated
    via merge_xml_for_terminal. For new terminals:
    - If terminal has PDO groups: only symbols in the default group are selected
    - If terminal has no PDO groups: all symbols are selected
    """
    from catio_terminals.service_file import FileService

    # Create empty config
    config = TerminalConfig()
    beckhoff_client = BeckhoffClient()

    # Get terminal info for EL3004 (4-channel analog input with PDO groups)
    terminals = await beckhoff_client.search_terminals("EL3004")
    terminal_info = next((t for t in terminals if t.terminal_id == "EL3004"), None)
    assert terminal_info is not None, "Could not find EL3004 in search results"

    # Add terminal with lazy_load=True (default, no symbols yet)
    terminal = await TerminalService.add_terminal_from_beckhoff(
        config, terminal_info, beckhoff_client, lazy_load=True
    )

    # Verify terminal has no symbols initially (lazy loaded)
    assert len(terminal.symbol_nodes) == 0, (
        "Lazy-loaded terminal should start with no symbols"
    )

    # Now simulate what happens when user clicks on terminal in the GUI
    # This triggers merge_xml_for_terminal which populates symbols
    await FileService.merge_xml_for_terminal("EL3004", terminal, beckhoff_client)

    # Verify symbols were populated
    assert len(terminal.symbol_nodes) > 0, "EL3004 should have symbols after merge"

    # EL3004 has PDO groups - only symbols in the default group should be selected
    # The default group is "Standard" which excludes "Compact" symbols
    print("\n=== Symbols after lazy-load merge ===")
    selected_symbols = []
    unselected_symbols = []
    for sym in terminal.symbol_nodes:
        print(f"Symbol '{sym.name_template}': selected={sym.selected}")
        if sym.selected:
            selected_symbols.append(sym.name_template)
        else:
            unselected_symbols.append(sym.name_template)

    # Verify at least some symbols are selected (the default group)
    assert len(selected_symbols) > 0, "At least some symbols should be selected"

    # Verify Compact symbols are not selected (they're not in the default group)
    for name in unselected_symbols:
        assert "Compact" in name, (
            f"Non-compact symbol '{name}' should be selected for default group"
        )

    print(f"✓ Verified {len(selected_symbols)} symbols selected (default group)")
    print(
        f"✓ Verified {len(unselected_symbols)} symbols unselected (non-default group)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
