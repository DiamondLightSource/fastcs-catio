from collections.abc import Iterator, Sequence
from functools import cached_property

import numpy as np
from typing_extensions import Any, Self, dataclass_transform, get_type_hints

from ._constants import CommandId, ErrorCode, IndexGroup, StateFlag
from ._types import BYTES16, NETID, UDINT, UINT, USINT


def _get_field_values(
    cls, fields: Sequence[str], kwargs: dict[str, Any]
) -> Iterator[Any]:
    """
    :params cls: the Message object type to extract values from
    :params fields: the names of the various fields which characterize this Message object
    :param kwargs: map of available fields and their associated values which define this Message object

    :raises KeyError: exception arising when a required field was expected but not found in the Message data structure
    """
    for field in fields:
        # Try first from kwargs
        value = kwargs.get(field, None)
        if value is None:
            # If not get it from class defaults
            value = cls.__dict__.get(field, None)
        if value is None:
            # It was required but not passed
            raise KeyError(f"{field} is a required argument")
        yield value


@dataclass_transform(kw_only_default=True)
class Message:
    """
    Define a generic ADS message type which the various ADS message structures conform to.

    Instance attributes:
        _value: numpy NDArray based on the specific structure of the ADS message type

    :raises TypeError: exception arising when trying to instantiate a Message object with both buffer and kwargs.
    """

    data: bytes
    """Array of bytes representing the value of the data associated with the ADS message"""

    def __init__(self, buffer: bytes = b"", *, data: bytes = b"", **kwargs):
        if buffer and kwargs:
            raise TypeError(
                "Can't have a Message class instantiated with both buffer and kwargs."
            )
        elif buffer:
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

    @cached_property
    def dtype(
        self,
    ) -> np.dtype:
        """
        Get the type of the Message object as a numpy data type.
        It includes all the fields specific to that Message, except for the 'data' field.
        Its value is computed once and then cached as a normal attribute for the life of the instance.

        :returns: the ADS message data type
        """
        hints = get_type_hints(type(self))
        hints.pop("data")
        return np.dtype(list(hints.items()))

    @classmethod
    def from_bytes(cls, buffer: bytes) -> Self:
        """
        Create a Message object whose value is a numpy NDArray defined from the given array of bytes.

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

    target_net_id: NETID
    """The AMS netid of the station for which the packet is intended"""
    target_port: UINT
    """The AMS port of the station for which the packet is intended"""
    source_net_id: NETID
    """The AMS netid of the station from which the packet is sent"""
    source_port: UINT
    """The AMS port of the station from which the packet is sent"""
    command_id: CommandId
    """ADS command id"""
    state_flags: StateFlag
    """Defines the protocol (bit7: TCP/UDP), interface (bit3: ADS) and message type (bit1: request/response)"""
    length: UDINT
    """Length of the data in bytes attached to this header"""
    error_code: ErrorCode
    """ADS error number"""
    invoke_id: UDINT
    """Id used to map a received response to a sent request"""


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
    ADS Read Device Info data structure received in response to an ADS Read Device Info request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    result: ErrorCode
    """ADS error number"""
    major_version: USINT
    """Major version number of the ADS device"""
    minor_version: USINT
    """Minor version number of the ADS device"""
    version_build: UINT
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
    ads_state: UINT
    """ADS status"""
    device_state: UINT
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
    index_offset: UDINT
    """Index offset of the data"""
    read_length: UDINT
    """Length of the data in bytes which is read"""

    @classmethod
    def test_read(cls) -> Self:
        return cls(
            index_group=IndexGroup.TEST_IGRP,
            index_offset=0x0000,
            read_length=np.dtype(UINT).itemsize,
        )

    @classmethod
    def read_device_count(cls) -> Self:
        """
        An ADS request to read the number of devices registered with the I/O server.

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGR_IODEVICE_STATE_BASE,
            index_offset=0x2,
            read_length=np.dtype(UDINT).itemsize,
        )

    @classmethod
    def read_device_ids(cls, device_count: int) -> Self:
        """
        An ADS request to read the id of the devices registered with the I/O server.
        (Note: the first index will represent the device count; device ids will follow)

        :param device_count: the number of registered EtherCAT devices

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGR_IODEVICE_STATE_BASE,
            index_offset=0x1,
            read_length=(int(device_count) + 1) * np.dtype(UINT).itemsize,
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
            read_length=np.dtype(UINT).itemsize,
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
            read_length=np.dtype(NETID).itemsize,
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
            read_length=np.dtype(UDINT).itemsize,
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
            read_length=np.dtype(UINT).itemsize,
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
            read_length=(np.dtype(UINT).itemsize) * num_slaves,
        )

    @classmethod
    def read_slave_identity(cls, address: UINT) -> Self:
        """
        An ADS request to read the CANopen identity of a configured slave terminal.
        (this includes vendorId, productCode, revisionNumber and serialNumber)

        :param address: the EtherCAT address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_MASTER_SLAVE_IDENTITY,
            index_offset=np.uint32(address),
            read_length=(np.dtype(UDINT).itemsize) * 4,
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
            read_length=np.dtype(UINT).itemsize,
        )

    @classmethod
    def read_slaves_states(cls, num_slaves: int) -> Self:
        """
        An ADS request to read the EtherCAT state and link status of all slave terminal.

        :param num_slaves: the number of slave terminals on the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_STATEMACHINE,
            index_offset=0x0,
            read_length=(np.dtype(UINT).itemsize) * num_slaves,
        )

    @classmethod
    def read_slave_states(cls, address: UINT) -> Self:
        """
        An ADS request to read the EtherCAT state and link status of a single slave terminal.

        :param address: the EtherCAT address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_STATEMACHINE,
            index_offset=np.uint32(address),
            read_length=np.dtype(UINT).itemsize,
        )

    @classmethod
    def read_slaves_crc(cls, num_slaves: int) -> Self:
        """
        An ADS request to read the counter values sum for the cyclic redundancy check (CRC) of all slaves.
        CRC counters are incremented for the respective communication ports (A,B,C,D) if an error has occurred
        (e.g. frames passing through the network which are destroyed or damaged due to cable, contact or connector problems).

        :param num_slaves: the number of slave terminals on the device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_CRC_COUNTERS,
            index_offset=0x0,
            read_length=(np.dtype(UDINT).itemsize) * num_slaves,
        )

    @classmethod
    def read_slave_crc(cls, address: UINT) -> Self:
        """
        An ADS request to read the counter values for the cyclic redundancy check (CRC) of a single slave terminal.
        CRC counters are incremented for the respective communication ports (A,B,C,D) if an error has occurred
        (e.g. frames passing through the network which are destroyed or damaged due to cable, contact or connector problems).

        :param address: the EtherCAT address of the slave terminal on the EtherCAT device

        :returns: an AdsReadRequest message
        """
        return cls(
            index_group=IndexGroup.ADSIGRP_SLAVE_CRC_COUNTERS,
            index_offset=np.uint32(address),
            read_length=(np.dtype(UDINT).itemsize) * 4,
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
            read_length=(np.dtype(UDINT).itemsize) * 5,
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


class AdsReadResponse(MessageResponse):
    """
    ADS Read data structure received in response to an ADS Read request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115876875.html&id=4960931295000833536
    """

    result: ErrorCode
    """ADS error number"""
    length: UDINT
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
    index_offset: UDINT
    """Index offset of the data"""
    write_length: UDINT
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


class AdsWriteResponse(MessageResponse):
    """
    ADS Write data structure received in response to an ADS Write request.
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115877899.html&id=8845698684103663373
    """

    result: ErrorCode
    """ADS error number"""


# ===================================================================
# ===== MESSAGE MAPPING
# ===================================================================

# Dictionary of all available ADS messages.
MESSAGE_CLASS: dict[type[MessageRequest], type[MessageResponse]] = {
    AdsReadDeviceInfoRequest: AdsReadDeviceInfoResponse,
    AdsReadStateRequest: AdsReadStateResponse,
    AdsReadRequest: AdsReadResponse,
    AdsWriteRequest: AdsWriteResponse,
}

# Dictionary of all available ADS requests and associated commands.
REQUEST_CLASS: dict[type[MessageRequest], CommandId] = {
    AdsReadDeviceInfoRequest: CommandId.ADSSRVID_READDEVICEINFO,
    AdsReadStateRequest: CommandId.ADSSRVID_READSTATE,
    AdsReadRequest: CommandId.ADSSRVID_READ,
    AdsWriteRequest: CommandId.ADSSRVID_WRITE,
}

# Dictionary of all available ADS commands and associated responses.
RESPONSE_CLASS: dict[CommandId, type[MessageResponse]] = {
    CommandId.ADSSRVID_READDEVICEINFO: AdsReadDeviceInfoResponse,
    CommandId.ADSSRVID_READSTATE: AdsReadStateResponse,
    CommandId.ADSSRVID_READ: AdsReadResponse,
    CommandId.ADSSRVID_WRITE: AdsWriteResponse,
}
