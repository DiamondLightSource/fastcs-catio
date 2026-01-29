"""Terminal catalog parsing for Beckhoff XML files."""

import logging
from pathlib import Path

from lxml import etree

from catio_terminals.xml_cache import BeckhoffTerminalInfo
from catio_terminals.xml_constants import (
    TERMINAL_ID_PATTERN,
    generate_terminal_url,
    parse_hex_value,
)

logger = logging.getLogger(__name__)


def extract_terminal_id_from_device(device, xml_file: Path) -> str | None:
    """Extract terminal ID from a Device element.

    Args:
        device: lxml Device element
        xml_file: Path to XML file (for fallback extraction from filename)

    Returns:
        Terminal ID string or None if not found
    """
    # Look for Type element with terminal-like text
    type_children = device.xpath(".//*[contains(local-name(), 'Type')]")
    for child in type_children:
        if child.text:
            text = child.text.strip()
            # Match any alphanumeric terminal ID pattern
            match = TERMINAL_ID_PATTERN.match(text)
            if match:
                return text

    # Fallback: extract from filename
    match = TERMINAL_ID_PATTERN.search(xml_file.stem)
    if match:
        return match.group(1).upper()

    return None


def extract_group_type(root) -> str:
    """Extract GroupType from XML root element.

    Args:
        root: lxml root element

    Returns:
        Group type string (e.g., "AnaIn", "DigOut") or "Other"
    """
    group_elements = root.xpath("//*[local-name()='GroupType']")
    if group_elements and isinstance(group_elements, list):
        group_elem = group_elements[0]
        if hasattr(group_elem, "text") and group_elem.text:
            return str(group_elem.text).strip()
    return "Other"


def _extract_terminal_name_and_description(device, terminal_id: str) -> tuple[str, str]:
    """Extract name and description from device element.

    Args:
        device: lxml Device element
        terminal_id: Terminal ID for fallback

    Returns:
        Tuple of (name, description)
    """
    name = terminal_id
    description = f"Terminal {terminal_id}"

    # Prefer English LcId=1033
    name_elems = device.xpath(".//Name[@LcId='1033']")
    first_name_elem = (
        name_elems[0] if isinstance(name_elems, list) and name_elems else None
    )
    if etree.iselement(first_name_elem) and first_name_elem.text is not None:
        name = first_name_elem.text.strip()
        desc_text = name
        if desc_text.startswith(terminal_id):
            desc_text = desc_text[len(terminal_id) :].strip()
            # Remove leading pipe separator if present
            if desc_text.startswith("|"):
                desc_text = desc_text[1:].strip()
        description = desc_text if desc_text else name
    else:
        name_elems = device.xpath(".//Name")
        first_name_elem = (
            name_elems[0] if isinstance(name_elems, list) and name_elems else None
        )
        if etree.iselement(first_name_elem) and first_name_elem.text is not None:
            name = first_name_elem.text.strip()

    return name, description


def parse_terminal_catalog(
    xml_files: list[Path],
    max_terminals: int = 0,
    progress_callback=None,
) -> list[BeckhoffTerminalInfo]:
    """Parse XML files to build terminal catalog.

    Args:
        xml_files: List of XML file paths to parse
        max_terminals: Maximum terminals to return (0 = unlimited)
        progress_callback: Optional callback(message, progress) where
            progress is 0.0-1.0

    Returns:
        List of BeckhoffTerminalInfo objects
    """
    terminals = []
    seen_ids: set[str] = set()
    total_files = len(xml_files)

    for idx, xml_file in enumerate(xml_files):
        if progress_callback and idx % 5 == 0:
            progress = idx / total_files
            progress_callback(f"Parsing file {idx + 1}/{total_files}...", progress)

        try:
            tree = etree.parse(str(xml_file))
            root = tree.getroot()
            group_type = extract_group_type(root)

            devices = root.xpath("//*[local-name()='Device']")
            if not isinstance(devices, list):
                continue

            for device in devices:
                # Ensure device is an Element (xpath can return strings/bytes)
                if not etree.iselement(device):
                    continue

                # Must have Type element with ProductCode
                type_elem = device.find("Type")
                if type_elem is None:
                    continue

                terminal_id = extract_terminal_id_from_device(device, xml_file)
                if not terminal_id:
                    continue

                # Check if PDOs use Ref attribute (no inline entries)
                # Skip these devices - prefer files with actual PDO entries
                has_pdo_refs = False
                for pdo in device.findall(".//TxPdo") + device.findall(".//RxPdo"):
                    if pdo.get("Ref") is not None:
                        has_pdo_refs = True
                        break

                if has_pdo_refs:
                    # Skip this device if we haven't seen a better version yet
                    # If we have, we already have the better version
                    continue

                if terminal_id in seen_ids:
                    continue

                seen_ids.add(terminal_id)

                # Extract product code and revision
                product_code = 0
                revision_number = 0
                product_code_str = type_elem.get("ProductCode")
                revision_str = type_elem.get("RevisionNo")
                if product_code_str:
                    product_code = parse_hex_value(product_code_str)
                if revision_str:
                    revision_number = parse_hex_value(revision_str)

                # Check if terminal has CoE objects
                has_coe = False
                objects_section = device.find(".//Profile/Dictionary/Objects")
                if objects_section is not None:
                    objects = objects_section.findall("Object")
                    has_coe = len(objects) > 0

                name, description = _extract_terminal_name_and_description(
                    device, terminal_id
                )

                terminals.append(
                    BeckhoffTerminalInfo(
                        terminal_id=terminal_id,
                        name=name,
                        description=description,
                        url=generate_terminal_url(terminal_id, group_type),
                        xml_file=str(xml_file),
                        product_code=product_code,
                        revision_number=revision_number,
                        group_type=group_type,
                        has_coe=has_coe,
                    )
                )

                if max_terminals > 0 and len(terminals) >= max_terminals:
                    logger.info(f"Reached max_terminals limit of {max_terminals}")
                    return terminals

        except Exception as e:
            logger.debug(f"Failed to parse {xml_file.name}: {e}")
            continue

    return terminals
