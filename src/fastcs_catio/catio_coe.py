"""CoE (CANopen over EtherCAT) utilities for dynamic controller generation.

This module provides classes and functions for handling CoE objects in
dynamically generated FastCS controllers.
"""

from dataclasses import dataclass

from fastcs.attributes import AttrRW
from fastcs.datatypes import Int

from fastcs_catio.catio_controller import CATioTerminalController


@dataclass
class CoEAdsItem:
    """ADS item for CoE (CANopen over EtherCAT) objects.

    Stores the index and subindex as integers for use with
    CATioControllerCoEAttributeIORef.

    Args:
        name: The symbol name (e.g., "Channel 1").
        type_name: The type name (e.g., "UINT").
        index: The CoE object index (e.g., 0x8000).
        subindex: The CoE object subindex (e.g., 0x01).
    """

    name: str
    type_name: str
    index: int
    subindex: int

    def __str__(self) -> str:
        """Return the string representation like 'CoE:8000:01'."""
        return f"CoE:{self.index:04X}:{self.subindex:02X}"

    @property
    def is_coe(self) -> bool:
        """Return True since this is a CoE item."""
        return True

    @property
    def index_hex(self) -> str:
        """Return the index as a hex string (e.g., '8000')."""
        return f"{self.index:04X}"

    @property
    def subindex_hex(self) -> str:
        """Return the subindex as a hex string (e.g., '01')."""
        return f"{self.subindex:02X}"


def generate_coe_attr_name(base_name: str, fallback: str) -> str:
    """Generate a PascalCase attribute name from a base name.

    Args:
        base_name: The base name to convert (e.g., "max_velocity").
        fallback: Fallback name if base_name is invalid (e.g., "CoE8000").

    Returns:
        PascalCase attribute name (e.g., "MaxVelocity").
    """
    attr_name = "".join(
        word.capitalize() for word in base_name.replace("_", " ").split()
    )
    if not attr_name or not attr_name[0].isalpha():
        attr_name = fallback
    return attr_name


def ensure_unique_coe_name(
    attr_name: str, created_attrs: dict[str, int], max_length: int = 39
) -> str:
    """Ensure CoE attribute name is unique by adding suffix if needed.

    Args:
        attr_name: The proposed attribute name.
        created_attrs: Dict of already-created attribute names.
        max_length: Maximum length before truncation (leaves room for suffix).

    Returns:
        Unique attribute name with suffix if collision detected.
    """
    # Truncate to max_length to leave room for collision suffix
    attr_name = attr_name[:max_length]

    original_name = attr_name
    suffix = 0
    while attr_name in created_attrs:
        if suffix < 10:
            attr_name = f"{original_name}{suffix}"
        else:
            # Use letters after digits exhausted
            attr_name = f"{original_name}{chr(ord('A') + suffix - 10)}"
        suffix += 1
    return attr_name


def process_coe_subindex(
    coe_obj,
    sub,
    created_coe_attrs: dict[str, int],
    controller: CATioTerminalController,
    add_attribute_fn,
) -> None:
    """Process a single CoE subindex and add it as an attribute.

    Args:
        coe_obj: The parent CoE object.
        sub: The subindex to process.
        created_coe_attrs: Dict tracking created attribute names.
        controller: The controller to add the attribute to.
        add_attribute_fn: Function to add attributes to the controller.
    """
    # Skip subindex 0 (count/descriptor, EtherCAT standard)
    if sub.subindex == 0:
        return

    # Generate attribute name from subindex name
    base_name = sub.name if sub.name else f"Sub{sub.subindex:02X}"
    fallback = f"CoE{coe_obj.index:04X}{sub.subindex:02X}"
    attr_name = generate_coe_attr_name(base_name, fallback)

    # Ensure unique name with collision handling
    attr_name = ensure_unique_coe_name(attr_name, created_coe_attrs)
    created_coe_attrs[attr_name] = sub.subindex

    # Generate description and ADS name
    desc = f"CoE{coe_obj.index:04X}{sub.subindex:02X}"
    if len(desc) > 40:
        desc = desc[:40]

    is_readonly = (sub.access or coe_obj.access).lower() in ("ro", "read-only")

    datatype = Int()  # TODO: map sub.type_name to FastCS type
    ads_item = CoEAdsItem(
        name=coe_obj.name,
        type_name=coe_obj.type_name,
        index=coe_obj.index,
        subindex=sub.subindex,
    )

    add_attribute_fn(controller, attr_name, ads_item, is_readonly, desc, datatype)


def add_coe_attribute(
    controller: CATioTerminalController,
    attr_name: str,
    ads_item: CoEAdsItem,
    is_readonly: bool,
    desc: str,
    datatype: Int,
) -> None:
    """Add a CoE FastCS attribute to a controller.

    Note: CoE attributes are added as read-write but without io_ref initially.
    The io_ref will be populated later by bind_io_refs when the device connects.

    Args:
        controller: The controller to add the attribute to.
        attr_name: The FastCS attribute name.
        ads_item: The CoE ADS item.
        is_readonly: Whether the attribute is read-only (currently unused for CoE).
        desc: The attribute description.
        datatype: The FastCS datatype.
    """
    # CoE attributes need address and dtype which aren't available yet.
    # Store the CoEAdsItem; io_ref created when device connects.
    # For now, create without io_ref - populated by bind_io_refs.
    io_ref = None
    # TODO - we will want to make an IORef something like this
    # can we collect enough info from the YAML and the current
    # client to build this?????
    #
    # io_ref = CATioControllerCoEAttributeIORef(
    #     name=ads_item.name,
    #     index=ads_item.index_hex,
    #     subindex=ads_item.subindex_hex,
    #     address=AmsAddress.from_string(
    #         "5.166.203.208.2.1:88"
    #     ),  # Placeholder, real address set later
    #     dtype=np.dtype("uint32"),  # Placeholder, real dtype set later
    # )
    controller.add_attribute(
        attr_name,
        AttrRW(
            datatype=datatype,
            io_ref=io_ref,
            group=controller.attr_group_name,
            initial_value=None,
            description=desc,
        ),
    )
    controller.ads_name_map[attr_name] = str(ads_item)
    # Store the typed AdsName for later io_ref binding
    ads_names_attr = "ads_names"
    if not hasattr(controller, ads_names_attr):
        setattr(controller, ads_names_attr, {})
    getattr(controller, ads_names_attr)[attr_name] = ads_item
