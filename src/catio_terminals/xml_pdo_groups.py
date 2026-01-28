"""PDO group parsing for Beckhoff terminal XML files.

Parses AlternativeSmMapping elements from TwinCAT VendorSpecific sections
to identify mutually exclusive PDO configurations.
"""

import logging

from lxml.etree import _Element

from catio_terminals.models import PdoGroup
from catio_terminals.xml_constants import parse_hex_value

logger = logging.getLogger(__name__)


def parse_pdo_groups(device: _Element) -> list[PdoGroup]:
    """Parse AlternativeSmMapping elements to extract PDO groups.

    AlternativeSmMapping elements define mutually exclusive PDO configurations.
    Each group contains a set of PDO indices that can be active together.

    Args:
        device: lxml Device element

    Returns:
        List of PdoGroup instances (empty if no alternative mappings found)
    """
    pdo_groups: list[PdoGroup] = []

    # Find AlternativeSmMapping elements in VendorSpecific/TwinCAT
    vendor_specific = device.find(".//VendorSpecific")
    if vendor_specific is None:
        return pdo_groups

    twincat = vendor_specific.find("TwinCAT")
    if twincat is None:
        return pdo_groups

    for alt_mapping in twincat.findall("AlternativeSmMapping"):
        name = alt_mapping.findtext("Name", "")
        if not name:
            continue

        # Check if this is the default mapping
        is_default = alt_mapping.get("Default") == "1"

        # Collect PDO indices from all Sm elements
        pdo_indices: list[int] = []
        for sm in alt_mapping.findall("Sm"):
            for pdo in sm.findall("Pdo"):
                if pdo.text:
                    pdo_index = parse_hex_value(pdo.text)
                    if pdo_index != 0:
                        pdo_indices.append(pdo_index)

        if pdo_indices:
            pdo_groups.append(
                PdoGroup(
                    name=name,
                    is_default=is_default,
                    pdo_indices=pdo_indices,
                    symbol_indices=[],  # Will be populated after symbol parsing
                )
            )

    return pdo_groups


def build_pdo_to_group_map(pdo_groups: list[PdoGroup]) -> dict[int, str]:
    """Build a mapping from PDO index to group name.

    Args:
        pdo_groups: List of PDO groups

    Returns:
        Dict mapping PDO index to group name
    """
    pdo_to_group: dict[int, str] = {}
    for group in pdo_groups:
        for pdo_index in group.pdo_indices:
            pdo_to_group[pdo_index] = group.name
    return pdo_to_group


def get_pdo_index_from_element(pdo: _Element) -> int:
    """Extract PDO index from a TxPdo or RxPdo element.

    Args:
        pdo: lxml PDO element (TxPdo or RxPdo)

    Returns:
        PDO index as integer
    """
    index_str = pdo.findtext("Index", "0")
    return parse_hex_value(index_str)


def assign_symbols_to_groups(
    pdo_groups: list[PdoGroup],
    symbol_pdo_mapping: dict[int, int],
) -> None:
    """Assign symbol indices to their corresponding PDO groups.

    After symbols are created, this function maps each symbol's source PDO
    index to the appropriate PDO group.

    Args:
        pdo_groups: List of PDO groups to update
        symbol_pdo_mapping: Dict mapping symbol index to source PDO index
    """
    if not pdo_groups:
        return

    # Build reverse mapping: PDO index -> group
    pdo_to_group: dict[int, PdoGroup] = {}
    for group in pdo_groups:
        for pdo_index in group.pdo_indices:
            pdo_to_group[pdo_index] = group

    # Assign symbols to groups
    for symbol_idx, pdo_index in symbol_pdo_mapping.items():
        group = pdo_to_group.get(pdo_index)
        if group:
            group.symbol_indices.append(symbol_idx)

    # Sort symbol indices for consistent output
    for group in pdo_groups:
        group.symbol_indices.sort()
