"""PDO (Process Data Object) parsing for Beckhoff terminal XML files."""

from catio_terminals.models import SymbolNode
from catio_terminals.utils import to_pascal_case
from catio_terminals.xml_constants import (
    ARRAY_ELEMENT_PATTERN,
    CHANNEL_KEYWORD_PATTERN,
    CHANNEL_NUMBER_PATTERN,
    get_ads_type,
    parse_hex_value,
)


def extract_channel_pattern(name: str) -> tuple[str, int] | None:
    """Extract channel pattern and number from a name.

    Args:
        name: Symbol name that may contain channel information

    Returns:
        Tuple of (pattern_template, channel_number) or None if no pattern found
    """
    keyword_match = CHANNEL_KEYWORD_PATTERN.search(name)
    if keyword_match:
        # Groups: (prefix, keyword, channel_num, suffix)
        prefix = keyword_match.group(1).strip()
        keyword = keyword_match.group(2)
        channel_num = int(keyword_match.group(3))
        suffix = keyword_match.group(4).strip()

        # Build pattern: "prefix keyword {channel} suffix"
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(f"{keyword} {{channel}}")
        if suffix:
            parts.append(suffix)
        pattern = " ".join(parts)
        return pattern, channel_num

    # Fall back to simple "name number" pattern
    number_match = CHANNEL_NUMBER_PATTERN.search(name)
    if number_match:
        prefix = number_match.group(1).strip()
        channel_num = int(number_match.group(2))
        return f"{prefix} {{channel}}", channel_num

    return None


def consolidate_array_entries(entries: list[dict]) -> list[dict]:
    """Consolidate array element entries into single array-typed entries.

    Array elements in Beckhoff XML are represented as individual entries like:
        - "Samples__ARRAY [0]" (DINT, 32 bits)
        - "Samples__ARRAY [1]" (DINT, 32 bits)
        - ...
        - "Samples__ARRAY [99]" (DINT, 32 bits)

    This function groups them into a single entry:
        - "Samples" (ARRAY [0..99] OF DINT)

    Args:
        entries: List of entry dictionaries with name, index, bit_len, data_type

    Returns:
        List of consolidated entries (array elements merged, non-arrays unchanged)
    """
    array_groups: dict[str, list[dict]] = {}
    non_array_entries: list[dict] = []

    for entry in entries:
        match = ARRAY_ELEMENT_PATTERN.match(entry["name"])
        if match:
            base_name = match.group(1)
            array_idx = int(match.group(2))
            if base_name not in array_groups:
                array_groups[base_name] = []
            array_groups[base_name].append({**entry, "array_idx": array_idx})
        else:
            non_array_entries.append(entry)

    # Build consolidated entries from array groups
    consolidated = list(non_array_entries)
    for base_name, elements in array_groups.items():
        if not elements:
            continue

        # Sort by array index to get bounds
        elements.sort(key=lambda e: e["array_idx"])
        min_idx = elements[0]["array_idx"]
        max_idx = elements[-1]["array_idx"]

        # Use first element's properties (they should all be the same type)
        first = elements[0]
        element_type = first["data_type"]
        element_bit_len = first["bit_len"]

        # Calculate total size for the array
        total_bit_len = element_bit_len * len(elements)

        # Create array type string
        array_type = f"ARRAY [{min_idx}..{max_idx}] OF {element_type}"

        consolidated.append(
            {
                "name": base_name,
                "index": first["index"],  # Use first element's index
                "bit_len": total_bit_len,
                "data_type": array_type,
            }
        )

    return consolidated


def _add_to_groups(
    channel_groups: dict,
    duplicate_tracker: dict,
    name: str,
    channel_info: tuple[str, int] | None,
    index_group: int,
    size: int,
    ads_type: int,
    data_type: str,
    access: str,
) -> None:
    """Add entry to channel_groups or duplicate_tracker.

    Args:
        channel_groups: Dict to collect channel patterns
        duplicate_tracker: Dict to track non-channel duplicates
        name: Symbol name
        channel_info: Tuple of (pattern, channel_num) or None
        index_group: ADS index group
        size: Size in bytes
        ads_type: ADS type code
        data_type: Data type name
        access: Access string (Read-only, Read/Write)
    """
    if channel_info:
        pattern, channel_num = channel_info
        group_key = (pattern, index_group, size, ads_type, data_type, access)
        if group_key not in channel_groups:
            channel_groups[group_key] = []
        channel_groups[group_key].append(channel_num)
    else:
        dup_key = (name, index_group, size, ads_type, data_type, access)
        duplicate_tracker[dup_key] = duplicate_tracker.get(dup_key, 0) + 1


def _process_bit_entries(
    bit_entries: list[dict],
    pdo_name: str,
    pdo_type: str,
    default_index_group: int,
    channel_groups: dict,
    duplicate_tracker: dict,
) -> None:
    """Process bit field entries and create composite symbol using PDO name.

    Bit entries are consolidated into a single symbol using the PDO name
    (e.g., "Channel 1" becomes "Channel {channel}"). The composite type
    is determined by the total bit count.

    Args:
        bit_entries: List of BOOL/bit entries to consolidate
        pdo_name: Name of the parent PDO (used as the symbol name)
        pdo_type: "TxPdo" or "RxPdo"
        default_index_group: Default index group if not in entry
        channel_groups: Dict to collect channel patterns
        duplicate_tracker: Dict to track non-channel duplicates
    """
    if not bit_entries:
        return

    is_output = pdo_type == "RxPdo"
    access = "Read/Write" if is_output else "Read-only"

    # Calculate total size of bit group (round up to nearest byte)
    total_bits = sum(e["bit_len"] for e in bit_entries)

    # Determine composite type based on bit count
    if total_bits <= 8:
        composite_type = "USINT"
        composite_size = 1
    elif total_bits <= 16:
        composite_type = "UINT"
        composite_size = 2
    else:
        composite_type = "UDINT"
        composite_size = 4

    first_index = bit_entries[0]["index"]
    index_group = (first_index >> 16) & 0xFFFF
    if index_group == 0:
        index_group = default_index_group

    ads_type = get_ads_type(composite_type)

    # Use PDO name directly as the symbol name
    full_name = pdo_name if pdo_name else "Status" if pdo_type == "TxPdo" else "Control"

    # Check for channel pattern in PDO name
    pdo_channel_info = extract_channel_pattern(pdo_name) if pdo_name else None

    _add_to_groups(
        channel_groups,
        duplicate_tracker,
        full_name,
        pdo_channel_info,
        index_group,
        composite_size,
        ads_type,
        composite_type,
        access,
    )


def _process_value_entry(
    entry_data: dict,
    pdo_name: str,
    pdo_channel_info: tuple[str, int] | None,
    default_index_group: int,
    is_output: bool,
    channel_groups: dict,
    duplicate_tracker: dict,
) -> None:
    """Process a single non-bit value entry.

    Args:
        entry_data: Entry dictionary with name, index, bit_len, data_type
        pdo_name: Name of the parent PDO
        pdo_channel_info: Channel info extracted from PDO name
        default_index_group: Default index group if not in entry
        is_output: True for RxPdo (outputs), False for TxPdo (inputs)
        channel_groups: Dict to collect channel patterns
        duplicate_tracker: Dict to track non-channel duplicates
    """
    entry_name = entry_data["name"]
    index = entry_data["index"]
    bit_len = entry_data["bit_len"]
    data_type = entry_data["data_type"]

    index_group = (index >> 16) & 0xFFFF
    if index_group == 0:
        index_group = default_index_group

    size = (bit_len + 7) // 8
    ads_type = get_ads_type(data_type)
    access = "Read/Write" if is_output else "Read-only"

    # Build symbol name and determine channel info
    if pdo_name and entry_name and pdo_name != entry_name:
        if pdo_channel_info:
            pdo_pattern, channel_num = pdo_channel_info
            pattern = f"{pdo_pattern}.{entry_name}"
            channel_info: tuple[str, int] | None = (pattern, channel_num)
            name = f"{pdo_name}.{entry_name}"
        else:
            name = f"{pdo_name}.{entry_name}"
            channel_info = extract_channel_pattern(name)
    elif pdo_name:
        name = pdo_name
        channel_info = pdo_channel_info
    else:
        name = entry_name
        channel_info = extract_channel_pattern(entry_name)

    _add_to_groups(
        channel_groups,
        duplicate_tracker,
        name,
        channel_info,
        index_group,
        size,
        ads_type,
        data_type,
        access,
    )


def process_pdo_entries(device, pdo_type: str) -> tuple[dict, dict]:
    """Process PDO entries and group by channel pattern.

    Uses PDO name (not Entry name) to determine channel patterns, matching
    how TwinCAT generates symbol names at runtime.

    When a PDO contains a group of bit fields followed by a value entry,
    the bit fields are collapsed into a single "Status" or "Control" composite
    symbol (matching TwinCAT's grouping behavior).

    Args:
        device: lxml Device element
        pdo_type: "TxPdo" or "RxPdo"

    Returns:
        Tuple of (channel_groups dict, duplicate_tracker dict)
    """
    channel_groups: dict = {}
    duplicate_tracker: dict = {}

    default_index_group = 0xF020 if pdo_type == "TxPdo" else 0xF030
    is_output = pdo_type == "RxPdo"

    for pdo in device.findall(f".//{pdo_type}"):
        pdo_name = pdo.findtext("Name", "")

        # Collect all entries for this PDO to analyze grouping
        entries = []
        for entry in pdo.findall("Entry"):
            entry_name = entry.findtext("Name", "")
            index_str = entry.findtext("Index", "0")
            index = parse_hex_value(index_str)

            # Skip padding/reserved entries (Index=#x0 indicates filler bits)
            if index == 0:
                continue

            if not entry_name:
                continue

            bit_len = int(entry.findtext("BitLen", "0"))
            data_type = entry.findtext("DataType", "UNKNOWN")

            entries.append(
                {
                    "name": entry_name,
                    "index": index,
                    "bit_len": bit_len,
                    "data_type": data_type,
                }
            )

        if not entries:
            continue

        # Consolidate array element entries into single array-typed entries
        entries = consolidate_array_entries(entries)

        # Analyze entries: separate bit fields from value entries
        # Bit fields are BOOL entries or entries with BitLen=1
        bit_entries = []
        value_entries = []
        for e in entries:
            is_bit = e["data_type"] == "BOOL" or e["bit_len"] == 1
            if is_bit:
                bit_entries.append(e)
            else:
                value_entries.append(e)

        # Process bit entries as composite symbol
        _process_bit_entries(
            bit_entries,
            pdo_name,
            pdo_type,
            default_index_group,
            channel_groups,
            duplicate_tracker,
        )

        # Process non-bit (value) entries normally
        pdo_channel_info = extract_channel_pattern(pdo_name) if pdo_name else None
        for entry_data in value_entries:
            _process_value_entry(
                entry_data,
                pdo_name,
                pdo_channel_info,
                default_index_group,
                is_output,
                channel_groups,
                duplicate_tracker,
            )

    return channel_groups, duplicate_tracker


def create_symbol_nodes(
    channel_groups: dict, duplicate_tracker: dict
) -> list[SymbolNode]:
    """Create SymbolNode list from grouped PDO data.

    Args:
        channel_groups: Dict mapping group keys to channel numbers
        duplicate_tracker: Dict mapping duplicate keys to counts

    Returns:
        List of SymbolNode instances
    """
    symbol_nodes = []

    for group_key, channel_nums in channel_groups.items():
        name_pattern, index_group, _size, _ads_type, data_type, access = group_key
        symbol_nodes.append(
            SymbolNode(
                name_template=name_pattern,
                index_group=index_group,
                type_name=data_type,
                channels=len(channel_nums),
                access=access,
                fastcs_name=to_pascal_case(name_pattern),
            )
        )

    for dup_key, count in duplicate_tracker.items():
        name, index_group, _size, _ads_type, data_type, access = dup_key
        if count > 1:
            name_pattern = f"{name} {{channel}}"
            symbol_nodes.append(
                SymbolNode(
                    name_template=name_pattern,
                    index_group=index_group,
                    type_name=data_type,
                    channels=count,
                    access=access,
                    fastcs_name=to_pascal_case(name_pattern),
                )
            )
        else:
            symbol_nodes.append(
                SymbolNode(
                    name_template=name,
                    index_group=index_group,
                    type_name=data_type,
                    channels=1,
                    access=access,
                    fastcs_name=to_pascal_case(name),
                )
            )

    return symbol_nodes
