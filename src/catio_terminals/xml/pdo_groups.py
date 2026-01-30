"""PDO group parsing for Beckhoff terminal XML files.

Parses AlternativeSmMapping elements from TwinCAT VendorSpecific sections
to identify mutually exclusive PDO configurations.

Also handles PDO Exclude elements as an alternative way to define
mutually exclusive PDO configurations (used by terminals like EL1502).
"""

import logging
from collections import defaultdict

from lxml.etree import _Element

from catio_terminals.models import PdoGroup
from catio_terminals.xml.constants import parse_hex_value

logger = logging.getLogger(__name__)


def parse_pdo_groups(device: _Element) -> list[PdoGroup]:
    """Parse PDO groups from device XML.

    Tries two methods:
    1. AlternativeSmMapping elements (TwinCAT VendorSpecific) - preferred
    2. PDO Exclude elements - fallback for terminals like EL1502

    Args:
        device: lxml Device element

    Returns:
        List of PdoGroup instances (empty if no alternative mappings found)
    """
    # Try AlternativeSmMapping first (more explicit)
    pdo_groups = _parse_alternative_sm_mapping(device)
    if pdo_groups:
        return pdo_groups

    # Fallback: Try to infer groups from PDO Exclude elements
    return _parse_pdo_excludes(device)


def _parse_alternative_sm_mapping(device: _Element) -> list[PdoGroup]:
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


def _parse_pdo_excludes(device: _Element) -> list[PdoGroup]:
    """Parse PDO Exclude elements to infer mutually exclusive groups.

    Some terminals (like EL1502) use <Exclude> elements inside TxPdo/RxPdo
    to declare which PDOs are mutually exclusive. This function analyzes
    the exclusion graph to identify per-channel vs combined modes.

    The default group is determined by which PDOs have an explicit Sm attribute
    (Sync Manager assignment), as these are the PDOs active by default.

    Args:
        device: lxml Device element

    Returns:
        List of PdoGroup instances inferred from exclusions
    """
    # Build exclusion graph and collect PDO info
    excludes: dict[int, set[int]] = defaultdict(set)
    pdo_names: dict[int, str] = {}
    pdo_has_sm: dict[int, bool] = {}  # Track which PDOs have Sm attribute
    all_pdos: set[int] = set()

    for pdo_type in ["TxPdo", "RxPdo"]:
        for pdo in device.findall(pdo_type):
            idx_str = pdo.findtext("Index", "")
            if not idx_str:
                continue
            idx = parse_hex_value(idx_str)
            if idx == 0:
                continue

            all_pdos.add(idx)
            pdo_names[idx] = pdo.findtext("Name", f"PDO 0x{idx:04X}")
            # PDOs with Sm attribute are assigned to a Sync Manager by default
            pdo_has_sm[idx] = pdo.get("Sm") is not None

            for excl in pdo.findall("Exclude"):
                if excl.text:
                    excl_idx = parse_hex_value(excl.text)
                    if excl_idx != 0:
                        excludes[idx].add(excl_idx)

    # No exclusions found - no dynamic PDO groups
    if not excludes:
        return []

    # Identify groups from exclusion pattern
    # Pattern: "Combined" PDOs exclude multiple "Channel" PDOs
    # Find PDOs that exclude multiple others (likely "Combined" mode)
    combined_pdos: set[int] = set()
    channel_pdos: set[int] = set()

    for pdo_idx, excluded in excludes.items():
        # If this PDO excludes 2+ others, it's likely a "Combined" PDO
        if len(excluded) >= 2:
            combined_pdos.add(pdo_idx)
            channel_pdos.update(excluded)
        # If excluded by a combined PDO, it's a channel PDO
        for other_idx, other_excluded in excludes.items():
            if pdo_idx in other_excluded and len(other_excluded) >= 2:
                channel_pdos.add(pdo_idx)
                combined_pdos.add(other_idx)

    # If we couldn't identify combined vs channel, try simpler heuristic
    if not combined_pdos and excludes:
        # Just check for symmetric exclusions (A excludes B, B excludes A)
        # Group by what they exclude
        logger.debug(f"Using symmetric exclusion heuristic for {len(excludes)} PDOs")
        return []  # Can't determine groups from simple exclusions

    # Determine which group is default based on Sm attribute
    # PDOs with Sm attribute are the default active PDOs
    combined_has_sm = any(pdo_has_sm.get(idx, False) for idx in combined_pdos)
    channel_has_sm = any(pdo_has_sm.get(idx, False) for idx in channel_pdos)

    # Default to the group whose PDOs have Sm attribute
    # If both or neither have Sm, default to Combined (as TwinCAT typically does)
    combined_is_default = combined_has_sm or not channel_has_sm

    # Build the two groups
    pdo_groups: list[PdoGroup] = []

    # Channel PDOs that aren't also combined
    pure_channel_pdos = channel_pdos - combined_pdos
    # PDOs with no exclusions go in both groups (always active)
    neutral_pdos = all_pdos - channel_pdos - combined_pdos

    if pure_channel_pdos:
        # Per-channel mode: channel PDOs + neutral PDOs
        pdo_groups.append(
            PdoGroup(
                name="Per-Channel",
                is_default=not combined_is_default,
                pdo_indices=sorted(pure_channel_pdos | neutral_pdos),
                symbol_indices=[],
            )
        )

    if combined_pdos:
        # Combined mode: combined PDOs + neutral PDOs
        pdo_groups.append(
            PdoGroup(
                name="Combined",
                is_default=combined_is_default,
                pdo_indices=sorted(combined_pdos | neutral_pdos),
                symbol_indices=[],
            )
        )

    if pdo_groups:
        default_name = next((g.name for g in pdo_groups if g.is_default), "unknown")
        logger.info(
            f"Inferred {len(pdo_groups)} PDO groups from Exclude elements: "
            f"{[g.name for g in pdo_groups]} (default: {default_name})"
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
