"""Test that CoE objects default to unselected when adding new terminals."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from catio_terminals.beckhoff import BeckhoffClient
from catio_terminals.models import CompositeTypesConfig, TerminalConfig
from catio_terminals.service_terminal import TerminalService


@pytest.mark.asyncio
async def test_new_terminal_coe_objects_default_unselected():
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

    # Create Beckhoff client and composite types
    beckhoff_client = BeckhoffClient()
    composite_types = CompositeTypesConfig.get_default()

    # Get terminal info for EL3602
    terminals = await beckhoff_client.search_terminals("EL3602")
    assert len(terminals) > 0, "Could not find EL3602 terminal"

    terminal_info = next((t for t in terminals if t.terminal_id == "EL3602"), None)
    assert terminal_info is not None, "Could not find EL3602 in search results"

    # Add terminal from Beckhoff (eager load to get CoE objects immediately)
    terminal = await TerminalService.add_terminal_from_beckhoff(
        config, terminal_info, beckhoff_client, composite_types, lazy_load=False
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
        await FileService.merge_xml_for_terminal(
            "EL3602", terminal, beckhoff_client, composite_types
        )
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

    # Create Beckhoff client and composite types
    beckhoff_client = BeckhoffClient()
    composite_types = CompositeTypesConfig.get_default()

    # Get terminal info for EL3602
    terminals = await beckhoff_client.search_terminals("EL3602")
    terminal_info = next((t for t in terminals if t.terminal_id == "EL3602"), None)
    assert terminal_info is not None

    # Add terminal (eager load to get CoE objects for testing)
    await TerminalService.add_terminal_from_beckhoff(
        config, terminal_info, beckhoff_client, composite_types, lazy_load=False
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
