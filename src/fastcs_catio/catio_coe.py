"""CoE (CANopen over EtherCAT) utilities for dynamic controller generation.

This module provides classes and functions for handling CoE objects in
dynamically generated FastCS controllers.
"""

import re
from dataclasses import dataclass

import numpy as np
from fastcs.attributes import AttrR, AttrRW
from fastcs.datatypes import Bool, DataType, Float, Int, String, Waveform

from fastcs_catio.catio_attribute_io import CATioControllerCoEAttributeIORef
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.logging import get_logger

logger = get_logger(__name__)

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
    "OutputBits": np.dtype(np.uint8),
}

# TWINCAT_TO_FASTCS: dict[str, DataType] = {
#     # Signed integer types
#     "SINT": Int(),
#     "INT": Int(),
#     "DINT": Int(),
#     "LINT": Int(),
#     # Unsigned integer types
#     "USINT": Int(),
#     "UINT": Int(),
#     "UDINT": Int(),
#     "ULINT": Int(),
#     # Byte/Word aliases (unsigned)
#     "BYTE": Int(),
#     "WORD": Int(),
#     "DWORD": Int(),
#     "LWORD": Int(),
#     # Floating point types
#     "REAL": Float(),
#     "LREAL": Float(),
#     # Boolean/bit types (stored as uint8)
#     "BOOL": Bool(),
#     "BIT": Bool(),
# }

STRING_MATCH = re.compile(r"STRING\((\d+)\)")
BYTE_ARRAY_MATCH = re.compile(r"ARRAY\s*\[(\d+)\.\.(\d+)\]\s*OF\s*BYTE")


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
    match = STRING_MATCH.match(type_name.upper())
    if match:
        length = int(match.group(1))
        return np.dtype(f"<S{length}")

    # Handle ARRAY [0..n] OF BYTE types
    match = BYTE_ARRAY_MATCH.match(type_name.upper())
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        byte_count = end - start + 1
        return np.dtype((np.uint8, (byte_count,)))

    upper_name = type_name.upper()
    if upper_name in TWINCAT_TO_NUMPY:
        return TWINCAT_TO_NUMPY[upper_name]

    # For unknown/compound types, treat as byte array if bit_size is given
    if bit_size is not None:
        byte_count = (bit_size + 7) // 8  # Round up to whole bytes
        return np.dtype((np.uint8, byte_count))

    # default to Int for unknown types
    return np.dtype(np.int8)


def numpy_dtype_to_fastcs(dtype: np.dtype, type_name: str) -> DataType:
    """Convert a numpy dtype to a FastCS DataType.

    Args:
        dtype: NumPy dtype to convert.

    Returns:
        FastCS DataType instance (Int, Float, or String).

    Raises:
        ValueError: If the dtype is not supported.
    """
    if type_name.upper() in ["BOOL", "BIT", "OUTPUTBITS"]:
        return Bool()

    # Handle byte array types (compound types like DT8020)
    # These have shape > () and subdtype of uint8
    if dtype.subdtype is not None:
        base_dtype, shape = dtype.subdtype
        if base_dtype == np.uint8 and len(shape) == 1:
            # Treat as array of ints (byte array)
            return Waveform(array_dtype=np.uint8, shape=shape)

    # Handle string types (fixed-length byte strings)
    # Add 1 to accommodate null terminator from CoE reads
    if dtype.kind == "S":
        return String(dtype.itemsize + 1)

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
class AdsItemBase:
    """Base class for ADS items (symbols and CoE objects).

    Provides common fields and properties for type conversion.

    Args:
        name: The item name (e.g., "Channel 1" or "Hardware version").
        type_name: The TwinCAT type name (e.g., "UINT", "INT").
        fastcs_name: The FastCS attribute name (snake_case).
        access: Access type (e.g., "Read-only", "ro", "rw").
    """

    name: str
    type_name: str
    fastcs_name: str
    access: str | None = None

    @property
    def readonly(self) -> bool:
        """Return True if this item is read-only.

        Subclasses may override for specific access string formats.
        """
        if self.access is None:
            return True
        access_lower = self.access.lower()
        # Handle both "Read-only"/"Read/Write" and "ro"/"rw" formats
        return "write" not in access_lower and access_lower not in ("rw", "wo")

    @property
    def is_primitive_type(self) -> bool:
        """Return True if this is a primitive TwinCAT type.

        Primitive types are those in TWINCAT_TO_NUMPY or STRING(n) types.
        Compound types (like DT8020, DT0800EN02) are not primitive.
        """
        if STRING_MATCH.match(self.type_name.upper()):
            return True
        if BYTE_ARRAY_MATCH.match(self.type_name.upper()):
            return True
        return self.type_name.upper() in TWINCAT_TO_NUMPY

    @property
    def numpy_dtype(self) -> np.dtype:
        """Return the numpy dtype for this item's type_name.

        Returns:
            numpy dtype corresponding to the TwinCAT type.

        Raises:
            ValueError: If the type_name is not recognized.
        """
        return twincat_type_to_numpy(self.type_name)

    @property
    def fastcs_datatype(self) -> DataType:
        """Return the FastCS DataType for this item's type_name.

        Returns:
            FastCS DataType (Int, Float, or String).

        Raises:
            ValueError: If the type_name cannot be converted.
        """
        try:
            return numpy_dtype_to_fastcs(self.numpy_dtype, self.type_name)
        except ValueError:
            return Int()  # Fall back for unknown types


@dataclass
class CoEAdsItem(AdsItemBase):
    """ADS item for CoE (CANopen over EtherCAT) objects.

    Stores the index and subindex as integers for use with
    CATioControllerCoEAttributeIORef.

    Args:
        name: The CoE object name (e.g., "Hardware version").
        type_name: The TwinCAT type name (e.g., "UINT").
        fastcs_name: The FastCS attribute name (snake_case).
        access: Access type (e.g., "ro", "rw").
        index: The CoE object index (e.g., 0x8000).
        subindex: The CoE object subindex (e.g., 0x01).
        bit_size: Size in bits (for compound types like DT8020).
    """

    index: int = 0
    subindex: int = 0
    bit_size: int | None = None

    def __str__(self) -> str:
        """Return the string representation like 'CoE:8000:01'."""
        return f"CoE:{self.index:04X}:{self.subindex:02X}"

    @property
    def index_hex(self) -> str:
        """Return the index as a hex string with 0x prefix (e.g., '0x8000')."""
        return f"0x{self.index:04X}"

    @property
    def subindex_hex(self) -> str:
        """Return the subindex as a hex string with 0x prefix (e.g., '0x0001')."""
        return f"0x{self.subindex:04X}"

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


def add_coe_attribute(
    controller: CATioTerminalController,
    ads_item: CoEAdsItem,
) -> None:
    """Add a CoE FastCS attribute to a controller.

    Creates a CATioControllerCoEAttributeIORef with:
    - index_hex and subindex_hex: CoE address (from YAML via ads_item)
    - numpy_dtype: Data type for the CoE parameter (from YAML via ads_item)
    - AmsAddress: Obtained from client.get_coe_ams_address(controller.io)

    Args:
        controller: The controller to add the attribute to.
        ads_item: The CoE ADS item containing index, subindex, type, fastcs_name,
            and access.

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
        logger.warning(f"Skipping creation of CoE item {ads_item}")
        return

    # Get AmsAddress from the client using the controller's IOSlave
    address = controller.connection.client.get_coe_ams_address(controller.io)

    # skip compound types as we do their sub inidices separately
    if not ads_item.is_primitive_type:
        return

    io_ref = CATioControllerCoEAttributeIORef(
        name=ads_item.fastcs_name,
        index=ads_item.index_hex,
        subindex=ads_item.subindex_hex,
        address=address,
        dtype=ads_item.numpy_dtype,
    )

    if ads_item.readonly:
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrR(
                datatype=ads_item.fastcs_datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    else:
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrRW(
                datatype=ads_item.fastcs_datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    controller.ads_name_map[ads_item.fastcs_name] = str(ads_item)
