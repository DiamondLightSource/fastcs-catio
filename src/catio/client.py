"""
ADS communication protocol
https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html&id=6446904803799887467
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import SupportsInt, TypeVar, overload

import numpy as np
import numpy.typing as npt

from ._constants import (
    AdsState,
    CoEIndex,
    CommandId,
    DeviceStateMachine,
    DeviceType,
    ErrorCode,
    IndexGroup,
    SlaveLinkState,
    SlaveStateMachine,
    StateFlag,
    TransmissionMode,
)
from ._types import AmsNetId
from .devices import (
    AdsSymbol,
    AdsSymbolNode,
    ChainLocation,
    DeviceFrames,
    IODevice,
    IOIdentity,
    IOServer,
    IOSlave,
    SlaveState,
)
from .messages import (
    MESSAGE_CLASS,
    REQUEST_CLASS,
    RESPONSE_CLASS,
    AdsAddDeviceNotificationRequest,
    AdsAddDeviceNotificationResponse,
    AdsCombinedNotificationStream,
    AdsDeleteDeviceNotificationRequest,
    AdsDeleteDeviceNotificationResponse,
    AdsNotificationStream,
    AdsReadDeviceInfoRequest,
    AdsReadDeviceInfoResponse,
    AdsReadRequest,
    AdsReadResponse,
    AdsReadStateRequest,
    AdsReadStateResponse,
    AdsReadWriteRequest,
    AdsReadWriteResponse,
    AdsSymbolTableEntry,
    AdsSymbolTableInfo,
    AdsWriteRequest,
    AdsWriteResponse,
    AmsHeader,
    Message,
    MessageRequest,
    MessageResponse,
    SlaveCRC,
)
from .symbols import symbol_lookup
from .utils import (
    bytes_to_string,
    get_local_netid_str,
)

# https://infosys.beckhoff.com/content/1033/ipc_security_win7/11019143435.html
ADS_TCP_PORT = 48898
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcsystemmanager/1089026187.html&id=754756950722060432
ADS_MASTER_PORT = 65535
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_system/31084171.html&id=
IO_SERVER_PORT = 300


MessageT = TypeVar("MessageT", bound=Message)


class ResponseEvent:
    """
    Define an event object which wait asynchronously for an ADS response to be received.

    Instance attributes:
        __event: an asynchronous event object whose flag can be set or cleared
        __value: a Message object associated with the received response
    """

    def __init__(self):
        self.__event = asyncio.Event()
        self.__value: Message | None = None

    def set(self, response: Message) -> None:
        """
        Save the response message and trigger the event flag.

        :param response: the ADS message comprised in the response
        """
        self.__value = response
        self.__event.set()

    async def get(self, cls: type[MessageT]) -> MessageT:
        """
        Asynchronously wait for the response event to be set, then check the response
        message type is as expected.

        :param cls: type of ADS message associated with this response event

        :returns: the received ADS message
        """
        await self.__event.wait()
        assert self.__value and isinstance(self.__value, cls), (
            f"Expected {cls}, got {self.__value}"
        )
        return self.__value


class AsyncioADSClient:
    """
    Define an ADS client which connects to a given ADS server.
    Communication services comprise explicit ADS requests to the server \
        and continuous monitoring of ADS responses.
    ADS communication protocol follows a clear message packet format.

    Instance attributes:
        __local_ams_net_id: \
            container object comprising the localhost netid bytes
        __local_ams_port: \
            int object defining the local port used for the ADS communication transport
        __target_ams_net_id: container object comprising the ADS server netid bytes
        __target_ams_port: int object defining the ADS server port \
            which ADS communication is routed to/from
        __target_coe_net_id: \
            container object comprising the EtherCAT Master Device netid bytes
        __reader: reader object used to read data asynchronously from the IO stream
        __writer: writer object used to write data asynchronously to the IO stream
        __current_invoke_id: \
            id assigned to a message request and used to map the received responses
        __response_events: \
            dictionary which associates a received response to a unique request id
        __variable_handles: \
            dictionary which associates a distinct handle value to a symbol name
        __device_notification_handles: \
            container object which associate a distinct handle value to \
                a notification variable
        __notif_templates: array of bytes corresponding to the first received \
            notification and used as a datastructure template for the following \
                notifications
        __buffer: array of bytes where device notifications are appended
        __buffer_cache: array of bytes used to save the partial notification data \
            which is received when multiple notification streams are required
        __notification_queue: asyncio queue where arrays of notifications are posted \
            onto and consumed from
        __receive_task: asynchronous task which continuously monitors the reception of \
            new ADS messages
        _ecdevices: dictionary comprising all EtherCAT devices registered on \
            the IO server
        _ecsymbols: dictionary comprising all ADS symbols configured on \
            the EtherCAT devices
    """

    def __init__(
        self,
        target_ams_net_id: str,
        target_ams_port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.__local_ams_net_id = AmsNetId.from_string(get_local_netid_str())
        self.__local_ams_port = 8000
        self.__target_ams_net_id = AmsNetId.from_string(target_ams_net_id)
        self.__target_ams_port = target_ams_port
        self.__reader = reader
        self.__writer = writer
        self.__current_invoke_id = np.uint32(0)
        self.__response_events: dict[SupportsInt, ResponseEvent] = {}
        self.__variable_handles: dict[
            str, int
        ] = {}  # key is variable name, value is notification handle
        self.__device_notification_handles: dict[
            SupportsInt, AdsSymbol
        ] = {}  # key is device id, value is dictionary of 'notification_handle: symbol'
        self.__notif_templates: dict[
            int, bytes
        ] = {}  # key is notification stream index, value is notification data
        self.__buffer: bytearray | None = None
        self.__bfr_cache = bytearray()
        self.__notification_queue = asyncio.Queue()
        self.__receive_task = asyncio.create_task(self._recv_forever())

        self._ecdevices: dict[
            SupportsInt, IODevice
        ] = {}  # key is device id, value is IODevice object
        self._ecsymbols: dict[
            SupportsInt, Sequence[AdsSymbol]
        ] = {}  # key is device id, value is list of AdsSymbol objects

    #################################################################
    ### CLIENT CONNECTION -------------------------------------------
    #################################################################

    @classmethod
    async def connected_to(
        cls,
        target_ip: str,
        target_ams_net_id: str,
        target_ams_port: int,
        ads_port: int = ADS_TCP_PORT,
    ) -> AsyncioADSClient:
        """
        Create an asynchronous ADS client connection to a given ADS server.

        :param target_ip: IP of the ADS server
        :param target_ams_net_id: netid of the ADS server
        :param target_ams_port: ADS port for the I/O device available on the ADS server
        :param ads_port: unencrypted ADS port for TCP connections

        :returns: an asynchronous ADS client connection
        """
        reader, writer = await asyncio.open_connection(target_ip, ads_port)
        logging.info(
            f"Opened client communication with ADS server at {time.strftime('%X')}"
        )
        return cls(
            target_ams_net_id,
            target_ams_port,
            reader,
            writer,
        )

    async def close(
        self,
    ) -> None:
        """
        Close the established ADS client connection.
        """
        self.__receive_task.cancel()
        self.__writer.close()
        await self.__writer.wait_closed()
        logging.info(
            f"Closed client communication with ADS server at {time.strftime('%X')}"
        )

    #################################################################
    ### ADS COMMUNICATION -------------------------------------------
    #################################################################

    async def _send_ams_message(
        self, command: CommandId, message: Message, **kwargs: AmsNetId | int
    ) -> ResponseEvent:
        """
        Send an AMS message to the ADS server; the data packet comprises an AMS header
        and the ADS command data.

        :param command: the type of command message sent to the server
        :param message: the ADS message request
        :param kwargs: optional keyword parameters
            (for example to specify different target netid and port)

        :returns: a ResponseEvent object associated with this message
        """
        ams_netid = kwargs.get("netid", self.__target_ams_net_id)
        ams_port = kwargs.get("port", self.__target_ams_port)
        assert isinstance(ams_netid, AmsNetId) and isinstance(ams_port, int)

        self.__current_invoke_id += 1
        payload = message.to_bytes()
        ams_header = AmsHeader(
            target_net_id=ams_netid.to_bytes6(),
            target_port=ams_port,
            source_net_id=self.__local_ams_net_id.to_bytes6(),
            source_port=self.__local_ams_port,
            command_id=command,
            state_flags=StateFlag.AMSCMDSF_ADSCMD,
            length=len(payload),
            error_code=ErrorCode.ERR_NOERROR,
            invoke_id=self.__current_invoke_id,
        )
        header_raw = ams_header.to_bytes()
        total_length = len(header_raw) + len(payload)
        length_bytes = total_length.to_bytes(4, byteorder="little", signed=False)
        self.__writer.write(b"\x00\x00" + length_bytes + header_raw + payload)
        # logging.debug(
        #     "Sending AMS packet: '\x00\x00', "
        #     + f"{length_bytes.hex(' ')}, {header_raw.hex(' ')}, {payload.hex(' ')}"
        # )
        await self.__writer.drain()
        response_ev = ResponseEvent()
        self.__response_events[self.__current_invoke_id] = response_ev
        return response_ev

    async def _recv_ams_message(
        self,
    ) -> tuple[AmsHeader, bytes]:
        """
        Receive an ADS message from the ADS server.
        The message format includes an AMS/TCP Header, an AMS Header and ADS Data:
        https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115883019.html#115972107&id=

        :returns: the AMS Header and ADS data as a tuple

        :raises TimeoutError: following a lack of ADS communication
        :raises ConnectionError: when the ADS client has disconnected form the server
        :raises ConnectionAbortedError: when the ADS client connection has completed
        """
        COMMUNICATION_TIMEOUT_SEC = 120
        try:
            async with asyncio.timeout(COMMUNICATION_TIMEOUT_SEC):
                msg_bytes = await self.__reader.readexactly(6)
                assert msg_bytes[:2] == b"\x00\x00", (
                    f"Received an invalid TCP header: {msg_bytes.hex()}"
                )
                length = int.from_bytes(
                    msg_bytes[-4:], byteorder="little", signed=False
                )
                packet = await self.__reader.readexactly(length)
                # logging.debug(f"Received packet is: {packet.hex(' ')}")
                AMS_HEADER_LENGTH = 32
                header = AmsHeader.from_bytes(packet[:AMS_HEADER_LENGTH])
                body = packet[AMS_HEADER_LENGTH:]
                return header, body
        except asyncio.TimeoutError as err:
            err.add_note(
                f"Empty packet after {COMMUNICATION_TIMEOUT_SEC} seconds, "
                + "system likely disconnected."
            )
            raise
        except asyncio.IncompleteReadError as err:
            raise ConnectionError("Remote connection to the device has ended") from err
        except asyncio.CancelledError as err:
            raise ConnectionAbortedError(
                "Asynchronous monitoring of ADS messages has completed."
            ) from err

    async def _handle_notification(self, header: AmsHeader, body: bytes) -> None:
        """
        Read the notification message and build the whole message structure.
        Depending on the number of subscribed symbol variables,
        the notification message may comprise more than one frame.

        :params header: the notificatin message header
        :params body: the notification message data
        """
        if self.__buffer is not None:
            # Check which notification frame is being handled.
            id = int(header.invoke_id)

            # Add a template to the data structure
            # which defines a whole notification message.
            if id not in self.__notif_templates:
                self.__notif_templates[id] = body
                self.__num_notif_streams += 1
            assert len(body) == len(self.__notif_templates[id]), (
                "ERROR: size mismatch in the notification streams."
            )

            # A complete notification message is made from multiple successive streams
            # sent from the ADS server.
            if 1 in self.__notif_templates:
                self.__bfr_cache += body

                if id + 1 < self.__num_notif_streams:
                    return
                else:
                    self.__buffer += self.__bfr_cache
                    self.__bfr_cache.clear()
                    return

            # A complete notification message is defined by a single stream
            # sent from the ADS server (so far).
            self.__buffer += body

    async def _recv_forever(self) -> None:
        """
        Receive ADS messages asynchronously until the client connection has ended.
        ADS messages are matched to their associated response type,
        then saved to the event queue.
        """
        while True:
            try:
                header, body = await self._recv_ams_message()
                assert header.error_code == ErrorCode.ERR_NOERROR, ErrorCode(
                    header.error_code
                )

                if header.command_id == CommandId.ADSSRVID_DEVICENOTE:
                    await self._handle_notification(header, body)
                else:
                    # assert CommandId(header.command_id) in RESPONSE_CLASS, (
                    #     f"ADS Command with id {header.command_id} is not implemented."
                    # )
                    cls = RESPONSE_CLASS[CommandId(header.command_id)]
                    response = cls.from_bytes(body)
                    self.__response_events[header.invoke_id].set(response)

            except ConnectionAbortedError as err:
                logging.warning(err)
                break
            except ConnectionError as err:
                logging.error(err)
                break

    @overload
    async def _ads_read(
        self, request: AdsReadDeviceInfoRequest, **kwargs: AmsNetId | int
    ) -> AdsReadDeviceInfoResponse: ...

    @overload
    async def _ads_read(
        self, request: AdsReadStateRequest, **kwargs: AmsNetId | int
    ) -> AdsReadStateResponse: ...

    @overload
    async def _ads_read(
        self, request: AdsReadRequest, **kwargs: AmsNetId | int
    ) -> AdsReadResponse: ...

    async def _ads_read(
        self,
        request: MessageRequest,
        **kwargs: AmsNetId | int,
    ) -> MessageResponse:
        """
        Send an ADS Read request to the server and return the ADS response.

        :param request: the ADS message request to send
        :param kwargs: optional keyword parameters
            (for example netid/port to address a different server)

        :returns: the ADS message response
        """
        response_event = await self._send_ams_message(
            REQUEST_CLASS[type(request)], request, **kwargs
        )
        cls = MESSAGE_CLASS[type(request)]
        response = await response_event.get(cls)
        assert response.result == ErrorCode.ERR_NOERROR, (
            f"ERROR {ErrorCode(response.result)}"
        )
        return response

    #################################################################
    ### I/O INTROSPECTION -------------------------------------------
    #################################################################

    async def _get_device_count(
        self,
    ) -> int:
        """
        Get the number of EtherCAT devices available on the I/O server.

        :returns: the number of EtherCAT devices
        """
        response = await self._ads_read(
            AdsReadRequest.read_device_count(), port=IO_SERVER_PORT
        )

        return int.from_bytes(bytes=response.data, byteorder="little", signed=False)

    async def _read_io_info(
        self,
    ) -> IOServer:
        """
        Read the name and the version number of the TwinCAT ADS IO.

        :returns: an instance of an IOServer object
        """
        info_response = await self._ads_read(
            AdsReadDeviceInfoRequest(), port=IO_SERVER_PORT
        )

        return IOServer(
            name=bytes_to_string(info_response.device_name.tobytes()),
            version="-".join(
                [str(info_response.major_version), str(info_response.minor_version)]
            ),
            build=info_response.version_build,
            num_devices=await self._get_device_count(),
        )

    async def _get_device_ids(
        self,
        dev_count: SupportsInt,
    ) -> Sequence[int]:
        """
        Get the id of each EtherCAT device registered with the I/O server.

        :param dev_count: the number of available devices

        :returns: a list of device ids
        """
        response = await self._ads_read(
            AdsReadRequest.read_device_ids(dev_count), port=IO_SERVER_PORT
        )

        # The first two bytes of the response represent the device count.
        device_count = int.from_bytes(
            bytes=response.data[:2], byteorder="little", signed=False
        )
        assert device_count == dev_count

        # Then device IDs follow.
        ids: Sequence[int] = []
        data = response.data[2:]
        for _ in range(int(dev_count)):
            ids.append(int.from_bytes(bytes=data[:2], byteorder="little", signed=False))
            data = data[2:]

        return ids

    async def _get_device_types(
        self,
        dev_ids: Sequence[int],
    ) -> Sequence[DeviceType]:
        """
        Get the type of each EtherCAT device registered with the I/O server.

        :param dev_ids: the list of available device ids

        :returns: a list of device types
        """
        types: Sequence[DeviceType] = []
        for id in dev_ids:
            response = await self._ads_read(
                AdsReadRequest.read_device_type(id), port=IO_SERVER_PORT
            )
            types.append(
                DeviceType(
                    int.from_bytes(
                        bytes=response.data, byteorder="little", signed=False
                    )
                )
            )

        return types

    async def _get_device_names(
        self,
        dev_ids: Sequence[int],
    ) -> Sequence[str]:
        """
        Get the name of each EtherCAT device registered with the I/O server.

        :param dev_ids: the list of available device ids

        :returns: a list of device names
        """
        names: Sequence[str] = []
        for id in dev_ids:
            response = await self._ads_read(
                AdsReadRequest.read_device_name(id), port=IO_SERVER_PORT
            )
            names.append(bytes_to_string(response.data))

        return names

    async def _get_device_netids(
        self,
        dev_ids: Sequence[int],
    ) -> Sequence[AmsNetId]:
        """
        Get the AmsNetid address of each EtherCAT device registered with the I/O server.

        :param dev_ids: the list of available device ids

        :returns: a list of netid address strings
        """
        netids: Sequence[AmsNetId] = []
        for id in dev_ids:
            response = await self._ads_read(
                AdsReadRequest.read_device_netid(id), port=IO_SERVER_PORT
            )
            netids.append(AmsNetId.from_bytes(response.data))

        return netids

    async def _get_device_identities(
        self,
        dev_netids: Sequence[AmsNetId],
    ) -> Sequence[IOIdentity]:
        """
        Get the CANopen identity of each EtherCAT device registered with the I/O server.

        :param dev_netids: a list comprising the netid string of all registered devices

        :returns: a list of slave identities
        """
        subindexes = ["0001", "0002", "0003", "0004"]
        identities: Sequence[IOIdentity] = []
        for netid in dev_netids:
            data = bytearray()
            for subindex in subindexes:
                response = await self._ads_read(
                    AdsReadRequest.read_device_identity(subindex),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                data.extend(response.data)
            identities.append(IOIdentity.from_bytes(bytes(data)))

        return identities

    async def _get_device_frame_counters(
        self,
        dev_netids: Sequence[AmsNetId],
    ) -> Sequence[DeviceFrames]:
        """
        Get the frame counters of each EtherCAT device registered with the I/O server.

        :param dev_netids: a list comprising the netid string of all registered devices

        :returns: a list of device frame counters
        """
        frame_counters: Sequence[DeviceFrames] = []
        for netid in dev_netids:
            response = await self._ads_read(
                AdsReadRequest.read_device_frame_counters(),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            frame_counters.append(DeviceFrames.from_bytes(response.data))

        return frame_counters

    async def _get_slave_count(
        self,
        dev_netids: Sequence[AmsNetId],
    ) -> Sequence[int]:
        """
        Get the number of configured slave terminals for each available EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices

        :returns: a list of slave counts
        """
        slave_counts: Sequence[int] = []
        for netid in dev_netids:
            response = await self._ads_read(
                AdsReadRequest.read_slave_count(),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            slave_counts.append(
                int.from_bytes(bytes=response.data, byteorder="little", signed=False)
            )

        return slave_counts

    async def _get_slave_crc_counters(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_counts: Sequence[int],
    ) -> Sequence[Sequence[np.uint32]]:
        """
        Get the error counter values for the cyclic redundancy check of all slave
        terminals for each available EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_counts: a list comprising the number of slaves on all devices

        :returns: a list of list of slave crc counters for each EtherCAT device
        """
        slave_crc_counters: Sequence[Sequence[np.uint32]] = []
        for netid, slave_count in zip(dev_netids, dev_slave_counts, strict=True):
            response = await self._ads_read(
                AdsReadRequest.read_slaves_crc(slave_count),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            slaves_crc = np.frombuffer(
                response.data,
                dtype=np.uint32,
                count=slave_count,
            )
            slave_crc_counters.append(slaves_crc.tolist())

        return slave_crc_counters

    async def _get_slave_addresses(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_counts: Sequence[int],
    ) -> Sequence[Sequence[np.uint16]]:
        """
        Get the fixed address of all slave terminals for each available EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_counts: a list comprising the number of slaves on all devices

        :returns: a list comprising a list of slave addresses for each EtherCAT device
        """
        assert len(dev_netids) == len(dev_slave_counts)

        slave_addresses: Sequence[Sequence[np.uint16]] = []
        for netid, slave_count in zip(dev_netids, dev_slave_counts, strict=True):
            response = await self._ads_read(
                AdsReadRequest.read_slaves_addresses(slave_count),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            addresses = np.frombuffer(
                response.data,
                dtype=np.uint16,
                count=slave_count,
            )
            slave_addresses.append(addresses.tolist())

        return slave_addresses

    async def _get_slave_identities(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_addresses: Sequence[Sequence[np.uint16]],
    ) -> Sequence[Sequence[IOIdentity]]:
        """
        Get the CANopen identity of all slave terminals for each EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_addresses: a list comprising the EtherCAT addresses
            of the slaves on all devices

        :returns: a list comprising a list of slave identities for each EtherCAT device
        """
        slave_identities: Sequence[Sequence[IOIdentity]] = []
        for netid, slave_addresses in zip(dev_netids, dev_slave_addresses, strict=True):
            identities: Sequence[IOIdentity] = []
            for address in slave_addresses:
                response = await self._ads_read(
                    AdsReadRequest.read_slave_identity(address),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                identities.append(IOIdentity.from_bytes(response.data))
            slave_identities.append(identities)

        return slave_identities

    async def _get_slave_types(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_counts: Sequence[int],
    ) -> Sequence[Sequence[str]]:
        """
        Get the CANopen type of all slave terminals for each available EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_counts: a list comprising the number of slaves on all devices

        :returns: a list comprising a list of slave types for each EtherCAT device
        """
        slave_types: Sequence[Sequence[str]] = []
        for netid, slave_count in zip(dev_netids, dev_slave_counts, strict=True):
            types: Sequence[str] = []
            for n in range(slave_count):
                coe_index = hex(CoEIndex.ADS_COE_OPERATIONAL_PARAMS + n)
                response = await self._ads_read(
                    AdsReadRequest.read_slave_type(coe_index),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                types.append(bytes_to_string(response.data))
            slave_types.append(types)

        return slave_types

    async def _get_slave_names(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_counts: Sequence[int],
    ) -> Sequence[Sequence[str]]:
        """
        Get the CANopen name of all slave terminals for each available EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_counts: a list comprising the number of slaves on all devices

        :returns: a list comprising a list of slave names for each EtherCAT device
        """
        slave_names: Sequence[Sequence[str]] = []
        for netid, slave_count in zip(dev_netids, dev_slave_counts, strict=True):
            names: Sequence[str] = []
            for n in range(slave_count):
                coe_index = hex(CoEIndex.ADS_COE_OPERATIONAL_PARAMS + n)
                response = await self._ads_read(
                    AdsReadRequest.read_slave_name(coe_index),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                names.append(bytes_to_string(response.data, strip=True))
            slave_names.append(names)

        return slave_names

    async def _get_slave_states(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_addresses: Sequence[Sequence[np.uint16]],
    ) -> Sequence[Sequence[SlaveState]]:
        """
        Get the EtherCAT state of all slave terminals for each EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_addresses: a list comprising the EtherCAT addresses of the
            slave terminals on all devices

        :returns: a list comprising a list of slave states for each EtherCAT device
        """
        slave_states: Sequence[Sequence[SlaveState]] = []
        for netid, slave_addresses in zip(dev_netids, dev_slave_addresses, strict=True):
            states: Sequence[SlaveState] = []
            for address in slave_addresses:
                response = await self._ads_read(
                    AdsReadRequest.read_slave_states(address),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                states.append(SlaveState.from_bytes(response.data))
            slave_states.append(states)

        return slave_states

    async def _make_slave_objects(
        self,
        dev_slave_types: Sequence[Sequence[str]],
        dev_slave_names: Sequence[Sequence[str]],
        dev_slave_addresses: Sequence[Sequence[np.uint16]],
        dev_slave_identities: Sequence[Sequence[IOIdentity]],
        dev_slave_states: Sequence[Sequence[SlaveState]],
    ) -> Sequence[Sequence[IOSlave]]:
        """
        Create custom slave objects from slave specific parameters.

        :param dev_slave_types: a list of slave type arrays for each EtherCAT device
        :param dev_slave_names: a list of slave name arrays for each EtherCAT device
        :param dev_slave_identities: a list of slave identitie arrays for each device
        :param dev_slave_addresses: a list of slave address arrays for each device

        :returns: a list comprising an array of the slave objects configured on each
            EtherCAT device
        """
        dev_slaves: Sequence[Sequence[IOSlave]] = []
        for (
            dev_slave_type,
            dev_slave_name,
            dev_slave_addr,
            dev_slave_identity,
            dev_slave_state,
        ) in list(
            zip(
                dev_slave_types,
                dev_slave_names,
                dev_slave_addresses,
                dev_slave_identities,
                dev_slave_states,
                strict=True,
            )
        ):
            slaves = [
                IOSlave(*tpl)
                for tpl in list(
                    zip(
                        dev_slave_type,
                        dev_slave_name,
                        dev_slave_addr,
                        dev_slave_identity,
                        dev_slave_state,
                        strict=True,
                    )
                )
            ]
            dev_slaves.append(slaves)

        return dev_slaves

    async def _get_ethercat_devices(
        self,
    ) -> dict[SupportsInt, IODevice]:
        """
        Get information about the EtherCAT devices registered with the IO server.

        :returns: a sequence of available EtherCAT devices
        """
        devices: dict[SupportsInt, IODevice] = {}
        try:
            dev_ids = await self._get_device_ids(self.ioserver.num_devices)
            logging.debug(f"List of device ids: {dev_ids}")

            dev_types = await self._get_device_types(dev_ids)
            logging.debug(f"List of device types: {dev_types}")

            dev_names = await self._get_device_names(dev_ids)
            logging.debug(f"List of device names: {dev_names}")

            dev_netids = await self._get_device_netids(dev_ids)
            logging.debug(f"List of device netids: {dev_netids}")

            dev_identities = await self._get_device_identities(dev_netids)
            logging.debug(f"List of device identities: {dev_identities}")

            dev_frames = await self._get_device_frame_counters(dev_netids)
            logging.debug(f"List of device frame counters at start: {dev_frames}")

            dev_slave_counts = await self._get_slave_count(dev_netids)
            logging.debug(f"List of device slave counts: {dev_slave_counts}")

            dev_slave_crc_counters = await self._get_slave_crc_counters(
                dev_netids, dev_slave_counts
            )
            logging.debug(
                f"List of device slave CRC counters at start: {dev_slave_crc_counters}"
            )

            dev_slave_addresses = await self._get_slave_addresses(
                dev_netids, dev_slave_counts
            )
            logging.debug(f"List of device slave addresses: {dev_slave_addresses}")

            dev_slave_identities = await self._get_slave_identities(
                dev_netids, dev_slave_addresses
            )
            logging.debug(f"List of device slave identities: {dev_slave_identities}")

            dev_slave_types = await self._get_slave_types(
                dev_netids,
                dev_slave_counts,
            )
            logging.debug(f"List of device slave types: {dev_slave_types}")

            dev_slave_names = await self._get_slave_names(
                dev_netids,
                dev_slave_counts,
            )
            logging.debug(f"List of device slave names: {dev_slave_names}")

            dev_slave_states = await self._get_slave_states(
                dev_netids,
                dev_slave_addresses,
            )
            logging.debug(f"List of device slave states at start: {dev_slave_states}")

            dev_slaves = await self._make_slave_objects(
                dev_slave_types,
                dev_slave_names,
                dev_slave_addresses,
                dev_slave_identities,
                dev_slave_states,
            )
            logging.debug(f"List of device slaves: {dev_slaves}")

            for params in list(
                zip(
                    dev_ids,
                    dev_types,
                    dev_names,
                    dev_netids,
                    dev_identities,
                    dev_frames,
                    dev_slave_counts,
                    dev_slave_crc_counters,
                    dev_slaves,
                    strict=True,
                )
            ):
                device = IODevice(*params)
                devices[device.id] = device

        except AssertionError as err:
            logging.critical(f"Problem during EtherCAT devices introspection -> {err}")

        return devices

    def _print_device_chain(
        self,
        device_id: SupportsInt,
    ) -> None:
        """
        Provide a console visualization of the EtherCAT chain for a given device.

        :param device_id: the id value of the EtherCAT device
        """
        print("\n============ Active EtherCAT devices ============")
        print("|")
        print(f"|----EherCAT Master '{self._ecdevices[device_id].name}'")
        print("\t|")
        for slave in self._ecdevices[device_id].slaves:
            if ("EK1100" in slave.name) | ("EK1200" in slave.name):
                print(
                    f"\t|----- {slave.loc_in_chain.node}::"
                    + f"{slave.loc_in_chain.position} -> {slave.name}"
                )
            else:
                print(
                    f"\t\t|----- {slave.loc_in_chain.node}::"
                    + f"{slave.loc_in_chain.position}\t-> {slave.type}\t{slave.name}"
                )

    async def _get_EtherCAT_chains(
        self,
    ) -> None:
        """
        Evaluate the position of the configured slaves in each EtherCAT device chain.
        Display the resulting chains on the console.

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        ...
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )

        for device in self._ecdevices.values():
            i, node, node_position = 0, 0, 0
            for slave in device.slaves:
                if slave.type == "EK1100":
                    node += 1
                    node_position = 0
                slave.loc_in_chain = ChainLocation(node, node_position)
                node_position += 1
                i += 1

            self._print_device_chain(device.id)

    async def introspect_IO_server(
        self,
    ) -> None:
        """
        Gather information about the EtherCAT I/O server (inc. name, version and build),
        identify the registered EtherCAT devices and associated slaves,
        and print out to the console the EtherCAT device chains.
        """
        self.ioserver = await self._read_io_info()
        logging.info(
            f"ADS device info: \tname={self.ioserver.name}, "
            + f"version={self.ioserver.version}, build={self.ioserver.build}"
        )
        logging.info(f"Number of I/O devices: {self.ioserver.num_devices}")
        assert self.ioserver.num_devices != 0, (
            "No device is registered with the I/O server"
        )

        self._ecdevices = await self._get_ethercat_devices()
        logging.info(f"Available I/O devices: {self._ecdevices}")

        await self._get_EtherCAT_chains()

    #################################################################
    ### I/O MONITORS: STATES, COUNTERS, FRAMES ----------------------
    #################################################################

    async def _get_states(
        self, netid: AmsNetId, port: int
    ) -> tuple[np.uint16, np.uint16]:
        """
        Read the ADS status.

        :param netid: the ams netid of the service to query the state from
        :param port: the ams port of the service to query the state from

        :returns: a tuple comprising both the ads link status and the ads device status
        """
        response = await self._ads_read(AdsReadStateRequest(), netid=netid, port=port)

        return response.ads_state, response.device_state

    async def check_ads_states(
        self,
    ) -> None:
        """
        Check that the ADS communication status with the IO server and devices is valid.

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )
        try:
            io_adsstate, io_devstate = await self._get_states(
                netid=self.__target_ams_net_id, port=IO_SERVER_PORT
            )
            logging.debug(f"IO states: ads={io_adsstate}, dev={io_devstate}")
            assert io_adsstate == AdsState.ADSSTATE_RUN, "IO device is not in run mode"

            for device in self._ecdevices.values():
                ec_adsstate, ec_devstate = await self._get_states(
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                logging.debug(
                    f"DEV{device.id} states: ads={ec_adsstate}, dev={ec_devstate}"
                )
                assert ec_devstate == SlaveLinkState.SLAVE_LINK_STATE_OK, (
                    "ADS link to EtherCAT device is not good"
                )

        except AssertionError as err:
            logging.critical(f"Problem during ADS communication status check -> {err}")
            raise

    async def check_slave_states(
        self, device_id: SupportsInt, slave_address: SupportsInt
    ) -> SlaveState:
        """
        Read the EtherCAT status of a given EtherCAT slave.

        :param device_id: the id of the EtherCAT device which the slave belongs to
        :param slave_address: the EtherCAT address of the slave terminal

        :returns: the EtherCAT state of the slave terminal

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )
        try:
            device = next(
                (dev for dev in self._ecdevices.values() if dev.id == int(device_id)),
                None,
            )
            assert device is not None, (
                f"No EtherCAT device with id {device_id} is registered \
                    with the I/O server."
            )
            assert slave_address in [s.address for s in device.slaves], (
                f"No slave terminal is defined at address {slave_address} \
                    on the EtherCAT device with id {device_id}."
            )
            response = await self._ads_read(
                AdsReadRequest.read_slave_states(slave_address),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            state = SlaveState.from_bytes(response.data)
            assert state.eCAT_state == SlaveStateMachine.SLAVE_STATE_OP, (
                "A slave terminal is not in operational state"
            )

            assert state.link_status == SlaveLinkState.SLAVE_LINK_STATE_OK, (
                "EtherCAT link for a slave terminal isn't in a good state"
            )

        except AssertionError as err:
            logging.critical(
                f"Problem during status check of an EtherCAT slave -> {err}"
            )
            raise

        return state

    async def poll_states(
        self,
    ) -> None:
        """
        Read the current ADS state of the EtherCAT devices and their associated slaves.
        """
        while not self._ecdevices:
            logging.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                # Check the device operation state.
                dev_response = await self._ads_read(
                    AdsReadRequest.read_device_state(),
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                dev_state = int.from_bytes(
                    bytes=dev_response.data, byteorder="little", signed=False
                )
                logging.debug(f"{device.name} state: {dev_state}")
                assert dev_state == DeviceStateMachine.DEVSTATE_OP, (
                    f"{device.name} is not operational, {DeviceStateMachine(dev_state)}"
                )

                # Check the slaves operation states.
                slave_response = await self._ads_read(
                    AdsReadRequest.read_slaves_states(device.slave_count),
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                states = np.frombuffer(
                    slave_response.data,
                    dtype=[("eCAT_state", np.uint8), ("link_status", np.uint8)],
                    count=int(device.slave_count),
                )

                # If any slave terminal is not operating as expected, update its status.
                if not np.all(states["eCAT_state"] == SlaveStateMachine.SLAVE_STATE_OP):
                    bad_eCAT = np.nonzero(
                        states["eCAT_state"] != SlaveStateMachine.SLAVE_STATE_OP
                    )[0]
                    assert bad_eCAT.size
                    for idx in bad_eCAT:
                        slave: IOSlave = (device.slaves)[idx]
                        logging.critical(
                            f"Slave terminal '{slave.name}' isn't in operational state."
                        )
                        slave.states.eCAT_state = states["eCAT_state"][idx]
                if not np.all(
                    states["link_status"] == SlaveLinkState.SLAVE_LINK_STATE_OK
                ):
                    bad_link = np.nonzero(
                        states["link_status"] != SlaveLinkState.SLAVE_LINK_STATE_OK
                    )[0]
                    assert bad_link.size
                    for idx in bad_link:
                        slave: IOSlave = (device.slaves)[idx]
                        logging.critical(
                            f"EtherCAT link for slave terminal '{slave.name}' isn't "
                            + "in a good state."
                        )
                        slave.states.link_status = states["link_status"][idx]

        except AssertionError as err:
            logging.critical(f"Problem polling an EtherCAT device state -> {err}")
            raise

    async def check_slave_crc(
        self, device_id: SupportsInt, slave_address: SupportsInt
    ) -> SlaveCRC:
        """
        Read the cyclic redundancy check counter values of a given EtherCAT slave.

        :param device_id: the id of the EtherCAT device which the slave belongs to
        :param slave_address: the EtherCAT address of the slave terminal

        :returns: the EtherCAT slave CRC counters

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )

        try:
            device = next(
                (dev for dev in self._ecdevices.values() if dev.id == int(device_id)),
                None,
            )
            assert device is not None, (
                f"No EtherCAT device with id {device_id} is registered \
                    with the I/O server."
            )
            assert slave_address in [s.address for s in device.slaves], (
                f"No slave terminal is defined at address {slave_address} \
                    on the EtherCAT device with id {device_id}."
            )
            response = await self._ads_read(
                AdsReadRequest.read_slave_crc(slave_address),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            # Padding is required in case some of the communication ports aren't used.
            return SlaveCRC.from_bytes(response.data.ljust(32, b"\0"))

        except AssertionError as err:
            logging.critical(f"Problem reading a slave CRC value -> {err}")
            raise

    async def poll_crc_counters(
        self,
    ) -> None:
        """
        Read the current error counter values of the slaves' CRC for each device.
        """
        while not self._ecdevices:
            logging.warning(
                "... waiting for EtherCAT devices initialisation before "
                + "polling CRC counters"
            )
            await asyncio.sleep(1)

        for device in self._ecdevices.values():
            response = await self._ads_read(
                AdsReadRequest.read_slaves_crc(device.slave_count),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            slaves_crc = np.frombuffer(
                response.data,
                dtype=np.uint32,
                count=int(device.slave_count),
            )

            # TO DO:
            # if required, this could be propagated down as an IOSlave class attribute.
            if not np.array_equal(device.slave_crc_counters, slaves_crc):
                device.slave_crc_counters = slaves_crc
                logging.warning(
                    f"{device.name}: slave CRC counters have changed and been updated."
                )

    async def get_device_frames(self, device_id: SupportsInt) -> None:
        """
        Read the frame counter values of an EtherCAT device.
        Frame counters include cyclic and acyclic frames, both sent and lost.

        :param device_id: the id of the EtherCAT device to get the frame counters from

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )

        try:
            device = next(
                (dev for dev in self._ecdevices.values() if dev.id == int(device_id)),
                None,
            )
            assert device is not None, (
                f"No EtherCAT device with id {device_id} is registered \
                    with the I/O server."
            )
            response = await self._ads_read(
                AdsReadRequest.read_device_frame_counters(),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            device.frame_counters = DeviceFrames.from_bytes(response.data)

        except AssertionError as err:
            logging.critical(f"Problem reading a device frame counter value -> {err}")
            raise

    async def poll_frame_counters(
        self,
    ) -> None:
        """
        Get the current frame counter values of all registered EtherCAT devices.
        """
        while not self._ecdevices:
            logging.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                await self.get_device_frames(device.id)
                logging.debug(
                    f"{device.name} frame counters: "
                    + f"cyclic_sent={device.frame_counters.cyclic_sent}, "
                    + f"cyclic_lost={device.frame_counters.cyclic_lost}, "
                    + f"acyclic_sent={device.frame_counters.acyclic_sent}, "
                    + f"cyclic_lost={device.frame_counters.acyclic_lost}, "
                )
        except AssertionError as err:
            logging.critical(f"Problem polling device frame counter values -> {err}")
            raise

    async def reset_device_frames(self, device_id: SupportsInt) -> None:
        """
        Command an EtherCAT device to reset its frame counters and lost frame counters.

        :param device_id: the id of the EtherCAT device to reset the frame counters from

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )
        try:
            device = next(
                (dev for dev in self._ecdevices.values() if dev.id == int(device_id)),
                None,
            )
            assert device is not None, (
                f"No EtherCAT device with id {device_id} is registered \
                    with the I/O server."
            )

            response_event = await self._send_ams_message(
                CommandId.ADSSRVID_WRITE,
                AdsWriteRequest.reset_device_frame_counters(),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            response = await response_event.get(AdsWriteResponse)
            assert response.result == ErrorCode.ERR_NOERROR, (
                f"ERROR {ErrorCode(response.result)}"
            )

        except AssertionError as err:
            logging.critical(f"Problem resetting a device frame counter value -> {err}")
            raise

    async def reset_frame_counters(
        self,
    ) -> None:
        """
        Reset the frame counters of all EtherCAT devices registered with the I/O server.
        """
        while not self._ecdevices:
            logging.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                await self.reset_device_frames(device.id)
                logging.info(f"Frame counters for {device.name} have been reset.")
        except AssertionError as err:
            logging.critical(f"Problem resetting device frame counter values -> {err}")
            raise

    # #################################################################
    # ### DEVICE SYMBOLS ----------------------------------------------
    # #################################################################

    def _parse_symbol_table_entry(
        self, device_id: SupportsInt, symbol_count: int, table_entries: bytes
    ) -> Sequence[AdsSymbolNode]:
        """
        Extract the ADS symbol node objects from a symbol table entry.

        :param symbol_count: the number of symbol entries registered in the table
        :param table_entries: a byte array comprising sequential symbol node information

        :returns: a list of all the symbol nodes available on the EtherCAT device
        """
        symbol_nodes: Sequence[AdsSymbolNode] = []
        data = table_entries
        for _ in range(symbol_count):
            entry = AdsSymbolTableEntry.from_bytes(data)
            dtype = np.dtype(
                [
                    ("name", np.dtype((np.bytes_, int(entry.name_size) + 1))),
                    ("type", np.dtype((np.bytes_, int(entry.type_size) + 1))),
                    ("comment", np.dtype((np.bytes_, int(entry.comment_size) + 1))),
                ]
            )
            arr = np.frombuffer(entry.data, dtype=dtype, count=1)
            symbol_nodes.append(
                AdsSymbolNode(
                    parent_id=device_id,
                    name=bytes_to_string(arr["name"].tobytes()),
                    type_name=bytes_to_string(arr["type"].tobytes()),
                    ads_type=entry.ads_type,
                    size=entry.size,
                    index_group=entry.index_group,
                    index_offset=entry.index_offset,
                    flag=entry.flag,
                    comment=bytes_to_string(arr["comment"].tobytes()),
                )
            )
            data = data[entry.read_length :]

        assert data == b"", f"Error: unprocessed data in the symbol table: {data}"

        return symbol_nodes

    async def get_device_symbols(self, device_id: SupportsInt) -> None:
        """
        Get all available ADS symbols on the EtherCAT I/O server.

        :param device_id: the id of the EtherCAT device to get the symbols from
        """
        # Get the length of the symbol table
        response = await self._ads_read(
            AdsReadRequest.get_length_symbol_table(),
            netid=self.__target_ams_net_id,
            port=self.__target_ams_port,
        )
        symbol_table = AdsSymbolTableInfo.from_bytes(response.data)

        # Get a list of the defined symbol nodes
        response = await self._ads_read(
            AdsReadRequest.fetch_symbol_table(symbol_table.table_length),
        )
        nodes = self._parse_symbol_table_entry(
            device_id, int(symbol_table.symbol_count), response.data
        )

        # Get a list of the available symbols
        symbols = []
        for node in nodes:
            symbols.extend(symbol_lookup(node))
        self._ecsymbols[device_id] = symbols
        logging.info(
            f"{symbol_table.symbol_count} entries in the symbol table returned "
            + f"a total of {len(symbols)} available symbols."
        )

    async def get_all_symbols(
        self,
    ) -> dict[SupportsInt, Sequence[AdsSymbol]]:
        """
        Get all ADS symbols available on the EtherCAT I/O server.

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )
        assert len(self._ecdevices) == 1, (
            "Only one EtherCAT device is supported for the moment."
        )
        dev_id = next(iter(self._ecdevices.keys()))
        await self.get_device_symbols(dev_id)

        return self._ecsymbols

    # #################################################################
    # ### DEVICE NOTIFICATIONS ----------------------------------------
    # #################################################################

    async def get_handle_by_name(self, name: str) -> int:
        """
        Get a unique identifier associated with the symbol name.
        It provides read/write access to the symbol variable
        whatever its position within the process image.

        :param name: name of the symbol variable

        :returns: a unique handle value
        """
        response_event = await self._send_ams_message(
            CommandId.ADSSRVID_READWRITE,
            AdsReadWriteRequest.get_handle_by_name(name=name),
        )
        response = await response_event.get(AdsReadWriteResponse)
        handle = int.from_bytes(bytes=response.data, byteorder="little", signed=False)
        return handle

    async def add_device_notification(
        self,
        symbol: AdsSymbol,
        max_delay_ms: int = 0,
        cycle_time_ms: int = 0,
    ) -> None:
        """
        Subscribe to notifications from the server for a given device symbol variable.

        :param symbol: the symbol variable to subscribe to.

        :param max_delay_ms: maximum time in milliseconds after which the ads device \
            notification is called.
            The smallest possible value is the task cycle time

        :param cycle_time_ms: periodic time slice in milliseconds at which the ads \
            server checks if the value changes.
            If 0, then the server will check the value with every task cycle
        """
        assert symbol in self._ecsymbols[symbol.parent_id], (
            f"Symbol '{symbol.name}' not found in the symbol list \
                of device {self._ecdevices[symbol.parent_id].name}."
        )

        variable_handle = self.__variable_handles.get(symbol.name, None)
        if variable_handle is None:
            variable_handle = await self.get_handle_by_name(name=symbol.name)
            assert variable_handle not in self.__variable_handles.values(), (
                f"Handle assignment error: handle id {variable_handle} \
                    is already defined."
            )
            self.__variable_handles[symbol.name] = variable_handle

        request = AdsAddDeviceNotificationRequest(
            index_group=IndexGroup.ADSIGR_GET_SYMVAL_BYHANDLE,
            index_offset=variable_handle,
            length=(np.dtype(symbol.dtype).itemsize) * symbol.size,
            transmission_mode=TransmissionMode.ADSTRANS_SERVERCYCLE,
            max_delay=int(max_delay_ms * 1e4),
            cycle_time=int(cycle_time_ms * 1e4),
        )

        response_event = await self._send_ams_message(
            CommandId.ADSSRVID_ADDDEVICENOTE, request
        )
        response = await response_event.get(AdsAddDeviceNotificationResponse)
        assert response.result == ErrorCode.ERR_NOERROR, ErrorCode(response.result)
        symbol.handle = response.handle

        # TO DO: check that notification handles don't get duplicated between devices,
        # otherwise dictionary must be separated further by device id
        self.__device_notification_handles[response.handle] = symbol
        logging.debug(
            f"Notification subscription for Device{symbol.parent_id}:{symbol.name} "
            + f"completed with handle {symbol.handle}."
        )

        self.__notif_templates = {}

    async def add_notifications(
        self,
        symbols: AdsSymbol | Sequence[AdsSymbol] | None = None,
        max_delay_ms: int = 0,
        cycle_time_ms: int = 0,
    ) -> None:
        """
        Subscribe to notifications from the server for given symbol variables.

        :param symbols: the symbol variable(s) to subscribe to.
            If None, then all symbols from all EtherCAT devices are subscribed to

        :param max_delay_ms: maximum time in milliseconds after which the ads device \
            notification is called.
            The smallest possible value is the task cycle time

        :param cycle_time_ms: periodic time slice in milliseconds at which the ads \
            server checks if the value changes.
            If 0, then the server will check the value with every task cycle

        :raises ValueError: if no EtherCAT device symbol is defined with the ADS client
        """
        if symbols is None:
            if not self._ecsymbols:
                raise ValueError(
                    "No device symbol has been defined with the ADS client yet."
                )
            all_symbols: Sequence[AdsSymbol] = []
            for _, dev_symbols in self._ecsymbols.items():
                all_symbols.extend(dev_symbols)
        else:
            if isinstance(symbols, AdsSymbol):
                all_symbols = [symbols]
            else:
                all_symbols = symbols

        for symbol in all_symbols:
            await self.add_device_notification(symbol, max_delay_ms, cycle_time_ms)

        logging.info(
            f"Successfully added {len(self.__device_notification_handles)} "
            + "notification handles"
        )

    async def delete_device_notification(
        self,
        symbol: AdsSymbol,
    ) -> None:
        """
        Remove a defined symbol notification subscription from the ADS server.

        :param symbol: the symbol variable to terminate device notification for

        :raises KeyError: exception arising when trying to delete a notification \
            subscription which doesn't exist
        """
        if symbol.handle is None:
            raise KeyError(
                f"{symbol.name} notifications are not registered as an active \
                    ADS subscription."
            )
        request = AdsDeleteDeviceNotificationRequest(
            handle=symbol.handle,
        )
        response_event = await self._send_ams_message(
            CommandId.ADSSRVID_DELETEDEVICENOTE, request
        )
        response = await response_event.get(AdsDeleteDeviceNotificationResponse)
        assert response.result == ErrorCode.ERR_NOERROR, ErrorCode(response.result)

        del self.__device_notification_handles[symbol.handle]
        logging.debug(
            f"Deleted notification handle {symbol.handle} for symbol {symbol.name} "
            + f"on device {self._ecdevices[symbol.parent_id].name}"
        )
        symbol.handle = None
        self.__notif_templates = {}

    async def delete_notifications(
        self, symbols: AdsSymbol | Sequence[AdsSymbol] | None = None
    ) -> None:
        """
        Delete the subscribed notifications from the server for given symbol variables.

        :param symbols: the symbol variable(s) to unsubscribe from.
            If None, then all symbols from all EtherCAT devices are unsubscribed from

        :raises ValueError: if no EtherCAT device symbol is defined with the ADS client
        """
        if symbols is None:
            if not self._ecsymbols:
                raise ValueError(
                    "No device symbol has been defined with the ADS client yet."
                )
            all_symbols: Sequence[AdsSymbol] = []
            for _, dev_symbols in self._ecsymbols.items():
                all_symbols.extend(dev_symbols)
        else:
            if isinstance(symbols, AdsSymbol):
                all_symbols = [symbols]
            else:
                all_symbols = symbols

        err_counter = 0
        for symbol in all_symbols:
            try:
                await self.delete_device_notification(symbol)
            except ValueError:
                err_counter += 1
            except KeyError as err:
                logging.error(
                    f"Notification deletion for {symbol.name} failed -> {err}."
                )

        if err_counter:
            logging.error(
                f"Failed to unsubscribe notifications for {err_counter} "
                + f"symbols out of {len(all_symbols)}."
            )
        else:
            logging.info(
                f"Successfully deleted client subscription to {len(all_symbols)} "
                + "symbol notifications."
            )

    def start_notification_monitor(
        self,
        flush_period: float = 0.5,
    ) -> None:
        """
        Trigger the appending of received ADS notifications into the buffer and \
            enable periodic flushing.

        :params flush_period: period in seconds when the notification data is flushed \
            to a queue
        """
        self.__num_notif_streams = 0
        self.__notif_templates = {}
        self.__buffer = bytearray()
        self.__flush_notifications_task = asyncio.create_task(
            self._periodic_flush(flush_period)
        )

    def stop_notification_monitor(
        self,
    ) -> None:
        """
        Disable periodic flushing which will also stop the appending of received \
            ADS notifications into the buffer.
        """
        self.__flush_notifications_task.cancel()

    async def _periodic_flush(self, interval_sec: float) -> None:
        """
        Periodically send the notification buffer to a queue.

        :param interval_sec: the period which flushing of the buffer to the queue \
            occurs at
        """
        template_data = b""
        streams_dtype = np.dtype([])
        first_flush = True
        while True:
            try:
                await asyncio.sleep(interval_sec)
                if self.__buffer is not None:
                    # Define the fixed stream model
                    # which the received notification buffer will be translated against.
                    if first_flush:
                        assert self.__notif_templates, (
                            "Flushing period is too short, \
                                notification data has not been initialised yet."
                        )

                        if 1 in self.__notif_templates:
                            # Multiple ADS notification streams are used by the server
                            # to report all requested notifications.
                            size = len(self.__notif_templates).to_bytes(
                                np.dtype(np.uint16).itemsize,
                                byteorder="little",
                                signed=False,
                            )
                            for data in self.__notif_templates.values():
                                template_data += data
                            streams = AdsCombinedNotificationStream.from_bytes(
                                size + template_data
                            )
                            streams_dtype = streams.get_combined_notifications_dtype(
                                self.__device_notification_handles
                            )
                        else:
                            # All requested notifications are reported in a single
                            # ADS notification stream.
                            template_data = self.__notif_templates[0]
                            streams = AdsNotificationStream.from_bytes(template_data)
                            streams_dtype = streams.get_notification_dtype(
                                self.__device_notification_handles
                            )

                        first_flush = False

                    # Wait for the notification buffer to be complete (i.e. includes all
                    # notifications from the cycle), then add it to the queue.
                    # Ignore process when no buffer is available,
                    # e.g. when flush period < notification cycle time
                    if not len(self.__buffer) == 0:
                        buffer = self.__buffer
                        self.__buffer = bytearray()
                        assert len(buffer) % len(template_data) == 0, (
                            "Request to flush an incomplete notification buffer."
                        )
                        self.__notification_queue.put_nowait(
                            await self._get_notifications_from_buffer(
                                streams_dtype, buffer
                            )
                        )

            except asyncio.CancelledError:
                # Add the last notification buffer to the queue despite the flushing
                # period not having completed.
                if self.__buffer is not None:
                    buffer = self.__buffer
                    self.__buffer = None
                    self.__notification_queue.put_nowait(
                        await self._get_notifications_from_buffer(streams_dtype, buffer)
                    )
                logging.info("...periodic flushing of notifications has ended.")
                break

    async def _get_notifications_from_buffer(
        self, stream_dtype: npt.DTypeLike, buffer: bytearray
    ) -> npt.NDArray:
        """
        Get the notification messages sent by the ADS device; \
            each message may contain multiple notifications.
        The data stream is extracted as an array of known data structures, \
            each corresponding to a distinct notification.

        :param streams_dtype: the data structure which the ads notification message \
            conforms to (i.e. single stream or combined streams)
        :param buffer: the bytes array comprising one or more ads notification messages

        :returns: an array of ads notifications
        """
        return np.frombuffer(
            buffer,
            dtype=stream_dtype,
        )

    async def get_notifications(self, timeout: int = 60) -> npt.NDArray:
        """
        Get the notification array available on the notification queue.
        (Temporary) A timeout is in place to exit the method if no notification data \
            has been added to the queue for a given period.

        :param timeout: the time in seconds to wait for new notification data to arrive

        :raises TimeoutError: timeout exception arising when no notification has been \
            received within the specified period
        """
        try:
            async with asyncio.timeout(timeout):
                notifs = await self.__notification_queue.get()
                self.__notification_queue.task_done()
                num_header_fields = 4 * self.__num_notif_streams
                logging.info(
                    f"Got {len(notifs)} notifications with "
                    + f"{(len(notifs.dtype.fields) - num_header_fields) // 3} "
                    + "I/O terminal values."
                )
                return notifs
        except TimeoutError as err:
            raise TimeoutError(
                f"...no notification added to the queue for the past {timeout} seconds!"
            ) from err

    def process_notifications(
        self,
        func: Callable,
        notifications: npt.NDArray,
    ) -> None:
        """
        Manipulate the received notification array by applying a given function.
        This method may be used to test the load on the client resources.

        :param func: the processing function to apply to the notification data
        :param notifications: a numpy array comprising multiple ADS notifications
        """
        data = func(notifications)
        # logging.info(
        #     f"Applied '{func.__name__}' function " + f"to notification data:\n{data}"
        # )
