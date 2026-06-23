"""Utility functions for catio_terminals."""

import re

# Common words that can be abbreviated when truncating names
_ABBREVIATIONS = {
    "activate": "act",
    "assign": "asn",
    "average": "avg",
    "backup": "bak",
    "calibration": "cal",
    "channel": "ch",
    "coldjunction": "cj",
    "compact": "cpt",
    "compensation": "comp",
    "checksum": "csum",
    "counter": "cnt",
    "current": "cur",
    "default": "def",
    "detection": "det",
    "device": "dev",
    "diagnosis": "diag",
    "differentiator": "diff",
    "disable": "dis",
    "delay": "dly",
    "dynamic": "dyn",
    "enable": "en",
    "feedback": "fb",
    "frequency": "freq",
    "function": "fn",
    "functions": "fns",
    "hardware": "hw",
    "identity": "id",
    "impulse": "imp",
    "input": "in",
    "inhibit": "inh",
    "inhibited": "inh",
    "length": "len",
    "limit": "lim",
    "map": "m",
    "maximum": "max",
    "minimum": "min",
    "modular": "mod",
    "number": "num",
    "offset": "off",
    "output": "out",
    "parameter": "par",
    "parameters": "pars",
    "presentation": "pres",
    "product": "prod",
    "reload": "rld",
    "resistance": "res",
    "revision": "rev",
    "restore": "rst",
    "samples": "smpl",
    "serial": "ser",
    "settings": "set",
    "subindex": "si",
    "standard": "std",
    "status": "sts",
    "software": "sw",
    "switch": "sw",
    "synchron": "sync",
    "threshold": "thr",
    "treshold": "thr",  # Handle typo in Beckhoff XML
    "trigger": "trig",
    "value": "val",
    "vendor": "vnd",
    "version": "ver",
}

# Matches the trailing "_idx<hex>" suffix appended to CoE attribute names
# so the parent CoE index survives any further shortening pass.
_IDX_SUFFIX_RE = re.compile(r"_idx[0-9a-f]+$")


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


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Args:
        name: snake_case string

    Returns:
        PascalCase version of the name

    Examples:
        >>> snake_to_pascal("ai_inputs_channel")
        'AiInputsChannel'
        >>> snake_to_pascal("status_word")
        'StatusWord'
        >>> snake_to_pascal("channel_{channel}_value")
        'Channel{channel}Value'
        >>> snake_to_pascal("simple")
        'Simple'
    """
    # Split on underscores, capitalize each word, join
    words = name.split("_")
    return "".join(word.capitalize() for word in words if word)


def make_fastcs_name(name: str, max_length: int = 40, suffix: str = "") -> str:
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

    def final_result():
        if suffix == "":
            return result
        else:
            return f"{result}_{suffix}"

    max_length = max_length - len(suffix) - 1 if suffix else max_length

    result = to_snake_case(name)
    if len(result) <= max_length:
        return final_result()

    # Apply abbreviations
    words = result.split("_")
    abbreviated = _abbreviate_words(words)
    abbreviated = _remove_duplicate_words(abbreviated)
    result = "_".join(abbreviated)
    if len(result) <= max_length:
        return final_result()

    # Final fallback: truncate at word boundary
    if len(result) > max_length:
        truncated = result[:max_length]
        last_underscore = truncated.rfind("_")
        if last_underscore > max_length // 2:
            truncated = truncated[:last_underscore]
        result = truncated

    return final_result()


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
    parent_index: int, subindex_name: str, max_length: int = 40
) -> str:
    """Create unique fastcs_name for subindex including parent context.

    Combines parent CoE object index with subindex name to create a unique
    identifier. If the combined name exceeds max_length, applies abbreviations
    and truncation strategies while preserving readability.

    Args:
        parent_index: Parent CoE object index (e.g., 0x8000, 0x1018)
        subindex_name: SubIndex name
        max_length: Maximum allowed length (default 40)

    Returns:
        Unique snake_case name under max_length characters with hex index suffix

    Examples:
        >>> make_subindex_fastcs_name(0x8000, "SubIndex 001")
        'subindex_001_idx8000'
        >>> make_subindex_fastcs_name(0x8001, "Counter value")
        'counter_value_idx8001'
        >>> make_subindex_fastcs_name(0x1018, "Vendor ID")
        'vendor_id_idx1018'
        >>> len(make_subindex_fastcs_name(0x8010, "Very Long SubIndex Name Here")) <= 40
        True
        >>> make_subindex_fastcs_name(0x8020, "Minimum fast cycle time")
        'minimum_fast_cycle_time_idx8020'
    """

    def final_result():
        return f"{result}_{hex_index}"

    # Convert both names to snake_case first
    hex_index = f"idx{hex(parent_index).lstrip('0x')}"
    max_length = max_length - len(hex_index) - 1  # for underscore

    sub_snake = to_snake_case(subindex_name)

    # Split into words
    sub_words = sub_snake.split("_")

    # Combine words, removing duplicates between parent and child
    # e.g., "CNT Inputs" + "Counter value" shouldn't have duplicate meaning
    combined_words = _remove_duplicate_words(sub_words)

    # First attempt: full names
    result = "_".join(combined_words)
    if len(result) <= max_length:
        return final_result()

    # Second attempt: abbreviate common words
    abbreviated = _abbreviate_words(combined_words)
    result = "_".join(abbreviated)
    if len(result) <= max_length:
        return final_result()

    # Final fallback: truncate to max_length preserving word boundaries
    result = "_".join(abbreviated)
    if len(result) > max_length:
        # Truncate at word boundary
        truncated = result[:max_length]
        last_underscore = truncated.rfind("_")
        if last_underscore > max_length // 2:
            truncated = truncated[:last_underscore]
        result = truncated

    return final_result()


def shorten_fastcs_name(snake_name: str, max_length: int) -> str:
    """Shorten an already snake_case fastcs_name to fit a length budget.

    Preserves any trailing ``_idx<hex>`` suffix so CoE attribute names keep
    their parent-index disambiguator after abbreviation/truncation. Returns
    the input unchanged when it already fits.

    Args:
        snake_name: A snake_case attribute name, optionally ending in
            ``_idx<hex>``.
        max_length: Maximum allowed length of the result.

    Returns:
        A snake_case name no longer than ``max_length`` characters.

    Examples:
        >>> shorten_fastcs_name("user_calibration_offset_idx8030", 23)
        'user_cal_off_idx8030'
        >>> shorten_fastcs_name("disable_wire_break_detection_idx8000", 26)
        'dis_wire_break_det_idx8000'
        >>> shorten_fastcs_name("enable_filter_idx8000", 30)
        'enable_filter_idx8000'
    """
    if len(snake_name) <= max_length:
        return snake_name

    match = _IDX_SUFFIX_RE.search(snake_name)
    if match:
        suffix = match.group(0)  # includes leading underscore
        body = snake_name[: match.start()]
    else:
        suffix = ""
        body = snake_name

    body_max = max_length - len(suffix)
    if body_max < 1:
        return snake_name[:max_length]

    if len(body) <= body_max:
        return body + suffix

    words = body.split("_")
    abbreviated = _abbreviate_words(words)
    abbreviated = _remove_duplicate_words(abbreviated)
    body = "_".join(abbreviated)
    if len(body) <= body_max:
        return body + suffix

    truncated = body[:body_max]
    last_underscore = truncated.rfind("_")
    if last_underscore > body_max // 2:
        truncated = truncated[:last_underscore]
    return truncated + suffix
