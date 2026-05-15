"""Test for duplicate fastcs_name entries in terminal YAML definitions.

This test ensures that when new terminal types are added or existing ones
are regenerated using the catio-terminals tool, no duplicate fastcs_name
values are created that could cause attribute conflicts in FastCS controllers.

The test checks both symbol_nodes and CoE subindices for duplicates. If any duplicates
are found, it reports the terminal type, the conflicting fastcs_name, and the relevant
symbol or CoE subindex details to help developers identify and resolve the issue.
Addition to the _ABBREVIATIONS dictionary in utils.py may be needed to create unique
fastcs_name values when generating from long symbol names.
"""

from pathlib import Path

import pytest
import yaml


def load_terminal_types() -> dict:
    """Load the terminal types YAML file.

    Returns:
        Dictionary containing terminal type definitions

    Raises:
        FileNotFoundError: If terminal_types.yaml cannot be found
    """
    yaml_path = (
        Path(__file__).parent.parent
        / "src"
        / "catio_terminals"
        / "terminals"
        / "terminal_types.yaml"
    )
    if not yaml_path.exists():
        raise FileNotFoundError(f"terminal_types.yaml not found at {yaml_path}")

    with open(yaml_path) as f:
        return yaml.safe_load(f)


def test_no_duplicate_fastcs_names_in_symbol_nodes():
    """Check that no terminal type has duplicate fastcs_name values in symbol_nodes.

    This prevents the "has existing attribute" error when FastCS initializes
    multi-channel symbols dynamically.

    Example of the issue:
        - "AI TxPDO-Map Standard Channel {channel}.Status__Limit 1"
          -> ai_txpdo_map_standard_ch_{channel}_sts
        - "AI TxPDO-Map Standard Channel {channel}.Status__Limit 2"
          -> ai_txpdo_map_standard_ch_{channel}_sts
        Both map to the same fastcs_name, causing a duplicate attribute error.
    """
    terminal_types = load_terminal_types()

    duplicates_found = {}

    for terminal_name, terminal_def in terminal_types.items():
        symbol_nodes = terminal_def.get("symbol_nodes", [])

        # Extract fastcs_name values for this terminal
        fastcs_names = {}
        for i, node in enumerate(symbol_nodes):
            fastcs_name = node.get("fastcs_name")
            if fastcs_name:
                if fastcs_name not in fastcs_names:
                    fastcs_names[fastcs_name] = []
                fastcs_names[fastcs_name].append(
                    {
                        "index": i,
                        "name_template": node.get("name_template"),
                    }
                )

        # Check for duplicates
        for fastcs_name, occurrences in fastcs_names.items():
            if len(occurrences) > 1:
                if terminal_name not in duplicates_found:
                    duplicates_found[terminal_name] = {}
                duplicates_found[terminal_name][fastcs_name] = occurrences

    # Report findings
    if duplicates_found:
        error_msg = "Duplicate fastcs_name values found in terminal symbol_nodes:\n"
        for terminal_name, dups in sorted(duplicates_found.items()):
            error_msg += f"\n  {terminal_name}:\n"
            for fastcs_name, occurrences in sorted(dups.items()):
                error_msg += f"    {fastcs_name} (appears {len(occurrences)} times):\n"
                for occ in occurrences:
                    error_msg += f"      [{occ['index']}] {occ['name_template']}\n"
        pytest.fail(error_msg)


def test_no_duplicate_fastcs_names_in_coe_subindices():
    """Check that no terminal type has duplicate fastcs_name values in CoE subindices.

    CoE objects can have multiple subindices with unique names. Each must have
    a unique fastcs_name to avoid attribute conflicts.
    """
    terminal_types = load_terminal_types()

    duplicates_found = {}

    for terminal_name, terminal_def in terminal_types.items():
        coe_objects = terminal_def.get("coe_objects", [])

        for obj_idx, coe_obj in enumerate(coe_objects):
            subindices = coe_obj.get("subindices", [])

            # Extract fastcs_name values for this CoE object
            fastcs_names = {}
            for sub_idx, subindex in enumerate(subindices):
                fastcs_name = subindex.get("fastcs_name")
                if fastcs_name:
                    if fastcs_name not in fastcs_names:
                        fastcs_names[fastcs_name] = []
                    fastcs_names[fastcs_name].append(
                        {
                            "obj_index": obj_idx,
                            "sub_index": sub_idx,
                            "name": subindex.get("name"),
                            "coe_index": coe_obj.get("index"),
                        }
                    )

            # Check for duplicates
            for fastcs_name, occurrences in fastcs_names.items():
                if len(occurrences) > 1:
                    if terminal_name not in duplicates_found:
                        duplicates_found[terminal_name] = {}
                    duplicates_found[terminal_name][fastcs_name] = occurrences

    # Report findings
    if duplicates_found:
        error_msg = "Duplicate fastcs_name values found in terminal CoE subindices:\n"
        for terminal_name, dups in sorted(duplicates_found.items()):
            error_msg += f"\n  {terminal_name}:\n"
            for fastcs_name, occurrences in sorted(dups.items()):
                error_msg += f"    {fastcs_name} (appears {len(occurrences)} times):\n"
                for occ in occurrences:
                    error_msg += (
                        f"      [CoE 0x{occ['coe_index']:04x}, "
                        f"subindex {occ['sub_index']}] {occ['name']}\n"
                    )
        pytest.fail(error_msg)
