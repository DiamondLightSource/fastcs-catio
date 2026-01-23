"""XML parsing utilities for Beckhoff terminal files."""

import logging
import re
from pathlib import Path

from lxml import etree

from catio_terminals.models import (
    CoEObject,
    CoESubIndex,
    Identity,
    SymbolNode,
    TerminalType,
)
from catio_terminals.utils import to_pascal_case
from catio_terminals.xml_cache import BeckhoffTerminalInfo

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns
TERMINAL_ID_PATTERN = re.compile(r"([A-Z]{2,3}\d{4})", re.IGNORECASE)
CHANNEL_KEYWORD_PATTERN = re.compile(
    r"(.*?)\s*(?:Channel|Ch\.?|Input|Output|AI|AO|DI|DO)\s+(\d+)(.*)",
    re.IGNORECASE,
)
CHANNEL_NUMBER_PATTERN = re.compile(r"(.+?)\s+(\d+)$")
KEYWORD_EXTRACT_PATTERN = re.compile(
    r"(Channel|Ch\.?|Input|Output|AI|AO|DI|DO)", re.IGNORECASE
)

# ADS type mapping
ADS_TYPE_MAP = {
    "BOOL": 33,
    "BYTE": 16,
    "USINT": 16,
    "SINT": 17,
    "WORD": 18,
    "UINT": 18,
    "INT": 2,
    "DWORD": 19,
    "UDINT": 19,
    "DINT": 3,
    "REAL": 4,
    "LREAL": 5,
}

# URL category mapping
URL_CATEGORY_MAP = {
    "DigIn": "el-ed1xxx-digital-input",
    "DigOut": "el-ed2xxx-digital-output",
    "AnaIn": "el-ed3xxx-analog-input",
    "AnaOut": "el-ed4xxx-analog-output",
    "Measuring": "el5xxx-position-measurement",
    "Communication": "el6xxx-communication",
    "Motor": "el7xxx-servo-drive",
    "PowerSupply": "el9xxx-power-supply",
}


def parse_hex_value(value: str) -> int:
    """Parse Beckhoff hex string (#x prefix) or standard hex to integer."""
    if value.startswith("#x"):
        return int(value[2:], 16)
    return int(value, 0)


def get_ads_type(data_type: str) -> int:
    """Map EtherCAT data type to ADS type code."""
    return ADS_TYPE_MAP.get(data_type.upper(), 65)  # 65 = generic structure


def generate_terminal_url(terminal_id: str, group_type: str) -> str:
    """Generate Beckhoff website URL for a terminal."""
    category = URL_CATEGORY_MAP.get(group_type, "ethercat-terminals")
    base = "https://www.beckhoff.com/en-gb/products/i-o/ethercat-terminals"
    return f"{base}/{category}/{terminal_id.lower()}.html"


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
    """Extract GroupType from XML root element."""
    group_elements = root.xpath("//*[local-name()='GroupType']")
    if group_elements and isinstance(group_elements, list):
        group_elem = group_elements[0]
        if hasattr(group_elem, "text") and group_elem.text:
            return str(group_elem.text).strip()
    return "Other"


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
                # Must have Type element with ProductCode
                type_elem = device.find("Type")
                if type_elem is None:
                    continue

                terminal_id = extract_terminal_id_from_device(device, xml_file)
                if not terminal_id or terminal_id in seen_ids:
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

                # Extract name (prefer English LcId=1033)
                name = terminal_id
                description = f"Terminal {terminal_id}"

                name_elems = device.xpath(".//Name[@LcId='1033']")
                if name_elems and name_elems[0].text:
                    name = name_elems[0].text.strip()
                    desc_text = name
                    if desc_text.startswith(terminal_id):
                        desc_text = desc_text[len(terminal_id) :].strip()
                    description = desc_text if desc_text else name
                else:
                    name_elems = device.xpath(".//Name")
                    if name_elems and name_elems[0].text:
                        name = name_elems[0].text.strip()

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
                    )
                )

                if max_terminals > 0 and len(terminals) >= max_terminals:
                    logger.info(f"Reached max_terminals limit of {max_terminals}")
                    return terminals

        except Exception as e:
            logger.debug(f"Failed to parse {xml_file.name}: {e}")
            continue

    return terminals


def _extract_channel_pattern(name: str) -> tuple[str, int] | None:
    """Extract channel pattern and number from a name.

    Returns:
        Tuple of (pattern_template, channel_number) or None if no pattern found
    """
    channel_match = CHANNEL_KEYWORD_PATTERN.search(name)
    if not channel_match:
        channel_match = CHANNEL_NUMBER_PATTERN.search(name)

    if not channel_match:
        return None

    prefix = channel_match.group(1).strip()
    channel_num = int(channel_match.group(2))
    suffix = channel_match.group(3).strip() if len(channel_match.groups()) > 2 else ""

    # Create pattern template
    if CHANNEL_KEYWORD_PATTERN.search(name):
        keyword_match = KEYWORD_EXTRACT_PATTERN.search(name)
        keyword = keyword_match.group(1) if keyword_match else "Channel"
        if prefix and suffix:
            pattern = f"{prefix} {keyword} {{channel}} {suffix}"
        elif prefix:
            pattern = f"{prefix} {keyword} {{channel}}"
        elif suffix:
            pattern = f"{keyword} {{channel}} {suffix}"
        else:
            pattern = f"{keyword} {{channel}}"
    else:
        pattern = f"{prefix} {{channel}}"

    return pattern, channel_num


def _process_pdo_entries(device, pdo_type: str) -> tuple[dict, dict]:
    """Process PDO entries and group by channel pattern.

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
        for entry in pdo.findall("Entry"):
            name = entry.findtext("Name", "")
            if not name:
                continue

            index_str = entry.findtext("Index", "0")
            index = parse_hex_value(index_str)
            bit_len = int(entry.findtext("BitLen", "0"))
            data_type = entry.findtext("DataType", "UNKNOWN")

            index_group = (index >> 16) & 0xFFFF
            if index_group == 0:
                index_group = default_index_group

            access = "Read/Write" if is_output else "Read-only"
            size = (bit_len + 7) // 8
            ads_type = get_ads_type(data_type)

            channel_info = _extract_channel_pattern(name)

            if channel_info:
                pattern, channel_num = channel_info
                group_key = (pattern, index_group, size, ads_type, data_type, access)
                if group_key not in channel_groups:
                    channel_groups[group_key] = []
                channel_groups[group_key].append(channel_num)
            else:
                dup_key = (name, index_group, size, ads_type, data_type, access)
                duplicate_tracker[dup_key] = duplicate_tracker.get(dup_key, 0) + 1

    return channel_groups, duplicate_tracker


def _create_symbol_nodes(
    channel_groups: dict, duplicate_tracker: dict
) -> list[SymbolNode]:
    """Create SymbolNode list from grouped PDO data."""
    symbol_nodes = []

    for group_key, channel_nums in channel_groups.items():
        name_pattern, index_group, size, ads_type, data_type, access = group_key
        symbol_nodes.append(
            SymbolNode(
                name_template=name_pattern,
                index_group=index_group,
                size=size,
                ads_type=ads_type,
                type_name=data_type,
                channels=len(channel_nums),
                access=access,
                fastcs_name=to_pascal_case(name_pattern),
            )
        )

    for dup_key, count in duplicate_tracker.items():
        name, index_group, size, ads_type, data_type, access = dup_key
        if count > 1:
            name_pattern = f"{name} {{channel}}"
            symbol_nodes.append(
                SymbolNode(
                    name_template=name_pattern,
                    index_group=index_group,
                    size=size,
                    ads_type=ads_type,
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
                    size=size,
                    ads_type=ads_type,
                    type_name=data_type,
                    channels=1,
                    access=access,
                    fastcs_name=to_pascal_case(name),
                )
            )

    return symbol_nodes


def _parse_coe_objects(device) -> list[CoEObject]:
    """Parse CoE objects from device element."""
    coe_objects = []

    # Build datatype map for subindex details
    datatype_map = {}
    datatypes_section = device.find(".//Profile/Dictionary/DataTypes")
    if datatypes_section is not None:
        for datatype in datatypes_section.findall("DataType"):
            dt_name = datatype.findtext("Name", "")
            if not dt_name:
                continue

            subitems = []
            for subitem in datatype.findall("SubItem"):
                subidx_str = subitem.findtext("SubIdx", "0")
                try:
                    subidx = int(subidx_str)
                except ValueError:
                    continue

                sub_flags = subitem.find("Flags")
                sub_access = "ro"
                if sub_flags is not None:
                    sub_access = sub_flags.findtext("Access", "ro").lower()

                subitems.append(
                    {
                        "subindex": subidx,
                        "name": subitem.findtext("Name", ""),
                        "type": subitem.findtext("Type", ""),
                        "bitsize": int(subitem.findtext("BitSize", "0") or "0"),
                        "access": sub_access,
                    }
                )
            datatype_map[dt_name] = subitems

    objects_section = device.find(".//Profile/Dictionary/Objects")
    if objects_section is None:
        return coe_objects

    for obj in objects_section.findall("Object"):
        index_str = obj.findtext("Index", "0")
        try:
            coe_index = parse_hex_value(index_str)
        except ValueError:
            continue

        obj_name = obj.findtext("Name", "Unknown")
        type_name = obj.findtext("Type", "UNKNOWN")
        bit_size = int(obj.findtext("BitSize", "0"))

        flags = obj.find("Flags")
        access = flags.findtext("Access", "ro").lower() if flags is not None else "ro"

        datatype_subitems = datatype_map.get(type_name, [])

        subindices = []
        info_section = obj.find("Info")
        if info_section is not None:
            for idx, subitem in enumerate(info_section.findall("SubItem")):
                subitem_name = subitem.findtext("Name", f"SubIndex {idx}")

                subitem_info = subitem.find("Info")
                default_data = None
                if subitem_info is not None:
                    default_data = subitem_info.findtext("DefaultData")

                subitem_type = None
                subitem_bitsize = None
                subitem_access = None
                subindex_num = idx

                for dt_sub in datatype_subitems:
                    if dt_sub["name"] == subitem_name:
                        subindex_num = dt_sub["subindex"]
                        subitem_type = dt_sub["type"]
                        subitem_bitsize = dt_sub["bitsize"]
                        subitem_access = dt_sub["access"]
                        break

                if subitem_type is None and "SubIndex" in subitem_name:
                    try:
                        subindex_num = int(subitem_name.split()[-1])
                    except (ValueError, IndexError):
                        pass

                subindices.append(
                    CoESubIndex(
                        subindex=subindex_num,
                        name=subitem_name,
                        type_name=subitem_type,
                        bit_size=subitem_bitsize,
                        access=subitem_access,
                        default_data=default_data,
                    )
                )

        coe_objects.append(
            CoEObject(
                index=coe_index,
                name=obj_name,
                type_name=type_name,
                bit_size=bit_size,
                access=access,
                subindices=subindices,
            )
        )

    return coe_objects


def parse_terminal_details(
    xml_content: str,
    terminal_id: str,
    group_type: str | None = None,
) -> TerminalType | None:
    """Parse terminal XML to create detailed TerminalType.

    Args:
        xml_content: XML content string
        terminal_id: Terminal ID to find
        group_type: Optional group type

    Returns:
        TerminalType instance or None if parsing fails
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
                description = desc_text if desc_text else name_elem.text
                break
            elif name_elem.text:
                description = name_elem.text

        # Process PDOs
        tx_channels, tx_dups = _process_pdo_entries(device, "TxPdo")
        rx_channels, rx_dups = _process_pdo_entries(device, "RxPdo")

        # Merge channel groups
        for key, nums in rx_channels.items():
            if key in tx_channels:
                tx_channels[key].extend(nums)
            else:
                tx_channels[key] = nums

        for key, count in rx_dups.items():
            tx_dups[key] = tx_dups.get(key, 0) + count

        symbol_nodes = _create_symbol_nodes(tx_channels, tx_dups)
        coe_objects = _parse_coe_objects(device)

        return TerminalType(
            description=description,
            identity=identity,
            symbol_nodes=symbol_nodes,
            coe_objects=coe_objects,
            group_type=group_type,
        )

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
    """Create a default terminal type with placeholder values."""
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
                size=2,
                ads_type=65,
                type_name=type_name,
                channels=channel_count,
            ),
            SymbolNode(
                name_template="WcState^WcState",
                index_group=0xF021,
                size=0,
                ads_type=33,
                type_name="BIT",
                channels=1,
            ),
        ],
        group_type=group_type,
    )
