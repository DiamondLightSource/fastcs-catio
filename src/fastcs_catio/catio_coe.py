"""CoE (CANopen over EtherCAT) utilities for dynamic controller generation.

This module provides classes and functions for handling CoE objects in
dynamically generated FastCS controllers.
"""

import re
from dataclasses import dataclass

import numpy as np
from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import DataType, Float, Int, String

from fastcs_catio.catio_attribute_io import CATioControllerCoEAttributeIORef
from fastcs_catio.catio_controller import CATioTerminalController

# Mapping from TwinCAT/IEC 61131-3 type names to numpy dtypes
TWINCAT_TO_NUMPY: dict[str, np.dtype] = {
    # Signed integer types
    "SINT": np.dtype(np.int8),
    "INT": np.dtype(np.int16),
    "DINT": np.dtype(np.int32),
    "LINT": np.dtype(np.int64),
    # Unsigned integer types
    "USINT": np.dtype(np.uint8),
    "UINT": np.dtype(np.uint16),
    "UDINT": np.dtype(np.uint32),
    "ULINT": np.dtype(np.uint64),
    # Byte/Word aliases (unsigned)
    "BYTE": np.dtype(np.uint8),
    "WORD": np.dtype(np.uint16),
    "DWORD": np.dtype(np.uint32),
    "LWORD": np.dtype(np.uint64),
    # Floating point types
    "REAL": np.dtype(np.float32),
    "LREAL": np.dtype(np.float64),
    # Boolean/bit types (stored as uint8)
    "BOOL": np.dtype(np.uint8),
    "BIT": np.dtype(np.uint8),
}


def twincat_type_to_numpy(type_name: str, bit_size: int | None = None) -> np.dtype:
    """Convert a TwinCAT/IEC 61131-3 type name to a numpy dtype.

    Handles STRING(n) types by returning a fixed-length byte string dtype.
    For unknown/compound types (like DT8020), uses bit_size to create a
    byte array dtype.

    Args:
        type_name: TwinCAT type name (e.g., "UINT", "DINT", "STRING(32)").
        bit_size: Size in bits for unknown/compound types (optional).

    Returns:
        Corresponding numpy dtype.

    Raises:
        ValueError: If the type name is not recognized and no bit_size given.
    """
    # Handle STRING(n) types
    string_match = re.match(r"STRING\((\d+)\)", type_name.upper())
    if string_match:
        length = int(string_match.group(1))
        return np.dtype(f"<S{length}")

    upper_name = type_name.upper()
    if upper_name in TWINCAT_TO_NUMPY:
        return TWINCAT_TO_NUMPY[upper_name]

    # For unknown/compound types, treat as byte array if bit_size is given
    if bit_size is not None:
        byte_count = (bit_size + 7) // 8  # Round up to whole bytes
        return np.dtype((np.uint8, byte_count))

    raise ValueError(f"Unknown TwinCAT type: {type_name}")


def numpy_dtype_to_fastcs(dtype: np.dtype) -> DataType:
    """Convert a numpy dtype to a FastCS DataType.

    Args:
        dtype: NumPy dtype to convert.

    Returns:
        FastCS DataType instance (Int, Float, or String).

    Raises:
        ValueError: If the dtype is not supported.
    """
    # Handle byte array types (compound types like DT8020)
    # These have shape > () and subdtype of uint8
    if dtype.subdtype is not None:
        base_dtype, shape = dtype.subdtype
        if base_dtype == np.uint8 and len(shape) == 1:
            # Treat as array of ints (byte array)
            return Int()

    # Handle string types (fixed-length byte strings)
    if dtype.kind == "S":
        return String(dtype.itemsize)

    # Handle boolean types
    if dtype == np.bool_:
        return Int()

    # Handle signed integer types
    if dtype.kind == "i":  # signed integer
        return Int()

    # Handle unsigned integer types
    if dtype.kind == "u":  # unsigned integer
        return Int()

    # Handle floating point types
    if dtype.kind == "f":  # floating point
        return Float()

    raise ValueError(f"Unsupported numpy dtype: {dtype}")


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
        bit_size: Size in bits (for compound types like DT8020).
    """

    name: str
    type_name: str
    index: int
    subindex: int
    bit_size: int | None = None

    def __str__(self) -> str:
        """Return the string representation like 'CoE:8000:01'."""
        return f"CoE:{self.index:04X}:{self.subindex:02X}"

    @property
    def is_coe(self) -> bool:
        """Return True since this is a CoE item."""
        return True

    @property
    def index_hex(self) -> str:
        """Return the index as a hex string with 0x prefix (e.g., '0x8000')."""
        return f"0x{self.index:04X}"

    @property
    def subindex_hex(self) -> str:
        """Return the subindex as a hex string with 0x prefix (e.g., '0x01')."""
        return f"0x{self.subindex:02X}"

    @property
    def is_primitive_type(self) -> bool:
        """Return True if this is a primitive TwinCAT type (not a compound type).

        Primitive types are those in TWINCAT_TO_NUMPY or STRING(n) types.
        Compound types (like DT8020, DT0800EN02) start with 'DT' or are otherwise
        not in the known type mapping.
        """
        # Check for STRING(n) types
        if re.match(r"STRING\(\d+\)", self.type_name.upper()):
            return True
        # Check if it's in the known type mapping
        return self.type_name.upper() in TWINCAT_TO_NUMPY

    @property
    def numpy_dtype(self) -> np.dtype:
        """Return the numpy dtype for this CoE item's type_name.

        For compound types (like DT8020), uses bit_size to create a byte array.

        Returns:
            numpy dtype corresponding to the TwinCAT type.

        Raises:
            ValueError: If the type_name is not recognized and no bit_size.
        """
        return twincat_type_to_numpy(self.type_name, self.bit_size)

    @property
    def fastcs_datatype(self) -> DataType:
        """Return the FastCS DataType for this CoE item's type_name.

        Returns:
            FastCS DataType (Int, Float, or String).

        Raises:
            ValueError: If the type_name cannot be converted.
        """
        return numpy_dtype_to_fastcs(self.numpy_dtype)


def generate_coe_attr_name(base_name: str, fallback: str) -> str:
    """Generate a snake_case attribute name from a base name.

    Args:
        base_name: The base name to convert (e.g., "Max Velocity").
        fallback: Fallback name if base_name is invalid (e.g., "coe_8000").

    Returns:
        snake_case attribute name (e.g., "max_velocity").
    """
    # Replace non-alphanumeric chars with spaces, then convert to snake_case
    cleaned = re.sub(r"[^a-zA-Z0-9]", " ", base_name)
    attr_name = "_".join(word.lower() for word in cleaned.split() if word)
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
    base_name = sub.name if sub.name else f"sub_{sub.subindex:02x}"
    fallback = f"coe_{coe_obj.index:04x}_{sub.subindex:02x}"
    attr_name = generate_coe_attr_name(base_name, fallback)

    # Ensure unique name with collision handling
    attr_name = ensure_unique_coe_name(attr_name, created_coe_attrs)
    created_coe_attrs[attr_name] = sub.subindex

    # Generate description and ADS name
    desc = f"CoE{coe_obj.index:04X}{sub.subindex:02X}"
    if len(desc) > 40:
        desc = desc[:40]

    is_readonly = (sub.access or coe_obj.access).lower() in ("ro", "read-only")

    # Use subindex type_name if available, otherwise fall back to parent object type
    type_name = sub.type_name if sub.type_name else coe_obj.type_name
    # Use subindex bit_size if available, otherwise fall back to parent object bit_size
    bit_size = sub.bit_size if sub.bit_size is not None else coe_obj.bit_size
    ads_item = CoEAdsItem(
        name=coe_obj.name,
        type_name=type_name,
        index=coe_obj.index,
        subindex=sub.subindex,
        bit_size=bit_size,
    )

    # Get FastCS datatype from the type_name via numpy dtype conversion
    try:
        datatype = ads_item.fastcs_datatype
    except ValueError:
        # Fall back to Int for unknown types
        datatype = Int()

    add_attribute_fn(controller, attr_name, ads_item, is_readonly, desc, datatype)


def add_coe_attribute(
    controller: CATioTerminalController,
    attr_name: str,
    ads_item: CoEAdsItem,
    is_readonly: bool,
    datatype: DataType,
) -> None:
    """Add a CoE FastCS attribute to a controller.

    Creates a CATioControllerCoEAttributeIORef with:
    - index_hex and subindex_hex: CoE address (from YAML via ads_item)
    - numpy_dtype: Data type for the CoE parameter (from YAML via ads_item)
    - AmsAddress: Obtained from client.get_coe_ams_address(controller.io)

    Args:
        controller: The controller to add the attribute to.
        attr_name: The FastCS attribute name.
        ads_item: The CoE ADS item containing index, subindex, and type info.
        is_readonly: Whether the attribute is read-only.
        desc: The attribute description.
        datatype: The FastCS datatype.

    Raises:
        AssertionError: If controller.io is not an IOSlave.
    """
    from fastcs_catio.devices import IOSlave

    # CoE parameters only apply to terminal controllers (IOSlave)
    assert isinstance(controller.io, IOSlave), (
        f"CoE attributes require IOSlave, got {type(controller.io)}"
    )

    # Skip io_ref for compound types - only create for primitive types
    if not ads_item.is_primitive_type:
        # For compound types, just record the mapping without creating an attribute
        # TODO: Add support for compound CoE types later
        return

    # Get AmsAddress from the client using the controller's IOSlave
    address = controller.connection.client.get_coe_ams_address(controller.io)

    # Skip io_ref for compound types - only create for primitive types
    if not ads_item.is_primitive_type:
        # For compound types, just record the mapping without creating an attribute
        # TODO add support for compound types with subindcies
        io_ref = None
    else:
        # Create the CoE io_ref with all required information
        io_ref = CATioControllerCoEAttributeIORef(
            name=attr_name,
            index=ads_item.index_hex,
            subindex=ads_item.subindex_hex,
            address=address,
            dtype=ads_item.numpy_dtype,
        )

    if is_readonly:
        controller.add_attribute(
            attr_name,
            AttrR(
                datatype=datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    else:
        controller.add_attribute(
            attr_name,
            AttrRW(
                datatype=datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    controller.ads_name_map[attr_name] = str(ads_item)
