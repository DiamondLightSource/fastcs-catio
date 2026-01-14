# ADS Data Types
# https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_plc_intro/2529388939.html&id=3451082169760117126

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Generic,
    Literal,
    Self,
    SupportsInt,
    TypeAlias,
    TypeVar,
    get_args,
    get_origin,
)

import numpy as np
import numpy.typing as npt

G = TypeVar("G", bound=npt.DTypeLike | npt.NDArray)
S = TypeVar("S")
# S = TypeVar("S", bound=SupportsInt | bytes | Sequence[int] | npt.NDArray)


class AdsMessageDataType(Generic[G, S]):
    """
    Generic class representing the data type used by the ADS system services.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_plc_intro/2529388939.html&id=3451082169760117126
    """

    def __init__(self, default: S):
        self.default = default
        """Default value for the data type."""

    def __get__(self, instance, owner) -> G: ...

    def __set__(self, instance, value: S): ...

    @classmethod
    def get_dtype(cls, datatype: Self) -> npt.DTypeLike:
        """
        Get the numpy data type from the AdsMessageDataType instance.

        :returns: the numpy data type

        :raises TypeError: exception arising when the AdsMessageDataType instance \
            isn't a valid numpy data type
        """
        np_type = get_args(datatype)[0]
        if isinstance(np_type, type) and issubclass(np_type, np.generic):
            # Keep numpy array scalar object types as they are
            return np_type
        if get_origin(np_type) == np.ndarray:
            # Extract type from np.ndarray[tuple[Literal[length]], np.dtype[np_type]]
            length_tuple, dtype_arg = get_args(np_type)
            length = get_args(get_args(length_tuple)[0])[0]
            if get_args(dtype_arg)[0] is np.bytes_:
                return f"S{length}"
        raise TypeError(f"AdsMessageDataType with unsupported numpy type: {np_type}")


@dataclass
class AmsNetId:
    """
    AmsNetId class representing the unique AmsNetId identifier of the TwinCAT device on
    the network which messages will be routed to using the ADS communication protocol.

    The 4-byte root is the unique identifier of the device, while the 2-byte mask is
    used to identify the network segment to which the device belongs.

    The AmsNetId can be converted to and from a byte stream or from a string in the
    standard dot-notation format (x.x.x.x.x.x).
    """

    root: tuple[int, int, int, int]
    """4-byte root of the AmsNetId"""
    mask: tuple[int, int]
    """2-byte mask of the AmsNetId"""

    @classmethod
    def from_bytes(cls, net_id: bytes) -> Self:
        """
        Convert a netid byte stream into a AmsNetId object.

        :param net_id: the netid value expressed as 6 bytes

        :returns: the AmsNetId expressed as tuples of integers

        :raises ValueError: if the netid is not exactly 6 bytes long
        """
        if len(net_id) != 6:
            raise ValueError("AMS NetID must be exactly 6 bytes long.")
        parts = np.frombuffer(net_id, dtype=np.uint8)
        return cls(tuple(parts[:4]), tuple(parts[4:]))

    @classmethod
    def from_string(cls, net_id: str) -> Self:
        """
        Convert a netid string from the standard dot-notation to a AmsNetId object.

        :param net_id: the netid value expressed as a string of format x.x.x.x.x.x

        :returns: the AmsNetId expressed as tuples of integers

        :raises ValueError: if the netid is not exactly 6 dot-separated octets
        """
        parts = [int(x) for x in net_id.split(".")]
        if len(parts) != 6:
            raise ValueError("AMS NetID must be exactly 6 dot-separated octets.")
        return cls((parts[0], parts[1], parts[2], parts[3]), (parts[4], parts[5]))

    def to_bytes(self) -> bytes:
        """
        Convert the AmsNetId object into a 6-byte array.

        :returns: the netid expressed as a byte stream
        """
        return (
            np.frombuffer(bytes(self.root + self.mask), dtype=np.uint8, count=6)
            .reshape((6,))
            .tobytes()
        )

    def to_string(self) -> str:
        """
        Convert the AmsNetId object into the standard dot-notation string.

        :returns: the netid expressed as a string of format x.x.x.x.x.x
        """
        return ".".join(map(str, self.root + self.mask))

    def __repr__(self) -> str:
        return f"AmsNetId(root={self.root}, mask={self.mask})"

    def __str__(self) -> str:
        return ".".join(map(str, self.root + self.mask))


@dataclass
class AmsAddress:
    """
    AmsAddress class representing the full AMS address of a TwinCAT device on the
    network.

    The AMS address consists of the AmsNetId and the port number on which the device \
        listens for ADS messages.
    The AmsAddress can be converted to and from a byte stream or from a string in the \
        standard notation (netid:port).
    """

    net_id: AmsNetId
    """AmsNetId of the TwinCAT device"""
    port: int
    """Port number of the TwinCAT device"""

    @classmethod
    def from_bytes(cls, address: bytes) -> Self:
        """
        Convert an AmsAddress byte stream into an AmsAddress object.

        :param address: the address value expressed as 8 bytes

        :returns: the AmsAddress including both netid and port

        :raises ValueError: if the input address is not exactly 8 bytes long
        """
        assert len(address) == 8, ValueError(
            "AMS Address must be exactly 8 bytes long."
        )
        netid = AmsNetId.from_bytes(address[:6])
        port = int.from_bytes(address[6:], byteorder="little", signed=False)
        return cls(netid, port)

    def to_bytes(self):
        """
        Convert the AmsAddress object into a byte stream.

        :returns: the AmsAddress expressed as a byte stream
        """
        return self.net_id.to_bytes() + self.port.to_bytes(
            length=2, byteorder="little", signed=False
        )

    @classmethod
    def from_string(cls, address: str):
        """
        Parse an AmsAddress object from a standard string notation (192.168.0.1.1.1:851)

        :param address: the address value expressed as a string of format netid:port

        :returns: the AmsAddress including both netid and port

        :raises ValueError: if the input address doesn't match the expected format
        """
        try:
            netid_str, port_str = address.split(":")
            netid = AmsNetId.from_string(netid_str)
            assert port_str.isdigit(), (
                f"String '{port_str}' contains non-digit characters or is empty."
            )
            port = int(port_str)
            return cls(netid, port)
        except Exception as e:
            raise ValueError(f"Invalid AmsAddress string '{address}'") from e

    def to_string(self) -> str:
        """
        Convert the AmsAddress object into the standard string notation.

        :returns: the AmsAddress expressed as a string of format netid:port
        """
        return f"{self.net_id.to_string()}:{self.port}"

    def __str__(self):
        return f"{self.net_id.to_string()}:{self.port}"


Length = TypeVar("Length", bound=int)
Dtype = TypeVar("Dtype", bound=np.generic)
ARRAY: TypeAlias = np.ndarray[tuple[Length], np.dtype[Dtype]]

BYTES6: TypeAlias = AdsMessageDataType[ARRAY[Literal[6], np.bytes_], bytes]
BYTES12: TypeAlias = AdsMessageDataType[ARRAY[Literal[12], np.bytes_], bytes]
BYTES16: TypeAlias = AdsMessageDataType[ARRAY[Literal[16], np.bytes_], bytes]

INT16: TypeAlias = AdsMessageDataType[np.int16, SupportsInt]
INT32: TypeAlias = AdsMessageDataType[np.int32, SupportsInt]

UINT8: TypeAlias = AdsMessageDataType[np.uint8, SupportsInt]
UINT16: TypeAlias = AdsMessageDataType[np.uint16, SupportsInt]
UINT32: TypeAlias = AdsMessageDataType[np.uint32, SupportsInt]
UINT64: TypeAlias = AdsMessageDataType[np.uint64, SupportsInt]
