"""Utility functions for catio_terminals."""

import re


def to_snake_case(name: str) -> str:
    """Convert symbol name to snake_case for FastCS attribute.

    Preserves {channel} placeholder for multi-channel symbols, placing it
    immediately after the word 'channel' if present.

    Args:
        name: Symbol name

    Returns:
        snake_case version of the name with {channel} positioned after 'channel'

    Examples:
        >>> to_snake_case("AI Inputs Channel {channel}")
        'ai_inputs_channel_{channel}'
        >>> to_snake_case("Status Word")
        'status_word'
        >>> to_snake_case("Channel {channel} Value")
        'channel_{channel}_value'

    Notes:
        The above '>>>' are picked up as test cases by doctest. And they pass!
    """
    # Check if name contains {channel} placeholder
    has_channel = "{channel}" in name

    # Remove {channel} temporarily for processing
    name_without_placeholder = name.replace("{channel}", "")

    # Replace special characters with spaces
    name_clean = re.sub(r"[^a-zA-Z0-9]+", " ", name_without_placeholder)
    # Split on spaces and convert to lowercase
    words = [word.lower() for word in name_clean.split() if word]

    # If has channel placeholder, insert it after the word 'channel'
    if has_channel:
        try:
            channel_idx = words.index("channel")
            words.insert(channel_idx + 1, "{channel}")
        except ValueError:
            # No 'channel' word found, append at end
            words.append("{channel}")

    return "_".join(words)
