"""XML parsing utilities for Beckhoff terminal files.

This module provides a facade for terminal XML parsing functionality,
re-exporting from specialized submodules:

- xml_constants: Regex patterns, type mappings, utility functions
- xml_catalog: Terminal catalog parsing (parse_terminal_catalog)
- xml_pdo: PDO (Process Data Object) parsing
- xml_pdo_groups: AlternativeSmMapping parsing for dynamic PDO configurations
- xml_coe: CoE (CANopen over EtherCAT) object parsing
"""

import logging

from lxml import etree

from catio_terminals.models import CompositeType, Identity, SymbolNode, TerminalType
from catio_terminals.xml_catalog import (
    extract_group_type,
    extract_terminal_id_from_device,
    parse_terminal_catalog,
)
from catio_terminals.xml_coe import parse_coe_objects
from catio_terminals.xml_constants import (
    ADS_TYPE_MAP,
    ARRAY_ELEMENT_PATTERN,
    CHANNEL_KEYWORD_PATTERN,
    CHANNEL_NUMBER_PATTERN,
    TERMINAL_ID_PATTERN,
    URL_CATEGORY_MAP,
    generate_terminal_url,
    get_ads_type,
    parse_hex_value,
)
from catio_terminals.xml_pdo import (
    consolidate_array_entries,
    create_symbol_nodes,
    extract_channel_pattern,
    process_pdo_entries,
)
from catio_terminals.xml_pdo_groups import (
    assign_symbols_to_groups,
    parse_pdo_groups,
)

logger = logging.getLogger(__name__)

# Re-export public API for backward compatibility
__all__ = [
    # Constants
    "ADS_TYPE_MAP",
    "ARRAY_ELEMENT_PATTERN",
    "CHANNEL_KEYWORD_PATTERN",
    "CHANNEL_NUMBER_PATTERN",
    "TERMINAL_ID_PATTERN",
    "URL_CATEGORY_MAP",
    # Utility functions
    "parse_hex_value",
    "get_ads_type",
    "generate_terminal_url",
    # Catalog functions
    "extract_terminal_id_from_device",
    "extract_group_type",
    "parse_terminal_catalog",
    # PDO group functions
    "parse_pdo_groups",
    "assign_symbols_to_groups",
    # Main parsing functions
    "parse_terminal_details",
    "create_default_terminal",
]


def parse_terminal_details(
    xml_content: str,
    terminal_id: str,
    group_type: str | None = None,
) -> tuple[TerminalType, dict[str, CompositeType]] | None:
    """Parse terminal XML to create detailed TerminalType.

    Args:
        xml_content: XML content string
        terminal_id: Terminal ID to find
        group_type: Optional group type

    Returns:
        Tuple of (TerminalType, composite_types dict) or None if parsing fails
    """
    try:
        if isinstance(xml_content, str):
            root = etree.fromstring(xml_content.encode("utf-8"))
        else:
            root = etree.fromstring(xml_content)

        # Find matching device
        device = None
        for dev in root.findall(".//Device"):
            type_elem = dev.find("Type")
            if type_elem is not None and type_elem.text == terminal_id:
                device = dev
                break

        if device is None:
            logger.warning(f"Device {terminal_id} not found in XML")
            return None

        type_elem = device.find("Type")
        if type_elem is None:
            return None

        # Extract identity
        product_code_str = type_elem.get("ProductCode") or "0"
        revision_str = type_elem.get("RevisionNo") or "0"
        product_code = parse_hex_value(product_code_str)
        revision = parse_hex_value(revision_str)

        vendor_elem = root.find(".//Vendor/Id")
        vendor_id = 2  # Beckhoff default
        if vendor_elem is not None and vendor_elem.text:
            vendor_id = int(vendor_elem.text)

        identity = Identity(
            vendor_id=vendor_id,
            product_code=product_code,
            revision_number=revision,
        )

        # Extract description
        description = f"Terminal {terminal_id}"
        for name_elem in device.findall("Name"):
            if name_elem.get("LcId") == "1033" and name_elem.text:
                desc_text = name_elem.text.strip()
                if desc_text.startswith(terminal_id):
                    desc_text = desc_text[len(terminal_id) :].strip()
                    # Remove leading pipe separator if present
                    if desc_text.startswith("|"):
                        desc_text = desc_text[1:].strip()
                description = desc_text if desc_text else name_elem.text
                break
            elif name_elem.text:
                description = name_elem.text

        # Process PDOs
        tx_channels, tx_dups, tx_bits, tx_bf_map, tx_pdo_map = process_pdo_entries(
            device, "TxPdo"
        )
        rx_channels, rx_dups, rx_bits, rx_bf_map, rx_pdo_map = process_pdo_entries(
            device, "RxPdo"
        )

        # Merge channel groups
        for key, group_info in rx_channels.items():
            if key in tx_channels:
                tx_channels[key]["channels"].extend(group_info["channels"])
                # Keep max size
                if group_info["size"] > tx_channels[key]["size"]:
                    tx_channels[key]["size"] = group_info["size"]
                    tx_channels[key]["ads_type"] = group_info["ads_type"]
                    tx_channels[key]["data_type"] = group_info["data_type"]
            else:
                tx_channels[key] = group_info

        # Merge duplicate trackers (now dicts with 'count' and 'tooltip')
        for key, info in rx_dups.items():
            if key in tx_dups:
                tx_dups[key]["count"] += info["count"]
                # Keep existing tooltip if present, otherwise use rx tooltip
                if not tx_dups[key].get("tooltip"):
                    tx_dups[key]["tooltip"] = info.get("tooltip")
            else:
                tx_dups[key] = info

        # Merge bit field trackers
        for key, info in rx_bits.items():
            if key not in tx_bits:
                tx_bits[key] = info
            else:
                # Merge symbols list
                tx_bits[key]["symbols"].extend(info["symbols"])

        # Merge channel bit field maps (keep the one with more bits)
        for pattern, bf_key in rx_bf_map.items():
            if pattern not in tx_bf_map or len(bf_key) > len(tx_bf_map[pattern]):
                tx_bf_map[pattern] = bf_key

        # Merge symbol PDO maps
        merged_pdo_map = {**tx_pdo_map, **rx_pdo_map}

        symbol_nodes, composite_types, symbol_index_to_pdo = create_symbol_nodes(
            tx_channels, tx_dups, tx_bits, tx_bf_map, merged_pdo_map
        )
        coe_objects = parse_coe_objects(device)

        # Parse PDO groups (AlternativeSmMapping)
        pdo_groups = parse_pdo_groups(device)

        # Assign symbols to their respective PDO groups
        if pdo_groups:
            assign_symbols_to_groups(pdo_groups, symbol_index_to_pdo)

        # Set default selected group based on is_default flag
        default_group = None
        for group in pdo_groups:
            if group.is_default:
                default_group = group.name
                break
        if not default_group and pdo_groups:
            default_group = pdo_groups[0].name

        terminal_type = TerminalType(
            description=description,
            identity=identity,
            symbol_nodes=symbol_nodes,
            coe_objects=coe_objects,
            group_type=group_type,
            pdo_groups=pdo_groups,
            selected_pdo_group=default_group,
        )

        return terminal_type, composite_types

    except etree.ParseError as e:
        logger.error(f"Failed to parse XML: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing terminal XML: {e}", exc_info=True)
        return None


def create_default_terminal(
    terminal_id: str,
    description: str,
    group_type: str | None = None,
) -> TerminalType:
    """Create a default terminal type with placeholder values.

    Args:
        terminal_id: Terminal ID (e.g., "EL3104")
        description: Terminal description
        group_type: Optional group type

    Returns:
        TerminalType with default/placeholder values
    """
    try:
        channel_count = int(terminal_id[-1])
    except (ValueError, IndexError):
        channel_count = 1

    if terminal_id.startswith("EL1"):
        symbol_name = "DI Input Channel {channel}"
        type_name = "DI Input Channel 1_TYPE"
    elif terminal_id.startswith("EL2"):
        symbol_name = "DO Output Channel {channel}"
        type_name = "DO Output Channel 1_TYPE"
    elif terminal_id.startswith("EL3"):
        symbol_name = "AI Input Channel {channel}"
        type_name = "AI Input Channel 1_TYPE"
    elif terminal_id.startswith("EL4"):
        symbol_name = "AO Output Channel {channel}"
        type_name = "AO Output Channel 1_TYPE"
    else:
        symbol_name = "Channel {channel}"
        type_name = "Channel 1_TYPE"

    return TerminalType(
        description=description,
        identity=Identity(
            vendor_id=2,
            product_code=0x0,
            revision_number=0x00100000,
        ),
        symbol_nodes=[
            SymbolNode(
                name_template=symbol_name,
                index_group=0xF030,
                type_name=type_name,
                channels=channel_count,
            ),
            SymbolNode(
                name_template="WcState^WcState",
                index_group=0xF021,
                type_name="BIT",
                channels=1,
            ),
        ],
        group_type=group_type,
    )


# Keep internal function names as aliases for backward compatibility
# These were private but may have been imported directly
_extract_channel_pattern = extract_channel_pattern
_consolidate_array_entries = consolidate_array_entries
_process_pdo_entries = process_pdo_entries
_create_symbol_nodes = create_symbol_nodes
_parse_coe_objects = parse_coe_objects
