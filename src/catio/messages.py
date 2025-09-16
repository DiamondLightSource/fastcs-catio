from collections.abc import Iterator, Sequence
from typing import ClassVar, SupportsInt, get_origin

import numpy as np
from typing_extensions import Any, Self, dataclass_transform, get_type_hints

from ._constants import (
    TWINCAT_STRING_ENCODING,
    AdsDataType,
    CommandId,
    ErrorCode,
    IndexGroup,
    StateFlag,
    SymbolFlag,
    TransmissionMode,
)
from ._types import (
    BYTES6,
    BYTES12,
    BYTES16,
    UINT8,
    UINT16,
    UINT32,
    UINT64,
    AdsMessageDataType,
)


def _get_field_values(
    cls, fields: Sequence[str], kwargs: dict[str, Any]
) -> Iterator[Any]:
    """
    :params cls: the Message object type to extract values from
    :params fields: the names of the various fields which characterize this Message \
        object
    :param kwargs: map of available fields and their associated values which define \
        this Message object

    :returns: a generator of the values of the fields in the Message object

    :raises KeyError: exception arising when a required field was expected \
        but not found in the Message data structure
    """
    for field in fields:
        # Try first from kwargs
        value = kwargs.get(field, None)
        if value is None:
            # If not get it from class defaults
            value = cls.__dict__.get(field, None).default
        if value is None:
            # It was required but not passed
            raise KeyError(f"{field} is a required argument")
        yield value


def _get_dtype_arg(annotation: Any) -> Any:
    """
    Get the numpy data type from the given annotation.

    :params annotation: the type annotation to extract the numpy data type from

    :returns: the numpy data type

    :raises TypeError: exception arising when the annotation isn't a valid numpy type
    """
    if get_origin(annotation) is AdsMessageDataType:
        # If we have AdsMessageDataType[np_type, coercible_type], extract np_type
        return AdsMessageDataType.get_dtype(annotation)
    elif issubclass(annotation, np.generic):
        # If we have a subclass of a numpy generic that will do
        return annotation

    raise TypeError(annotation)


@dataclass_transform(kw_only_default=True)
class Message:
    """
    Define a generic ADS message type which the various message structures conform to.

    Instance attributes:
        _value: numpy NDArray based on the specific structure of the ADS message type

    :raises TypeError: exception arising when trying to instantiate a Message object \
        with both buffer and kwargs.
    """

    data: bytes
    """Array of bytes representing the data associated with the ADS message"""
    dtype: ClassVar[np.dtype]
    """Numpy data type representing the ADS Message."""

    def __init__(self, buffer: bytes = b"", *, data: bytes = b"", **kwargs):
        if buffer:
            if kwargs:
                raise TypeError(
                    "Can't have a Message class instantiated with both buffer and kwargs."
                )
            self._value = np.frombuffer(buffer, self.dtype, count=1)
            self.data = buffer[self._value.nbytes :]
        else:
            fields = self.dtype.fields
            values = (
                tuple(_get_field_values(type(self), list(fields.keys()), kwargs))
                if fields is not None
                else ()
            )
            self._value = np.array([values], dtype=self.dtype)
            self.data = data

    def __getattr__(self, name: str) -> Any:
        """
        Overriding method used to access the value of the Message object attributes.
        """
        return self._value[name][0]

    def __init_subclass__(cls):
        """
        Get the type of the Message object as a numpy data type.
        It includes all fields specific to that Message, except for the 'data' field.
        Its value is computed once and then cached as a normal attribute \
            for the life of the instance.

        :returns: the ADS message data type
        """
        items = []
        for name, annotation in get_type_hints(cls).items():
            if name not in {"data", "dtype"}:
                items.append((name, _get_dtype_arg(annotation)))
        cls.dtype = np.dtype(items)

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """
        Create a Message object whose value is a numpy NDArray defined from the given \
            array of bytes.

        :param buffer: the array of bytes characterising the type of Message

        :returns: an instance of the Message class
        """
        return cls(buffer)

    def to_bytes(self, include_data: bool = True) -> bytes:
        """
        Convert a Message object into an array of bytes.

        :returns: a byte array representing the ADS message and its associated data
        """
        return (
            (self._value.tobytes() + self.data)
            if include_data
            else self._value.tobytes()
        )


class MessageRequest(Message):
    """Message interface for an ADS request to the server."""

    ...


class MessageResponse(Message):
    """Message interface for an ADS response from the server."""

    ...


class AmsHeader(Message):
    """
    AMS Header structure included in all ADS communications.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115847307.html&id=7738940192708835096
    """

    target_net_id: BYTES6
    """The AMS netid of the station for which the packet is intended"""
    target_port: UINT16
    """The AMS port of the station for which the packet is intended"""
    source_net_id: BYTES6
    """The AMS netid of the station from which the packet is sent"""
    source_port: UINT16
    """The AMS port of the station from which the packet is sent"""
    command_id: CommandId
    """ADS command id"""
    state_flags: StateFlag
    """Defines the protocol (bit7: TCP/UDP), interface (bit3: ADS) and message type \
        (bit1: request/response)"""
    length: UINT32
    """Length of the data in bytes attached to this header"""
    error_code: ErrorCode
    """ADS error number"""
    invoke_id: UINT32
    """Id used to map a received response to a sent request"""


# ===================================================================
# ===== ETHERCAT I/O PROPERTIES
# ===================================================================


class IOIdentity(Message):
    """
    Define the identity parameters of an EtherCAT device or slave.
    """

    vendor_id: UINT32
    """The vendor id number"""
    product_code: UINT32
    """The product code"""
    revision_number: UINT32
    """The revision number"""
    serial_number: UINT32
    """The serial number"""

    def __str__(self):
        return f"code:{self.product_code}, s/n:{self.serial_number}"


class DeviceFrames(Message):
    """
    Define the frame counters of an EtherCAT device.
    """

    time: UINT32
    """System time"""
    cyclic_sent: UINT32
    """Number of cyclic frames sent by the master device"""
    cyclic_lost: UINT32
    """Number of lost cyclic frames"""
    acyclic_sent: UINT32
    """Number of acyclic frames sent by the master device"""
    acyclic_lost: UINT32
    """Number of lost acyclic frames"""

    def __array__(self):
        return np.array(
            [
                self.time,
                self.cyclic_sent,
                self.cyclic_lost,
                self.acyclic_sent,
                self.acyclic_lost,
            ],
            dtype=np.uint32,
        )

    @property
    def __array_struct__(self):
        return self.__array__().__array_struct__


class SlaveCRC(Message):
    """
    Define the cyclic redundancy check error counters of an EtherCAT slave.
    Ports B, C and D may not be used, thus potentially absent from an ADS response.
    """

    portA_crc: UINT32
    """CRC error counter of communication port A"""
    portB_crc: UINT32
    """CRC error counter of communication port B"""
    portC_crc: UINT32
    """CRC error counter of communication port C"""
    portD_crc: UINT32
    """CRC error counter of communication port D"""

    def __array__(self):
        return np.array(
            [
                self.portA_crc,
                self.portB_crc,
                self.portC_crc,
                self.portD_crc,
            ],
            dtype=np.uint32,
        )

    @property
    def __array_struct__(self):
        return self.__array__().__array_struct__


class SlaveState(Message):
    """
    Define the EtherCAT state and link status of an EtherCAT slave.
    """

    eCAT_state: UINT8
    """The EtherCAT state"""
    link_status: UINT8
    """The link status for communication"""

    def __array__(self):
        return np.array(
            [
                self.eCAT_state,
                self.link_status,
            ],
            dtype=np.uint8,
        )

    @property
    def __array_struct__(self):
        return self.__array__().__array_struct__


class AdsSymbolTableInfo(Message):
    """
    Define the symbol table information stored on the I/O server.
    """

    symbol_count: UINT32
    """The number of symbols accessible on the device"""
    table_length: UINT32
    """The length of the symbol table uploaded in the controller"""
    reserved: BYTES12
    """Unidentified additional data used by TwinCAT"""


class AdsSymbolTableEntry(Message):
    """
    ADS devices that support symbol names store those names in an internal table.
    """

    read_length: UINT32
    """Length of the complete symbol entry data in bytes"""
    index_group: UINT32
    """Index group of the symbol"""
    index_offset: UINT32
    """Index offset of the symbol"""
    size: UINT32
    """Size of the symbol in bytes (0 corresponds to 'bit')"""
    ads_type: AdsDataType
    """ADS data type of the symbol"""
    flag: SymbolFlag
    """ADS symbol flag"""
    name_size: UINT16
    """Length of the symbol name in bytes (null terminating character not counted)"""
    type_size: UINT16
    """Length of the symbol type name in bytes \
        (null terminating character not counted)"""
    comment_size: UINT16
    """Length of the entry comment in bytes (null terminating character not counted)"""
    data: bytes
    """Symbol entry data"""


# ===================================================================
# ===== INFO
# ===================================================================


class AdsReadDeviceInfoRequest(MessageRequest):
    """
    ADS Read device Info packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    pass  # No additional data required


class AdsReadDeviceInfoResponse(MessageResponse):
    """
    ADS Read Device Info data structure received in response to an \
        ADS Read Device Info request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    result: ErrorCode
    """ADS error number"""
    major_version: UINT8
    """Major version number of the ADS device"""
    minor_version: UINT8
    """Minor version number of the ADS device"""
    version_build: UINT16
    """Build number"""
    device_name: BYTES16
    """Name of the ADS device"""


# ===================================================================
# ===== STATE
# ===================================================================


class AdsReadStateRequest(MessageRequest):
    """
    ADS Read State packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115878923.html&id=6874981934243835072
    """

    pass  # No additional data required


class AdsReadStateResponse(MessageResponse):
    """
    ADS Read State data structure received in response to an ADS Read State request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115878923.html&id=6874981934243835072
    """

    result: ErrorCode
    """ADS error number"""
    ads_state: UINT16
    """ADS status"""
    device_state: UINT16
    """Device status"""


# ===================================================================
# ===== READ
# ===================================================================


class AdsReadRequest(MessageRequest):
    """
    ADS Read packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    index_group: IndexGroup
    """Index group of the data"""
    index_offset: UINT32
    """Index offset of the data"""
    read_length: UINT32
    """Length of the data in bytes which is read"""

    @classmethod
    def read_device_count(cls) -> Self:
        """
        An ADS request to read the number of devices registered with the I/O server.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGR_IODEVICE_STATE_BASE,
            index_offset=0x2,
            read_length=np.dtype(np.uint32).itemsize,
        )

    @classmethod
    def read_device_ids(cls, device_count: SupportsInt) -> Self:
        """
        An ADS request to read the id of the devices registered with the I/O server.
        (Note: the first index will represent the device count; device ids will follow)

        :param device_count: the number of registered EtherCAT devices

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGR_IODEVICE_STATE_BASE,
            index_offset=0x1,
            read_length=(int(device_count) + 1) * np.dtype(np.uint16).itemsize,
        )

    @classmethod
    def read_device_type(cls, device_id: int) -> Self:
        """
        An ADS request to read the type of a given EtherCAT device.

        :param device_id: the id of the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup(
                int(IndexGroup.ADSIGR_IODEVICE_STATE_BASE + device_id)
            ),
            index_offset=0x7,
            read_length=np.dtype(np.uint16).itemsize,
        )

    @classmethod
    def read_device_name(cls, device_id: int) -> Self:
        """
        An ADS request to read the name of a given EtherCAT device.

        :param device_id: the id of the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup(
                int(IndexGroup.ADSIGR_IODEVICE_STATE_BASE + device_id)
            ),
            index_offset=0x1,
            read_length=0xFF,
        )

    @classmethod
    def read_device_netid(cls, device_id: int) -> Self:
        """
        An ADS request to read the ams netid of a given EtherCAT device.

        :param device_id: the id of the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup(
                int(IndexGroup.ADSIGR_IODEVICE_STATE_BASE + device_id)
            ),
            index_offset=0x5,
            read_length=6,
        )

    @classmethod
    def read_device_identity(cls, subindex: str) -> Self:
        """
        An ADS request to read the CANopen identity of a given EtherCAT device
        (this includes vendorId, productCode, revisionNumber and serialNumber).
        The value is accessed via a CAN-over-EtherCAT parameter (sdo).

        :returns: an AdsReadRequest message
        """
        index = "0x1018"
        return cls(
            index_group=IndexGroup.ADSIGRP_COE_LINK,
            index_offset=int(index + subindex, base=16),
            read_length=np.dtype(np.uint32).itemsize,
        )

    @classmethod
    def read_slave_count(cls) -> Self:
        """
        An ADS request to read the number of slave terminals configured on a device.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_COUNT_SLAVE,
            index_offset=0x0,
            read_length=np.dtype(np.uint16).itemsize,
        )

    @classmethod
    def read_slaves_addresses(cls, num_slaves: int) -> Self:
        """
        An ADS request to read the EtherCAT addresses of all configured slave terminals.

        :param num_slaves: the number of slave terminals on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_SLAVE_ADDRESSES,
            index_offset=0x0,
            read_length=(np.dtype(np.uint16).itemsize) * num_slaves,
        )

    @classmethod
    def read_slave_identity(cls, address: SupportsInt) -> Self:
        """
        An ADS request to read the CANopen identity of a configured slave terminal.
        (this includes vendorId, productCode, revisionNumber and serialNumber)

        :param address: the address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_SLAVE_IDENTITY,
            index_offset=np.uint32(address),
            read_length=(np.dtype(np.uint32).itemsize) * 4,
        )

    @classmethod
    def read_device_state(cls) -> Self:
        """
        An ADS request to read the state of an EtherCAT device (e.g. Master device).

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_STATEMACHINE,
            index_offset=0x0100,
            read_length=np.dtype(np.uint16).itemsize,
        )

    @classmethod
    def read_slaves_states(cls, num_slaves: SupportsInt) -> Self:
        """
        An ADS request to read the EtherCAT state and link status of all slave terminal.

        :param num_slaves: the number of slave terminals on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_STATEMACHINE,
            index_offset=0x0,
            read_length=(np.dtype(np.uint16).itemsize) * int(num_slaves),
        )

    @classmethod
    def read_slave_states(cls, address: SupportsInt) -> Self:
        """
        An ADS request to read the EtherCAT state and link status of \
            a single slave terminal.

        :param address: the address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_STATEMACHINE,
            index_offset=np.uint32(address),
            read_length=np.dtype(np.uint16).itemsize,
        )

    @classmethod
    def read_slaves_crc(cls, num_slaves: SupportsInt) -> Self:
        """
        An ADS request to read the counter values sum for the cyclic redundancy check \
            (CRC) of all slaves.
        CRC counters are incremented for the respective communication ports (A,B,C,D) \
            if an error has occurred (e.g. frames passing through the network which \
                are destroyed or damaged due to cable, contact or connector problems).

        :param num_slaves: the number of slave terminals on the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_CRC_COUNTERS,
            index_offset=0x0,
            read_length=(np.dtype(np.uint32).itemsize) * int(num_slaves),
        )

    @classmethod
    def read_slave_crc(cls, address: SupportsInt) -> Self:
        """
        An ADS request to read the counter values for the cyclic redundancy check \
            (CRC) of a single slave terminal.
        CRC counters are incremented for the respective communication ports (A,B,C,D) \
            if an error has occurred (e.g. frames passing through the network which \
                are destroyed or damaged due to cable, contact or connector problems).

        :param address: the address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_CRC_COUNTERS,
            index_offset=np.uint32(address),
            read_length=(np.dtype(np.uint32).itemsize) * 4,
        )

    @classmethod
    def read_device_frame_counters(cls) -> Self:
        """
        An ADS request to read the frame counters of an EtherCAT device.
        This includes cyclic and acyclic frames, both sent and lost.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_FRAME_COUNTERS,
            index_offset=0x0,
            read_length=(np.dtype(np.uint32).itemsize) * 5,
        )

    @classmethod
    def read_slave_type(cls, index: str) -> Self:
        """
        An ADS request to read the type of a slave terminal configured on a device.
        The value is accessed via a CAN-over-EtherCAT parameter (sdo).

        :param index: the index of the accessed CoE range as an hexadecimal string

        :returns: an AdsReadRequest message
        """
        subindex = "0002"
        return cls(
            index_group=IndexGroup.ADSIGRP_COE_LINK,
            index_offset=int(index + subindex, base=16),
            read_length=16,
        )

    @classmethod
    def read_slave_name(cls, index: str) -> Self:
        """
        An ADS request to read the name of a slave terminal configured on a device.
        The value is accessed via a CAN-over-EtherCAT parameter (sdo).

        :param index: the index of the accessed CoE range as an hexadecimal string

        :returns: an AdsReadRequest message
        """
        subindex = "0003"
        return cls(
            index_group=IndexGroup.ADSIGRP_COE_LINK,
            index_offset=int(index + subindex, base=16),
            read_length=32,
        )

    @classmethod
    def get_length_symbol_table(cls) -> Self:
        """
        An ADS request to get the length of the symbol table registered with the server.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SYM_UPLOADINFO2,
            index_offset=0,
            read_length=24,
        )

    @classmethod
    def fetch_symbol_table(cls, length: SupportsInt) -> Self:
        """
        ADS request to get a list of all symbols defined in the server's symbol table.

        :param length: the length of the symbol table data

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SYM_UPLOAD,
            index_offset=0,
            read_length=length,
        )

    @classmethod
    def read_symbol(
        cls, group: SupportsInt, offset: SupportsInt, length: SupportsInt
    ) -> Self:
        """
        An ADS request to get the value of a given ADS symbol.

        :param group: the index group of the ADS symbol to read the value from
        :param offset: the index offset of the ADS symbol to read the value from
        :param length: the length of the symbol data in bytes to read

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup(group),
            index_offset=offset,
            read_length=length,
        )

    @classmethod
    def read_coe_value(cls, index: str, subindex: str, datatype: Any) -> Self:
        """
        An ADS request to get the value of a CAN-over-EtherCAT parameter (sdo/pdo).

        :param index: the CoE index assigned to the parameter (HIWORD=0xYYYY0000)
        :param subindex: the CoE subindex assigned to the parameter (LOBYTE=0x000000YY)
        :param type: the parameter data type

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_COE_LINK,
            index_offset=int(index + subindex, base=16),
            read_length=np.dtype(datatype).itemsize,
        )


class AdsReadResponse(MessageResponse):
    """
    ADS Read data structure received in response to an ADS Read request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    result: ErrorCode
    """ADS error number"""
    length: UINT32
    """Length of the data supplied back from the ADS device"""
    data: bytes
    """Data supplied back from the ADS device"""


# ===================================================================
# ===== WRITE
# ===================================================================


class AdsWriteRequest(MessageRequest):
    """
    ADS Write packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115877899.html&id=8845698684103663373
    """

    index_group: IndexGroup
    """Index group of the data"""
    index_offset: UINT32
    """Index offset of the data"""
    write_length: UINT32
    """Length of the data in bytes which is written"""
    data: bytes
    """Data written to the ADS device"""

    @classmethod
    def reset_device_frame_counters(cls) -> Self:
        """
        An ADS request to reset the frame counters of an EtherCAT device to zero.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_FRAME_COUNTERS,
            index_offset=0x0,
            write_length=0x0,
            data=b"",
        )

    @classmethod
    def write_symbol(cls, group: SupportsInt, offset: SupportsInt, data: bytes) -> Self:
        """
        An ADS request to write a given value to an ADS symbol.

        :param group: the index group of the ADS symbol to write the value to
        :param offset: the index offset of the ADS symbol to write the value to
        :param data: the data in bytes to write

        :returns: an AdsWriteRequest message
        """
        return cls(
            index_group=IndexGroup(group),
            index_offset=offset,
            write_length=len(data),
            data=data,
        )

    @classmethod
    def write_coe_value(cls, index: str, subindex: str, data: bytes) -> Self:
        """
        An ADS request to write a given value to a CAN-over-EtherCAT parameter (sdo/pdo).

        :param index: the CoE index assigned to the parameter (HIWORD=0xYYYY0000)
        :param subindex: the CoE subindex assigned to the parameter (LOBYTE=0x000000YY)
        :param data: the data in bytes to write

        :returns: an AdsWriteRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_COE_LINK,
            index_offset=int(index + subindex, base=16),
            write_length=len(data),
            data=data,
        )


class AdsWriteResponse(MessageResponse):
    """
    ADS Write data structure received in response to an ADS Write request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115877899.html&id=8845698684103663373
    """

    result: ErrorCode
    """ADS error number"""


# ===================================================================
# ===== READ/WRITE
# ===================================================================


class AdsReadWriteRequest(MessageRequest):
    """
    ADS Read Write packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115884043.html&id=2085949217954035635
    """

    index_group: IndexGroup
    """Index group of the data"""
    index_offset: UINT32
    """Index offset of the data"""
    read_length: UINT32
    """Length of the data in bytes which is read"""
    write_length: UINT32
    """Length of the data in bytes which is written"""
    data: bytes
    """Data written to the ADS device"""

    @classmethod
    def get_handle_by_name(cls, name: str) -> Self:
        """
        An ADS request to get a unique handle associated with a given name.

        :params name: the ads symbol variable name

        :returns: an AdsReadWriteRequest message
        """
        data = name.encode(encoding=TWINCAT_STRING_ENCODING) + b"\x00"
        return cls(
            index_group=IndexGroup.ADSIGR_GET_SYMHANDLE_BYNAME,
            index_offset=0,
            read_length=np.dtype(np.uint32).itemsize,
            write_length=len(data),
            data=data,
        )

    @classmethod
    def readwrite_symbol(
        cls, group: SupportsInt, offset: SupportsInt, length: SupportsInt, data: bytes
    ) -> Self:
        """
        An ADS request to read the current value of a symbol \
            and write a new value to it as part of a single data frame.

        :param group: the index group of the ADS symbol to read from and write to
        :param offset: the index offset of the ADS symbol to read from and write to
        :param length: the length of the symbol data in bytes to read
        :param data: the data in bytes to write

        :returns: an AdsReadWriteRequest message
        """
        return cls(
            index_group=IndexGroup(group),
            index_offset=offset,
            read_length=length,
            write_length=len(data),
            data=data,
        )

    @classmethod
    def sumread_symbols(cls, reads: Sequence[AdsReadRequest]) -> Self:
        """
        Get the value of multiple variables which are not structured \
            within a linear memory.
        This function appears to be valid for ADS symbol variables, but not applicable \
            to CoE parameters (returns invalid index group error).

        :params reads: a list of AdsReadRequest sub-commands, \
            each one of them associated with one of the variables to read

        :returns: an AdsReadWriteRequest message
        """
        count = len(reads)
        assert count, (
            "Minimum one ADS ReadRequest is required to carry out an ADS SumRead call"
        )
        assert count < 500, (
            "A maximum of 500 sub-commands can be requested in an ADS SumRead call."
        )
        data = b""
        length = count * np.dtype(ErrorCode).itemsize
        for request in reads:
            data += request.to_bytes(include_data=False)
            length += request.read_length

        return cls(
            index_group=IndexGroup.ADSIGRP_SUMUP_READ,
            index_offset=count,
            read_length=length,
            write_length=len(data),
            data=data,
        )

    @classmethod
    def sumwrite_symbols(cls, writes: Sequence[AdsWriteRequest]) -> Self:
        """
        Set the value of multiple variables which are not structured \
            within a linear memory.
        This function appears to be valid for ADS symbol variables, but not applicable \
            to CoE parameters (returns invalid index group error).

        !Note that this service appears not to be supported by the CX2020 server \
            (error 0x0701 ADSERR_DEVICE_SRVNOTSUPP)!

        :params writes: a list of AdsWriteRequest sub-commands, each one of them \
            associated with one of the variables to write

        :returns: an AdsReadWriteRequest message
        """
        count = len(writes)
        assert count, (
            "Minimum one ADS WriteRequest is required to carry out an ADS SumWrite call"
        )
        assert count < 500, (
            "A maximum of 500 sub-commands can be requested in an ADS SumWrite call."
        )
        data = b""
        length = count * np.dtype(ErrorCode).itemsize
        for request in writes:
            data += request.to_bytes(include_data=False)
        for request in writes:
            data += request.data

        return cls(
            index_group=IndexGroup.ADSIGRP_SUMUP_WRITE,
            index_offset=count,
            read_length=length,
            write_length=len(data),
            data=data,
        )

    @classmethod
    def sumreadwrite_symbols(cls, readwrites: Sequence[Self]) -> Self:
        """
        Get and set the value of multiple variables which are not structured \
            within a linear memory.
        This function appears to be valid for ADS symbol variables, but not applicable \
            to CoE parameters (returns invalid index group error).

        !Note that this service appears not to be supported by the CX2020 server \
            (error 0x0701 ADSERR_DEVICE_SRVNOTSUPP)!

        :params readwrites: a list of AdsReadWriteRequest sub-commands, \
            each one of them associated with one of the variables to read then write

        :returns: an AdsReadWriteRequest message
        """
        count = len(readwrites)
        assert count, (
            "Minimum one ADS ReadWrite request is required to carry out \
                an ADS SumReadWrite call"
        )
        assert count < 500, (
            "A maximum of 500 sub-commands can be requested in \
                an ADS SumReadWrite call."
        )
        data = b""
        length = count * (np.dtype(ErrorCode).itemsize + np.dtype(np.uint32).itemsize)
        for cmd in readwrites:
            length += cmd.read_length
            data += cmd.to_bytes(include_data=False)
        for cmd in readwrites:
            data += cmd.data

        return cls(
            index_group=IndexGroup.ADSIGRP_SUMUP_READWRITE,
            index_offset=count,
            read_length=length,
            write_length=len(data),
            data=data,
        )


class AdsReadWriteResponse(MessageResponse):
    """
    ADS ReadWrite data structure received in response to an ADS ReadWrite request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115884043.html&id=2085949217954035635
    """

    result: ErrorCode
    """ADS error number"""
    length: UINT32
    """Length of the data supplied back from the ADS device"""
    data: bytes
    """Data supplied back from the ADS device"""


# ===================================================================
# ===== ADD DEVICE NOTIFICATION
# ===================================================================


class AdsAddDeviceNotificationRequest(MessageRequest):
    """
    ADS Add Device Notification packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115880971.html&id=7388557527878561663
    """

    index_group: IndexGroup
    """Index group of the data"""
    index_offset: UINT32
    """Index offset of the data"""
    length: UINT32
    """Length of data in bytes expected for this notification"""
    transmission_mode: TransmissionMode = TransmissionMode.ADSTRANS_SERVERONCHA
    """Chosen mode of device notification"""
    max_delay: UINT32
    """At the latest after this time, the ADS Device Notification is called; \
        the unit is 100ns"""
    cycle_time: UINT32
    """The ADS server checks if the value changes in this time slice; \
        the unit is 100ns"""
    reserved: BYTES16 = BYTES16(default=b"")
    """Reserved memory block,; must be set to 0"""


class AdsAddDeviceNotificationResponse(MessageResponse):
    """
    ADS AddDeviceNotification data structure received in response to an ADS \
        AddDeviceNotification request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115880971.html&id=7388557527878561663
    """

    result: ErrorCode
    """ADS error number"""
    handle: UINT32
    """Notification handle"""


# ===================================================================
# ===== DELETE DEVICE NOTIFICATION
# ===================================================================


class AdsDeleteDeviceNotificationRequest(MessageRequest):
    """
    ADS Delete Device Notification packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115881995.html&id=6216061301016726131
    """

    handle: UINT32
    """Notification handle; this handle is created by the AdsAddDeviceNotification \
        command"""


class AdsDeleteDeviceNotificationResponse(MessageResponse):
    """
    ADS DeleteDeviceNotification data structure received in response to an ADS \
        DeleteDeviceNotification request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115881995.html&id=6216061301016726131
    """

    result: ErrorCode
    """ADS error number"""


# ===================================================================
# ===== DEVICE NOTIFICATION
# ===================================================================


class AdsCombinedNotificationStream(Message):
    """
    Define a combined stream made from multiple notification streams.
    Such object is required for very high number of symbol notifications; \
        each ads notification stream can comprise around 4kbytes.
    """

    size: UINT16
    """Number of AdsNotificationStream elements"""
    data: bytes
    """Array of AdsNotificationStream elements"""

    def get_combined_notifications_dtype(
        self,
        device_name: str,
        symbols: dict[SupportsInt, Any],
    ) -> np.dtype:
        """
        Get the datatype structure used to interpret the bytes array from a \
            notification which comprises multiple streams

        :param device_name: the name of the device providing the notification
        :param symbols: a container object mapping the notification handle and related \
            symbol for all configured notifications

        :returns: a numpy array of datatypes characteristic of a whole ads notification
        """
        dtypes = []
        offset = 0
        stream_size = 0

        data = self.data
        for i in range(1, self.size + 1):
            stream_size = 4 + int.from_bytes(data[:4], byteorder="little", signed=False)
            notification = AdsNotificationStream.from_bytes(data[:stream_size])
            dtypes += [
                (f"_{device_name}.length{i}", np.uint32),
                (f"_{device_name}.stamps{i}", np.uint32),
            ]
            assert notification.stamps == 1, (
                f"Error: notification stream {i} comprises {notification.stamps} \
                    distinct timestamps."
            )
            stamp_header = AdsStampHeader.from_bytes(notification.data)
            dtypes += [
                (f"_{device_name}.timestamp{i}", np.uint64),
                (f"_{device_name}.samples{i}", np.uint32),
            ]
            notif_data = stamp_header.data

            for _ in range(int(stamp_header.samples)):
                assert notif_data, notif_data
                sample = AdsNotificationSample.from_bytes(notif_data)
                symbol = symbols[sample.handle]
                assert symbol.nbytes == sample.size
                dtypes += [
                    (f"_{symbol.name.replace(' ', '')}.handle", np.uint32),
                    (f"_{symbol.name.replace(' ', '')}.size", np.uint32),
                    (f"_{symbol.name.replace(' ', '')}.value", symbol.datatype),
                ]
                notif_data = notif_data[8 + sample.size :]

            assert notif_data == b"", (
                f"Error: unprocessed data in the notification stream {i}: {notif_data}"
            )
            offset += stream_size
            data = self.data[offset:]

        assert data == b"", (
            f"Error: unprocessed data in the combined notification stream: {data}"
        )

        return np.dtype(dtypes)


class AdsNotificationStream(Message):
    """
    ADS DeviceNotification packet
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115883019.html&id=3360461216738457777
    """

    length: UINT32
    """Size of 'stamps+data' in bytes"""
    stamps: UINT32
    """Number of AdsStampHeader elements"""
    data: bytes
    """Array with AdsStampHeader elements"""

    def get_notification_dtype(
        self, device_name: str, symbols: dict[SupportsInt, Any]
    ) -> np.dtype:
        """
        Get the datatype structure used to interpret the bytes array from a single \
            notification packet (note that the notification packet is assumed to \
                comprise a single stamp header).

        :param device_name: the name of the device providing the notification
        :param symbols: a container object mapping the notification handle and related \
            symbol for all configured notifications

        :returns: a numpy array of datatypes characteristic of the active device \
            notification structure
        """
        dtypes = [
            (f"_{device_name}.length", np.uint32),
            (f"_{device_name}.stamps", np.uint32),
        ]
        assert self.stamps == 1, (
            f"Error: notification comprises {self.stamps} distinct timestamps."
        )
        stamp_header = AdsStampHeader.from_bytes(self.data)
        dtypes += [
            (f"_{device_name}.timestamp", np.uint64),
            (f"_{device_name}.samples", np.uint32),
        ]
        data = stamp_header.data
        for _ in range(int(stamp_header.samples)):
            assert data, data
            sample = AdsNotificationSample.from_bytes(data)
            symbol = symbols[sample.handle]
            assert symbol.nbytes == sample.size
            dtypes += [
                (f"_{symbol.name.replace(' ', '')}.handle", np.uint32),
                (f"_{symbol.name.replace(' ', '')}.size", np.uint32),
                (f"_{symbol.name.replace(' ', '')}.value", symbol.datatype),
            ]
            data = data[8 + sample.size :]
        assert data == b"", (
            f"Error: unprocessed data in the notification stream: {data}"
        )
        return np.dtype(dtypes)


class AdsStampHeader(Message):
    timestamp: UINT64
    """UTC time stamp corresponding to the notification packet \
        (100ns intervals since 01.01.1601)"""
    samples: UINT32
    """Number of AdsNotificationSample elements"""
    data: bytes
    """Array with AdsNotificationSample elements"""


class AdsNotificationSample(Message):
    handle: UINT32
    """Notification handle"""
    size: UINT32
    """Size of the data in bytes"""
    data: bytes
    """Data"""


# ===================================================================
# ===== MESSAGE MAPPING
# ===================================================================

# Dictionary of all available ADS messages.
MESSAGE_CLASS: dict[type[MessageRequest], type[MessageResponse]] = {
    AdsAddDeviceNotificationRequest: AdsAddDeviceNotificationResponse,
    AdsDeleteDeviceNotificationRequest: AdsDeleteDeviceNotificationResponse,
    AdsReadDeviceInfoRequest: AdsReadDeviceInfoResponse,
    AdsReadStateRequest: AdsReadStateResponse,
    AdsReadRequest: AdsReadResponse,
    AdsReadWriteRequest: AdsReadWriteResponse,
    AdsWriteRequest: AdsWriteResponse,
}

# Dictionary of all available ADS requests and associated commands.
REQUEST_CLASS: dict[type[MessageRequest], CommandId] = {
    AdsAddDeviceNotificationRequest: CommandId.ADSSRVID_ADDDEVICENOTE,
    AdsDeleteDeviceNotificationRequest: CommandId.ADSSRVID_DELETEDEVICENOTE,
    AdsReadDeviceInfoRequest: CommandId.ADSSRVID_READDEVICEINFO,
    AdsReadStateRequest: CommandId.ADSSRVID_READSTATE,
    AdsReadRequest: CommandId.ADSSRVID_READ,
    AdsReadWriteRequest: CommandId.ADSSRVID_READWRITE,
    AdsWriteRequest: CommandId.ADSSRVID_WRITE,
}

# Dictionary of all available ADS commands and associated responses.
RESPONSE_CLASS: dict[CommandId, type[MessageResponse]] = {
    CommandId.ADSSRVID_ADDDEVICENOTE: AdsAddDeviceNotificationResponse,
    CommandId.ADSSRVID_DELETEDEVICENOTE: AdsDeleteDeviceNotificationResponse,
    CommandId.ADSSRVID_READDEVICEINFO: AdsReadDeviceInfoResponse,
    CommandId.ADSSRVID_READSTATE: AdsReadStateResponse,
    CommandId.ADSSRVID_READ: AdsReadResponse,
    CommandId.ADSSRVID_READWRITE: AdsReadWriteResponse,
    CommandId.ADSSRVID_WRITE: AdsWriteResponse,
}
