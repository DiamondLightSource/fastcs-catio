"""CoE (CANopen over EtherCAT) object parsing for Beckhoff terminal XML files."""

from catio_terminals.models import CoEObject, CoESubIndex
from catio_terminals.xml.constants import parse_hex_value


def _build_datatype_map(device) -> dict[str, list[dict]]:
    """Build a map of datatype names to their subitem definitions.

    Args:
        device: lxml Device element

    Returns:
        Dict mapping datatype names to lists of subitem info dicts
    """
    datatype_map: dict[str, list[dict]] = {}

    datatypes_section = device.find(".//Profile/Dictionary/DataTypes")
    if datatypes_section is None:
        return datatype_map

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

    return datatype_map


def _parse_subindices(info_section, datatype_subitems: list[dict]) -> list[CoESubIndex]:
    """Parse subindices from object Info section.

    Args:
        info_section: lxml Info element from Object
        datatype_subitems: List of subitem dicts from datatype definition

    Returns:
        List of CoESubIndex instances
    """
    subindices = []

    if info_section is None:
        return subindices

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

        # Match with datatype definition to get type info
        for dt_sub in datatype_subitems:
            if dt_sub["name"] == subitem_name:
                subindex_num = dt_sub["subindex"]
                subitem_type = dt_sub["type"]
                subitem_bitsize = dt_sub["bitsize"]
                subitem_access = dt_sub["access"]
                break

        # Try to extract subindex from name if not found in datatype
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

    return subindices


def parse_coe_objects(device) -> list[CoEObject]:
    """Parse CoE objects from device element.

    Args:
        device: lxml Device element

    Returns:
        List of CoEObject instances
    """
    coe_objects = []

    # Build datatype map for subindex details
    datatype_map = _build_datatype_map(device)

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
        info_section = obj.find("Info")
        subindices = _parse_subindices(info_section, datatype_subitems)

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
