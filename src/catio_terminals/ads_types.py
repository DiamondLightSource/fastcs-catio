"""ADS data type definitions and mappings.

This module provides the canonical mapping between type names and their
corresponding ADS data type IDs and sizes. Both fastcs-catio and the
ADS simulator use these definitions.
"""

from enum import IntEnum


class AdsDataType(IntEnum):
    """ADS data type identifiers.

    Reference:
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_utilities/35330059.html
    """

    VOID = 0
    """Reserved"""
    INT16 = 2
    """Signed 16 bit integer (INT16)"""
    INT32 = 3
    """Signed 32 bit integer (INT32)"""
    REAL32 = 4
    """32 bit floating point number (REAL)"""
    REAL64 = 5
    """64 bit floating point number (LREAL)"""
    INT8 = 16
    """Signed 8 bit integer (INT8)"""
    UINT8 = 17
    """Unsigned 8 bit integer (UINT8|BYTE)"""
    UINT16 = 18
    """Unsigned 16 bit integer (UINT16|WORD)"""
    UINT32 = 19
    """Unsigned 32 bit integer (UINT32|DWORD)"""
    INT64 = 20
    """Signed 64 bit integer (INT64)"""
    UINT64 = 21
    """Unsigned 64 bit integer (UINT64|LWORD)"""
    STRING = 30
    """String type (STRING)"""
    WSTRING = 31
    """Wide character type (WSTRING)"""
    REAL80 = 32
    """Reserved"""
    BIT = 33
    """Bit type (BIT)"""
    MAXTYPES = 34
    """Maximum available type"""
    BIGTYPE = 65
    """Structured type (STRUCT)"""


# Mapping from type name to (ads_type, size_in_bytes)
# Size of 0 indicates a bit-level type (accessed via bit index)
TYPE_INFO: dict[str, tuple[AdsDataType, int]] = {
    # Bit types (size=0 means bit-addressed)
    "BIT": (AdsDataType.BIT, 0),
    "BOOL": (AdsDataType.BIT, 0),
    # Integer types
    "SINT": (AdsDataType.INT8, 1),
    "INT": (AdsDataType.INT16, 2),
    "DINT": (AdsDataType.INT32, 4),
    "LINT": (AdsDataType.INT64, 8),
    "USINT": (AdsDataType.UINT8, 1),
    "UINT": (AdsDataType.UINT16, 2),
    "UDINT": (AdsDataType.UINT32, 4),
    "ULINT": (AdsDataType.UINT64, 8),
    # Byte/Word aliases
    "BYTE": (AdsDataType.UINT8, 1),
    "WORD": (AdsDataType.UINT16, 2),
    "DWORD": (AdsDataType.UINT32, 4),
    "LWORD": (AdsDataType.UINT64, 8),
    # Floating point types
    "REAL": (AdsDataType.REAL32, 4),
    "LREAL": (AdsDataType.REAL64, 8),
    # Special multi-bit types (treated as structured, 1 byte)
    "BIT2": (AdsDataType.BIGTYPE, 1),
    "BIT3": (AdsDataType.BIGTYPE, 1),
    "BIT4": (AdsDataType.BIGTYPE, 1),
    # Unknown/fallback type
    "UNKNOWN": (AdsDataType.BIGTYPE, 1),
}


def get_type_info(type_name: str) -> tuple[AdsDataType, int]:
    """Look up ADS type and size from a type name.

    Args:
        type_name: The type name (e.g., "INT", "BOOL", "UINT")

    Returns:
        Tuple of (AdsDataType, size_in_bytes).
        Size of 0 indicates a bit-level type.

    Raises:
        KeyError: If type_name is not recognized
    """
    return TYPE_INFO[type_name.upper()]


def get_ads_type(type_name: str) -> AdsDataType:
    """Get the ADS data type ID for a type name.

    Args:
        type_name: The type name (e.g., "INT", "BOOL", "UINT")

    Returns:
        AdsDataType enum value

    Raises:
        KeyError: If type_name is not recognized
    """
    return TYPE_INFO[type_name.upper()][0]


def get_size(type_name: str) -> int:
    """Get the size in bytes for a type name.

    Args:
        type_name: The type name (e.g., "INT", "BOOL", "UINT")

    Returns:
        Size in bytes (0 for bit types)

    Raises:
        KeyError: If type_name is not recognized
    """
    return TYPE_INFO[type_name.upper()][1]


def is_known_type(type_name: str) -> bool:
    """Check if a type name is a known standard type.

    Args:
        type_name: The type name to check

    Returns:
        True if the type has a known mapping
    """
    return type_name.upper() in TYPE_INFO
