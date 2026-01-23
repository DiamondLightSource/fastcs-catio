"""Utility functions for catio_terminals."""

import re


def to_pascal_case(name: str) -> str:
    """Convert symbol name to PascalCase for FastCS attribute.

    Preserves {channel} placeholder for multi-channel symbols.

    Args:
        name: Symbol name

    Returns:
        PascalCase version of the name with {channel} preserved

    Examples:
        >>> to_pascal_case("AI Inputs Channel {channel}")
        'AiInputsChannel{channel}'
        >>> to_pascal_case("Status Word")
        'StatusWord'
    """
    # Check if name contains {channel} placeholder
    has_channel = "{channel}" in name

    # Remove {channel} temporarily for processing
    name_without_placeholder = name.replace("{channel}", "")

    # Replace special characters with spaces
    name_clean = re.sub(r"[^a-zA-Z0-9]+", " ", name_without_placeholder)
    # Split on spaces and capitalize each word
    words = name_clean.split()
    pascal_name = "".join(word.capitalize() for word in words if word)

    # Add back {channel} placeholder if it was present
    if has_channel:
        pascal_name += "{channel}"

    return pascal_name
