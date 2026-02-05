"""Dynamic type conversion utilities for TwinCAT/IEC 61131-3 types.

This module provides utilities for converting TwinCAT type names to numpy dtypes
and FastCS DataTypes, used for dynamic controller generation.
"""

import re
from dataclasses import dataclass

import numpy as np
from fastcs.datatypes import Bool, DataType, Float, Int, String, Waveform

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
        type_name: Original TwinCAT type name for special handling.

    Returns:
        FastCS DataType instance (Int, Float, String, Bool, or Waveform).

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
    group: str | None = None
    access: str | None = None

    def __post_init__(self) -> None:
        """Post-initialization checks."""
        if not self.name:
            raise ValueError("AdsItemBase requires a non-empty name.")
        if not self.type_name:
            self.type_name = "BIT"  # Default to INT for unknown types
        if not self.fastcs_name:
            raise ValueError("AdsItemBase requires a non-empty fastcs_name.")

    @property
    def fastcs_group(self) -> str | None:
        """Return the attribute group name."""

        return re.sub(r"[\s.]", "", self.group) if self.group else None

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
