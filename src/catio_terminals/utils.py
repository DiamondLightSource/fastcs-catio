"""Utility functions for catio_terminals."""

import re

# Common words that can be abbreviated when truncating names
_ABBREVIATIONS = {
    "channel": "ch",
    "subindex": "si",
    "counter": "cnt",
    "output": "out",
    "input": "in",
    "status": "sts",
    "value": "val",
    "parameter": "par",
    "parameters": "pars",
    "settings": "set",
    "minimum": "min",
    "maximum": "max",
    "threshold": "thr",
    "treshold": "thr",  # Handle typo in Beckhoff XML
    "enable": "en",
    "disable": "dis",
    "function": "fn",
    "functions": "fns",
    "synchron": "sync",
    "diagnosis": "diag",
    "default": "def",
    "modular": "mod",
    "device": "dev",
    "identity": "id",
    "hardware": "hw",
    "software": "sw",
    "version": "ver",
    "restore": "rst",
    "backup": "bak",
    "checksum": "csum",
    "activate": "act",
    "impulse": "imp",
    "length": "len",
    "trigger": "trig",
    "delay": "dly",
    "feedback": "fb",
    "current": "cur",
    "number": "num",
    "serial": "ser",
    "revision": "rev",
    "product": "prod",
    "vendor": "vnd",
    "assign": "asn",
    "reload": "rld",
    "switch": "sw",
    "inhibit": "inh",
    "inhibited": "inh",
}


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


def make_fastcs_name(name: str, max_length: int = 40) -> str:
    """Create fastcs_name with length limit and abbreviations.

    Converts name to snake_case. If the result exceeds max_length,
    applies abbreviations to reduce length while preserving readability.

    Args:
        name: Original name
        max_length: Maximum allowed length (default 40)

    Returns:
        snake_case name under max_length characters

    Examples:
        >>> make_fastcs_name("AI Inputs")
        'ai_inputs'
        >>> make_fastcs_name("Very Long Parameter Name With Many Words", 25)
        'very_long_par_name_with'
        >>> len(make_fastcs_name("Status Input Cycle Counter Channel 1")) <= 40
        True
    """
    snake = to_snake_case(name)
    if len(snake) <= max_length:
        return snake

    # Apply abbreviations
    words = snake.split("_")
    abbreviated = _abbreviate_words(words)
    abbreviated = _remove_duplicate_words(abbreviated)
    result = "_".join(abbreviated)
    if len(result) <= max_length:
        return result

    # Final fallback: truncate at word boundary
    if len(result) > max_length:
        truncated = result[:max_length]
        last_underscore = truncated.rfind("_")
        if last_underscore > max_length // 2:
            truncated = truncated[:last_underscore]
        result = truncated

    return result


def _abbreviate_words(words: list[str]) -> list[str]:
    """Abbreviate common words to reduce name length.

    Args:
        words: List of lowercase words

    Returns:
        List with common words abbreviated
    """
    return [_ABBREVIATIONS.get(word, word) for word in words]


def _remove_duplicate_words(words: list[str]) -> list[str]:
    """Remove consecutive duplicate words and parent-child duplicates.

    Args:
        words: List of words

    Returns:
        List with duplicates removed
    """
    if not words:
        return words

    result = [words[0]]
    for word in words[1:]:
        if word != result[-1]:
            result.append(word)
    return result


def make_subindex_fastcs_name(
    parent_name: str, subindex_name: str, max_length: int = 40
) -> str:
    """Create unique fastcs_name for subindex including parent context.

    Combines parent CoE object name with subindex name to create a unique
    identifier. If the combined name exceeds max_length, applies abbreviations
    and truncation strategies while preserving readability.

    Args:
        parent_name: Parent CoE object name
        subindex_name: SubIndex name
        max_length: Maximum allowed length (default 40)

    Returns:
        Unique snake_case name under max_length characters

    Examples:
        >>> make_subindex_fastcs_name("CNT Settings Ch.1", "SubIndex 000")
        'cnt_settings_ch_1_subindex_000'
        >>> make_subindex_fastcs_name("CNT Inputs Ch.1", "Counter value")
        'cnt_inputs_ch_1_counter_value'
        >>> make_subindex_fastcs_name("Identity", "Vendor ID")
        'identity_vendor_id'
        >>> long_parent = "Very Long Parent Object Name Here"
        >>> long_sub = "And A Very Long SubIndex Name Too"
        >>> len(make_subindex_fastcs_name(long_parent, long_sub)) <= 40
        True
        >>> make_subindex_fastcs_name("SM input parameter", "Minimum fast cycle time")
        'sm_in_par_min_fast_cycle_time'
    """
    # Convert both names to snake_case first
    parent_snake = to_snake_case(parent_name)
    sub_snake = to_snake_case(subindex_name)

    # Split into words
    parent_words = parent_snake.split("_")
    sub_words = sub_snake.split("_")

    # Combine words, removing duplicates between parent and child
    # e.g., "CNT Inputs" + "Counter value" shouldn't have duplicate meaning
    combined_words = parent_words + sub_words
    combined_words = _remove_duplicate_words(combined_words)

    # First attempt: full names
    result = "_".join(combined_words)
    if len(result) <= max_length:
        return result

    # Second attempt: abbreviate common words
    abbreviated = _abbreviate_words(combined_words)
    abbreviated = _remove_duplicate_words(abbreviated)
    result = "_".join(abbreviated)
    if len(result) <= max_length:
        return result

    # Third attempt: keep essential parts
    # Priority: parent prefix (first 2 words) + subindex identifier
    parent_abbrev = _abbreviate_words(parent_words)
    sub_abbrev = _abbreviate_words(sub_words)

    # Keep first 2-3 words of parent, all of subindex
    essential_parent = parent_abbrev[:3]
    combined = essential_parent + sub_abbrev
    combined = _remove_duplicate_words(combined)
    result = "_".join(combined)
    if len(result) <= max_length:
        return result

    # Fourth attempt: keep first 2 parent words + truncate subindex
    essential_parent = parent_abbrev[:2]
    combined = essential_parent + sub_abbrev
    combined = _remove_duplicate_words(combined)
    result = "_".join(combined)
    if len(result) <= max_length:
        return result

    # Final fallback: truncate to max_length preserving word boundaries
    result = "_".join(combined)
    if len(result) > max_length:
        # Truncate at word boundary
        truncated = result[:max_length]
        last_underscore = truncated.rfind("_")
        if last_underscore > max_length // 2:
            truncated = truncated[:last_underscore]
        result = truncated

    return result
