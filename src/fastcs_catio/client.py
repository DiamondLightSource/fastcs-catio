"""
ADS communication protocol
https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html&id=6446904803799887467
"""

from __future__ import annotations

import asyncio
import re
import socket
import time
from collections.abc import Awaitable, Callable, Sequence
from contextlib import closing
from copy import deepcopy
from logging import getLogger
from typing import Any, SupportsInt, TypeVar, dataclass_transform, overload

import numpy as np
import numpy.typing as npt

from ._constants import (
    TWINCAT_STRING_ENCODING,
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
    SystemServiceCommandId,
    TransmissionMode,
    UDPTag,
)
from ._types import AmsAddress, AmsNetId
from .devices import (
    AdsSymbol,
    AdsSymbolNode,
    ChainLocation,
    DeviceFrames,
    IODevice,
    IOIdentity,
    IONodeType,
    IOServer,
    IOSlave,
    IOTreeNode,
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
    AdsUDPMessage,
    AdsUDPResponseStream,
    AdsWriteRequest,
    AdsWriteResponse,
    AmsHeader,
    Message,
    MessageRequest,
    MessageResponse,
    SlaveCRC,
    UDPInfo,
)
from .symbols import symbol_lookup
from .utils import (
    bytes_to_string,
    get_local_netid_str,
    get_localhost_ip,
    get_localhost_name,
)

logger = getLogger(__name__)

# https://infosys.beckhoff.com/content/1033/ipc_security_win7/11019143435.html
ADS_TCP_PORT: int = 48898
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcsystemmanager/1089026187.html&id=754756950722060432
ADS_MASTER_PORT: int = 65535
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_system/31084171.html&id=
IO_SERVER_PORT: int = 300
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/index.html&id=2683277694279723185
# https://infosys.beckhoff.com/english.php?content=../content/1033/ipc_security_win7/11019143435.html&id=
SYSTEM_SERVICE_PORT: int = 10000

REMOTE_UDP_PORT: int = 48899


MessageT = TypeVar("MessageT", bound=Message)
FuncType = Callable[[Any, Any], Awaitable[Any]]


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


#################################################################
### REMOTE ROUTE ------------------------------------------------
#################################################################


def get_remote_address(remote_ip: str) -> AmsNetId:
    """
    Get the AmsNetId of a remote TwinCAT server via UDP communication.

    :param remote_ip: IP address of the remote TwinCAT server
    :returns: the AmsNetId of the remote TwinCAT server
    """
    UDPMessage.invoke_id += 1
    request = AdsUDPMessage.get_remote_info(UDPMessage.invoke_id)
    return UDPMessage(remote_ip).get_netid(request)


@dataclass_transform(kw_only_default=True)
class UDPMessage:
    """
    Define a UDP communication message object to a remote Beckhoff TwinCAT server.
    """

    invoke_id: int = 0
    """Static variable used to assign a unique id to each UDP message"""
    UDP_COOKIE: bytes = b"\x71\x14\x66\x03"
    """Static variable defining the UDP cookie value used in the UDP message header"""

    def __init__(self, remote_ip: str):
        self.target = remote_ip
        """IP address of the remote Beckhoff TwinCAT server"""

    def _send_recv(self, message: AdsUDPMessage) -> bytes:
        """
        Send a UDP message to the remote target and receive the response.

        :param message: the UDP message to send
        :returns: the data block contained in the UDP response message
        """
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
            # Listen on any available port for the response from the CX
            sock.bind(("", 0))

            # Account for slow communications and enable TimeoutError to be raised
            sock.settimeout(5)

            # Send the data to the Beckhoff CX server target
            sock.sendto(message.to_bytes(), (self.target, REMOTE_UDP_PORT))

            # Receive the data from the Beckhoff CX server target
            data, addr = sock.recvfrom(1024)
            assert addr[0] == self.target, (
                "Unintended recipient for the UDP response message."
            )

            # Validate the UDP response message and extract the relevant data block
            response = AdsUDPMessage.from_bytes(data)
            assert response.udp_cookie == message.udp_cookie, (
                "Received invalid UDP cookie"
            )
            assert response.invoke_id == message.invoke_id, (
                "Unexpected UDP response identifier"
            )
            assert response.service_id == (
                message.service_id | SystemServiceCommandId.ADSSCVID_RESPONSE
            ), "Invalid command Id in UDP response"

            return response.data

    def get_netid(self, message: AdsUDPMessage) -> AmsNetId:
        """
        Get the AmsNetId of the remote Beckhoff TwinCAT server.

        :param message: the UDP message to send
        :returns: the AmsNetId of the remote Beckhoff TwinCAT server

        :raises TimeoutError: following a lack of UDP communication
        """
        try:
            response = AdsUDPResponseStream.from_bytes(self._send_recv(message))
            assert response.port == SYSTEM_SERVICE_PORT, (
                f"Expected UDP response from system service port "
                f"({SYSTEM_SERVICE_PORT}), "
                f"got port {response.port} instead."
            )
            return AmsNetId.from_bytes(response.netid.tobytes())

        except TimeoutError:
            logger.error("UDP communication with Beckhoff CX target timed out.")
            raise

    def add_route(self, message: AdsUDPMessage) -> bool:
        """
        Add a remote route to the Beckhoff TwinCAT server.

        :param message: the UDP message to send
        :returns: True if the route was added successfully, False otherwise

        :raises TimeoutError: following a lack of UDP communication
        """
        try:
            response = AdsUDPResponseStream.from_bytes(self._send_recv(message))
            assert response.port == SYSTEM_SERVICE_PORT, (
                f"Expected UDP response from system service port "
                f"({SYSTEM_SERVICE_PORT}), "
                f"got port {response.port} instead."
            )
            # TO DO: CAN WE CHECK RESPONSE FOR INVALID PASSWORD?
            for _ in range(response.count):
                info = UDPInfo.from_bytes(response.data)
                if info.tag_id != 1:
                    logger.warning(f"Ignoring tag {info.tag_id}")
                    continue
                if info.length != 4:
                    logger.error("Invalid tag length")
                    return False
                error_code = int.from_bytes(info.data, byteorder="little", signed=False)
                return error_code == ErrorCode.ERR_NOERROR
            return False

        except TimeoutError:
            logger.error("UDP communication with Beckhoff CX target timed out.")
            raise

    def delete_route(self, message: AdsUDPMessage):
        """
        Delete a remote route from the Beckhoff TwinCAT server.

        :param message: the UDP message to send
        :returns: True if the route was deleted successfully, False otherwise

        :raises TimeoutError: following a lack of UDP communication
        """
        try:
            response = AdsUDPResponseStream.from_bytes(self._send_recv(message))
            assert response.port == SYSTEM_SERVICE_PORT, (
                f"Expected UDP response from system service port ({SYSTEM_SERVICE_PORT}"
                + f"), but got port {response.port} instead."
            )
            error_code = response.count
            return error_code == ErrorCode.ERR_NOERROR

        except TimeoutError:
            logger.error("UDP communication with Beckhoff CX target timed out.")
            raise


class RemoteRoute:
    """
    Define a remote route to a Beckhoff TwinCAT server via UDP communication.
    """

    def __init__(
        self,
        remote: str,
        route_name: str = "",
        user_name: str = "Administrator",
        password: str = "1",
    ):
        self.remote = remote
        """IP address of the remote Beckhoff TwinCAT server"""
        self.routename = route_name or get_localhost_name()
        """Name assigned to the remote route"""
        self.hostnetid = AmsNetId.from_string(get_local_netid_str())
        """AmsNetId of the local host machine"""
        self.username = user_name
        """User name for authentication with the remote TwinCAT server"""
        self.password = password
        """Password for authentication with the remote TwinCAT server"""
        self.hostname = get_localhost_ip()
        """IP address of the local host machine (client)"""

    def _get_route_info_as_bytes(self) -> bytes:
        """
        Build the route information as an array of bytes.

        :returns: the route information as an array of bytes
        """
        lst: list[UDPInfo] = []
        # Remote ip not part of the route definition packet to send, so skip it
        params = deepcopy(vars(self))
        params.pop("remote")
        for name, value in params.items():
            udp_tag: UDPTag | None = getattr(UDPTag, name.upper(), None)
            if udp_tag:
                id = udp_tag.value
            else:
                raise KeyError(
                    f"{__class__}: argument name mismatch with expected UDP tag"
                )

            if isinstance(value, str):
                length = len(value) + 1
                data = value.encode(encoding=TWINCAT_STRING_ENCODING) + b"\x00"
            elif isinstance(value, AmsNetId):
                length = 6
                data = value.to_bytes()
            else:
                raise TypeError(
                    "Unexpected input parameter type in ADS route creation."
                )

            lst.append(UDPInfo(tag_id=id, length=length, data=data))

        count = len(lst).to_bytes(length=4, byteorder="little")
        address = AmsAddress(self.hostnetid, 0)
        param_bytes = b"".join([param.to_bytes() for param in lst])
        byte_array = address.to_bytes() + count + param_bytes

        return byte_array

    def add(self) -> bool:
        """
        Add a remote route to the Beckhoff TwinCAT server.

        :returns: True if the route was added successfully, False otherwise
        """
        UDPMessage.invoke_id += 1
        request = AdsUDPMessage.add_remote_route(
            UDPMessage.invoke_id, self._get_route_info_as_bytes()
        )

        status = UDPMessage(self.remote).add_route(request)
        if status:
            logger.debug(
                f"Successfully added host {self.hostname} to remote {self.remote}"
            )
        else:
            logger.error(
                f"Failed to add host machine {self.hostname} to remote {self.remote}"
            )

        return status

    def delete(self) -> bool:
        """
        Delete a remote route from the Beckhoff TwinCAT server.

        :returns: True if the route was deleted successfully, False otherwise
        """
        UDPMessage.invoke_id += 1
        request = AdsUDPMessage.del_remote_route(
            UDPMessage.invoke_id,
            self._get_route_info_as_bytes(),
        )

        status = UDPMessage(self.remote).delete_route(request)
        if status:
            logger.debug(
                f"Successfully deleted route {self.routename} from remote {self.remote}"
            )
        else:
            logger.error(
                f"Failed to delete route {self.routename} from remote {self.remote}"
            )

        return status


#################################################################
### ADS CLIENT ------------------------------------------------
#################################################################


class AsyncioADSClient:
    """
    Define an ADS client which connects to a given ADS server.
    Communication services comprise explicit ADS requests to the server \
        and continuous monitoring of ADS responses.
    ADS communication protocol follows a clear message packet format.
    """

    def __init__(
        self,
        target_ams_net_id: str,
        target_ams_port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.__local_ams_net_id: AmsNetId = AmsNetId.from_string(get_local_netid_str())
        """Container object comprising the localhost netid bytes"""
        self.__local_ams_port: int = 8000
        """The local port used for the ADS communication transport"""
        self.__target_ams_net_id: AmsNetId = AmsNetId.from_string(target_ams_net_id)
        """Container object comprising the ADS server netid bytes"""
        self.__target_ams_port: int = target_ams_port
        """The ADS server port which ADS communication is routed to/from"""
        self.__reader: asyncio.StreamReader = reader
        """Reader object used to read data asynchronously from the IO stream"""
        self.__writer: asyncio.StreamWriter = writer
        """Writer object used to write data asynchronously to the IO stream"""
        self.__current_invoke_id: int = 0
        """Id assigned to a message request and used to map the received responses"""
        self.__response_events: dict[SupportsInt, ResponseEvent] = {}
        """Dictionary which associates a received response to a unique request id"""
        self.__variable_handles: dict[
            str, int
        ] = {}  # key is variable name, value is notification handle
        """Dictionary which associates a distinct handle value to a symbol name"""
        self.__device_notification_handles: dict[
            SupportsInt, AdsSymbol
        ] = {}  # key is device id, value is dictionary of 'notification_handle: symbol'
        """Dictionar which associates a handle value to a notification variable"""
        self.__notif_templates: dict[
            int, bytes
        ] = {}  # key is notification stream index, value is notification data
        """Dictionary which associates each notification stream to an array of bytes \
            corresponding to the first received notification \
                and used as a datastructure template for the following notifications"""
        self.__buffer: bytearray | None = None
        """Array of bytes where device notifications are appended"""
        self.__bfr_cache: bytearray = bytearray()
        """Array of bytes used to save the partial notification data which is received \
        when multiple notification streams are required"""
        self.__notification_queue: asyncio.Queue = asyncio.Queue()
        """Asyncio queue where notification arrays are posted onto and consumed from"""
        self.__receive_task: asyncio.Task = asyncio.create_task(self._recv_forever())
        """Asynchronous task which monitors the reception of new ADS messages"""

        self._ecdevices: dict[
            SupportsInt, IODevice
        ] = {}  # key is device id, value is IODevice object
        """Dictionary comprising all EtherCAT devices registered on the IO server"""
        self._ecsymbols: dict[
            SupportsInt, Sequence[AdsSymbol]
        ] = {}  # key is device id, value is list of AdsSymbol objects
        """Dictionary comprising all ADS symbols configured on the EtherCAT devices"""
        self.fastcs_io_map: dict[
            int, IOServer | IODevice | IOSlave
        ] = {}  # key: FastCS controller object unique identifier, value: CATio object
        """Dictionary comprising all CATio objects mapped by their FastCS unique id"""
        self.__flush_notifications_task: asyncio.Task | None = None
        """Asynchronous task which periodically flushes the notification buffer"""

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
        logger.info(
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
        logger.info(
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
            target_net_id=ams_netid.to_bytes(),
            target_port=ams_port,
            source_net_id=self.__local_ams_net_id.to_bytes(),
            source_port=self.__local_ams_port,
            command_id=command,
            state_flags=StateFlag.AMSCMDSF_ADSCMD,
            length=len(payload),
            error_code=ErrorCode.ERR_NOERROR,
            invoke_id=np.uint32(self.__current_invoke_id),
        )
        header_raw = ams_header.to_bytes()
        total_length = len(header_raw) + len(payload)
        length_bytes = total_length.to_bytes(4, byteorder="little", signed=False)

        logger.debug(
            f"Sending AMS packet: len:{total_length}, cmd:{command}, "
            f"invoke_id:{self.__current_invoke_id}, target:{ams_netid}:{ams_port}"
        )
        self.__writer.write(b"\x00\x00" + length_bytes + header_raw + payload)

        await self.__writer.drain()
        logger.debug(f"Sent AMS packet len:{total_length}.")

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
        communication_timeout_sec = 120
        try:
            async with asyncio.timeout(communication_timeout_sec):
                logger.debug("Waiting to receive AMS message...")
                msg_bytes = await self.__reader.readexactly(6)
                assert msg_bytes[:2] == b"\x00\x00", (
                    f"Received an invalid TCP header: {msg_bytes.hex()}"
                )
                length = int.from_bytes(
                    msg_bytes[-4:], byteorder="little", signed=False
                )

                logger.debug(f"Expecting AMS message of length: {length} bytes")
                packet = await self.__reader.readexactly(length)
                logger.debug(f"Received packet of length {length} bytes")

                ams_header_length = 32
                header = AmsHeader.from_bytes(packet[:ams_header_length])
                body = packet[ams_header_length:]
                return header, body
        except TimeoutError as err:
            err.add_note(
                f"Empty packet after {communication_timeout_sec} seconds, "
                + "system likely disconnected."
            )
            raise
        except asyncio.IncompleteReadError as err:
            raise ConnectionError("Remote connection to the device has ended") from err
        except asyncio.CancelledError as err:
            raise ConnectionAbortedError(
                "Asynchronous monitoring of ADS messages has completed."
            ) from err
        except Exception as err:
            raise Exception("Client ADS messaging process failed.") from err

    async def _handle_notification(self, header: AmsHeader, body: bytes) -> None:
        """
        Read the notification message and build the whole message structure.
        Depending on the number of subscribed symbol variables,
        the notification message may comprise more than one frame.

        :param header: the notificatin message header
        :param body: the notification message data
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
                    assert CommandId(header.command_id) in RESPONSE_CLASS, (
                        f"ADS Command with id {header.command_id} is not implemented."
                    )
                    cls = RESPONSE_CLASS[CommandId(header.command_id)]
                    response = cls.from_bytes(body)
                    self.__response_events[header.invoke_id].set(response)

            except AssertionError as err:
                logger.error(err)
                break
            except ConnectionAbortedError as err:
                logger.warning(err)
                break
            except Exception as err:
                logger.error(err)
                break

    @overload
    async def _ads_command(
        self, request: AdsReadDeviceInfoRequest, **kwargs: AmsNetId | int
    ) -> AdsReadDeviceInfoResponse: ...

    @overload
    async def _ads_command(
        self, request: AdsReadStateRequest, **kwargs: AmsNetId | int
    ) -> AdsReadStateResponse: ...

    @overload
    async def _ads_command(
        self, request: AdsReadRequest, **kwargs: AmsNetId | int
    ) -> AdsReadResponse: ...

    @overload
    async def _ads_command(
        self, request: AdsWriteRequest, **kwargs: AmsNetId | int
    ) -> AdsWriteResponse: ...

    @overload
    async def _ads_command(
        self, request: AdsReadWriteRequest, **kwargs: AmsNetId | int
    ) -> AdsReadWriteResponse: ...

    async def _ads_command(
        self,
        request: MessageRequest,
        **kwargs: AmsNetId | int,
    ) -> MessageResponse:
        """
        Send an ADS Command request to the server and return the ADS response.

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

    async def _get_device_count(self) -> int:
        """
        Get the number of EtherCAT devices available on the I/O server.

        :returns: the number of EtherCAT devices
        """
        response = await self._ads_command(
            AdsReadRequest.read_device_count(), port=IO_SERVER_PORT
        )

        return int.from_bytes(bytes=response.data, byteorder="little", signed=False)

    async def _read_io_info(self) -> AdsReadDeviceInfoResponse:
        """
        Read the name and the version number of the TwinCAT ADS IO.

        :returns: an instance of AdsReadDeviceInfoResponse
        """
        return await self._ads_command(AdsReadDeviceInfoRequest(), port=IO_SERVER_PORT)

    async def _get_io_server(self) -> IOServer:
        """
        Get the I/O server information.
        This includes name, version, build and number of devices.

        :returns: an instance of an IOServer object
        """
        info_response = await self._read_io_info()

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
        response = await self._ads_command(
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
            try:
                response = await self._ads_command(
                    AdsReadRequest.read_device_type(id), port=IO_SERVER_PORT
                )
                types.append(
                    DeviceType(
                        int.from_bytes(
                            bytes=response.data, byteorder="little", signed=False
                        )
                    )
                )
            except AssertionError as err:
                # Type request for 'Onboard I/O Device' device returns an error
                # e.g. the CX7000 will return ErrorCode.ADSERR_DEVICE_INVALIDINTERFACE
                logger.warning(
                    f"Device {id} will be ignored as not an EtherCAT Master ({err})"
                )
                types.append(DeviceType(0))
                continue

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
            response = await self._ads_command(
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
            response = await self._ads_command(
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
                response = await self._ads_command(
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
            response = await self._ads_command(
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
            response = await self._ads_command(
                AdsReadRequest.read_slave_count(),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            slave_counts.append(
                int.from_bytes(bytes=response.data, byteorder="little", signed=False)
            )

        return slave_counts

    async def _get_slaves_crc_counters(
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
        slaves_crc_counters: Sequence[Sequence[np.uint32]] = []
        for netid, slave_count in zip(dev_netids, dev_slave_counts, strict=True):
            response = await self._ads_command(
                AdsReadRequest.read_slaves_crc(slave_count),
                netid=netid,
                port=ADS_MASTER_PORT,
            )
            slaves_crc = np.frombuffer(
                response.data,
                dtype=np.uint32,
                count=slave_count,
            )
            slaves_crc_counters.append(slaves_crc.tolist())

        return slaves_crc_counters

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
            response = await self._ads_command(
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
                logger.debug(f"READING slave: address={address} ...")
                response = await self._ads_command(
                    AdsReadRequest.read_slave_identity(address),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                logger.debug(
                    f"READ slave: address={address}, response={{response.data.hex()}}"
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
                response = await self._ads_command(
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
                response = await self._ads_command(
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
                response = await self._ads_command(
                    AdsReadRequest.read_slave_states(address),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                states.append(SlaveState.from_bytes(response.data))
            slave_states.append(states)

        return slave_states

    async def _get_slave_crcs(
        self,
        dev_netids: Sequence[AmsNetId],
        dev_slave_addresses: Sequence[Sequence[np.uint16]],
    ) -> Sequence[Sequence[SlaveCRC]]:
        """
        Get the detailed CRC error counters of all slaves for each EtherCAT device.

        :param dev_netids: a list comprising the netid string of all registered devices
        :param dev_slave_addresses: a list comprising the EtherCAT addresses of the
            slave terminals on all devices

        :returns: a list comprising a list of slave crcs for each EtherCAT device
        """
        slave_crcs: Sequence[Sequence[SlaveCRC]] = []
        for netid, slave_addresses in zip(dev_netids, dev_slave_addresses, strict=True):
            crcs: Sequence[SlaveCRC] = []
            for address in slave_addresses:
                response = await self._ads_command(
                    AdsReadRequest.read_slave_crc(address),
                    netid=netid,
                    port=ADS_MASTER_PORT,
                )
                # Padding is required for the communication ports which aren't used.
                crcs.append(SlaveCRC.from_bytes(response.data.ljust(32, b"\0")))
            slave_crcs.append(crcs)

        return slave_crcs

    async def _make_slave_objects(
        self,
        dev_ids: Sequence[int],
        dev_slave_types: Sequence[Sequence[str]],
        dev_slave_names: Sequence[Sequence[str]],
        dev_slave_addresses: Sequence[Sequence[np.uint16]],
        dev_slave_identities: Sequence[Sequence[IOIdentity]],
        dev_slave_states: Sequence[Sequence[SlaveState]],
        dev_slave_crcs: Sequence[Sequence[SlaveCRC]],
    ) -> Sequence[Sequence[IOSlave]]:
        """
        Create custom slave objects from slave specific parameters.

        :param dev_ids: a list of configured EtherCAT devices
        :param dev_slave_types: a list of slave type arrays for each EtherCAT device
        :param dev_slave_names: a list of slave name arrays for each EtherCAT device
        :param dev_slave_identities: a list of slave identitie arrays for each device
        :param dev_slave_addresses: a list of slave address arrays for each device

        :returns: a list comprising an array of the slave objects configured on each
            EtherCAT device
        """
        assert len(dev_ids) == len(dev_slave_addresses), (
            "Registered device counts don't match."
        )
        dev_slave_parent_ids: Sequence[Sequence[int]] = []
        for i in range(len(dev_ids)):
            num_slaves = len(dev_slave_addresses[i])
            dev_slave_parent_ids.append([dev_ids[i] for _ in range(num_slaves)])

        dev_slaves: Sequence[Sequence[IOSlave]] = []
        for (
            dev_slave_parent_id,
            dev_slave_type,
            dev_slave_name,
            dev_slave_addr,
            dev_slave_identity,
            dev_slave_state,
            dev_slave_crc,
        ) in list(
            zip(
                dev_slave_parent_ids,
                dev_slave_types,
                dev_slave_names,
                dev_slave_addresses,
                dev_slave_identities,
                dev_slave_states,
                dev_slave_crcs,
                strict=True,
            )
        ):
            slaves = [
                IOSlave(*tpl)
                for tpl in list(
                    zip(
                        dev_slave_parent_id,
                        dev_slave_type,
                        dev_slave_name,
                        dev_slave_addr,
                        dev_slave_identity,
                        dev_slave_state,
                        dev_slave_crc,
                        strict=True,
                    )
                )
            ]
            dev_slaves.append(slaves)

        return dev_slaves

    async def get_ethercat_master_device(self):
        """
        Introspect the IO server for the registered Master device.
        Any device which cannot follow the same introspection protocol \
            as the Master device is filtered out (e.g. the CX7000 Onboard I/O device).

        :returns: a tuple comprising a list of device ids and a list of device types
        """
        dev_ids = await self._get_device_ids(self.ioserver.num_devices)
        dev_types = await self._get_device_types(dev_ids)

        # Filter the non-Master devices:
        ids: Sequence[int] = [
            dev_ids[i]
            for i, tp in enumerate(dev_types)
            if tp != DeviceType.IODEVICETYPE_INVALID
        ]
        if len(ids) != len(dev_ids):
            logger.warning(
                "EtherCAT devices introspection was hacked. "
                + "Incompatible I/O devices have been omitted."
            )
            logger.debug(f"Initial list of device ids: {dev_ids}")
            logger.debug(f"Initial list of device types: {dev_types}")
            dev_ids = ids
            types: Sequence[DeviceType] = [
                type for type in dev_types if type != DeviceType.IODEVICETYPE_INVALID
            ]
            dev_types = types
            assert len(dev_ids) == len(dev_types), (
                "Device count mismatch for id and type parameters"
            )

        return dev_ids, dev_types

    async def _get_ethercat_devices(self) -> dict[SupportsInt, IODevice]:
        """
        Get information about the EtherCAT devices registered with the IO server.

        :returns: a sequence of available EtherCAT devices
        """
        devices: dict[SupportsInt, IODevice] = {}
        try:
            dev_ids, dev_types = await self.get_ethercat_master_device()
            logger.debug(f"List of device ids: {dev_ids}")
            logger.debug(f"List of device types: {dev_types}")

            dev_names = await self._get_device_names(dev_ids)
            logger.debug(f"List of device names: {dev_names}")

            dev_netids = await self._get_device_netids(dev_ids)
            logger.debug(f"List of device netids: {dev_netids}")

            dev_identities = await self._get_device_identities(dev_netids)
            logger.debug(f"List of device identities: {dev_identities}")

            dev_frames = await self._get_device_frame_counters(dev_netids)
            logger.debug(f"List of device frame counters at start: {dev_frames}")

            dev_slave_counts = await self._get_slave_count(dev_netids)
            logger.debug(f"List of device slave counts: {dev_slave_counts}")

            dev_slave_crc_counters = await self._get_slaves_crc_counters(
                dev_netids, dev_slave_counts
            )
            logger.debug(
                f"List of device slave CRC counters at start: {dev_slave_crc_counters}"
            )

            dev_slave_addresses = await self._get_slave_addresses(
                dev_netids, dev_slave_counts
            )
            logger.debug(f"List of device slave addresses: {dev_slave_addresses}")

            dev_slave_identities = await self._get_slave_identities(
                dev_netids, dev_slave_addresses
            )
            logger.debug(f"List of device slave identities: {dev_slave_identities}")

            dev_slave_types = await self._get_slave_types(
                dev_netids,
                dev_slave_counts,
            )
            logger.debug(f"List of device slave types: {dev_slave_types}")

            dev_slave_names = await self._get_slave_names(
                dev_netids,
                dev_slave_counts,
            )
            logger.debug(f"List of device slave names: {dev_slave_names}")

            dev_slave_states = await self._get_slave_states(
                dev_netids,
                dev_slave_addresses,
            )
            logger.debug(f"List of device slave states at start: {dev_slave_states}")

            dev_slave_crcs = await self._get_slave_crcs(
                dev_netids,
                dev_slave_addresses,
            )
            logger.debug(f"List of device slave crcs at start: {dev_slave_crcs}")

            dev_slaves = await self._make_slave_objects(
                dev_ids,
                dev_slave_types,
                dev_slave_names,
                dev_slave_addresses,
                dev_slave_identities,
                dev_slave_states,
                dev_slave_crcs,
            )
            logger.debug(f"List of device slaves: {dev_slaves}")

            for params in list(
                zip(
                    dev_ids,
                    dev_types,
                    dev_names,
                    dev_netids,
                    dev_identities,
                    dev_frames,
                    dev_slave_counts,
                    dev_slave_states,
                    dev_slave_crc_counters,
                    dev_slaves,
                    strict=True,
                )
            ):
                device = IODevice(*params)
                devices[device.id] = device

        except AssertionError as err:
            logger.critical(f"Problem during EtherCAT devices introspection -> {err}")

        return devices

    def _print_device_chain(self, device_id: SupportsInt) -> None:
        """
        Provide a console visualization of the EtherCAT chain for a given device.

        :param device_id: the id value of the EtherCAT device
        """
        print("\n============ Active EtherCAT devices ============")
        print("|")
        print(f"|----EtherCAT Master '{self._ecdevices[device_id].name}'")
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

    async def _get_ethercat_chains(self) -> None:
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
            node_count = 0
            node, node_position = 0, 0
            for slave in device.slaves:
                if slave.type == "EK1100":
                    slave.category = IONodeType.Coupler
                    node_count += 1
                    node += 1
                    node_position = 0
                slave.loc_in_chain = ChainLocation(node, node_position)
                node_position += 1
            device.node_count = node_count
            self._print_device_chain(device.id)

    def _generate_system_tree(self) -> IOTreeNode:
        """
        Generate a tree structure from the components available on the EtherCAT system.
        The root node is the I/O server whose child nodes are the EtherCAT devices.
        Each device node may comprise either coupler terminals as child nodes or
        slave terminals as leaf nodes.
        Coupler nodes may comprise slave terminals as leaf nodes.

        :returns: the root node of the EtherCAT system tree
        """
        server_node = IOTreeNode(self.ioserver)
        for device in self._ecdevices.values():
            parent_path = deepcopy(server_node.path)
            device_node = IOTreeNode(device, parent_path)
            server_node.add_child(device_node)
            coupler_node = None
            for slave in device.slaves:
                if slave.type == "EK1100":
                    parent_path = deepcopy(device_node.path)
                    coupler_node = IOTreeNode(slave, parent_path)
                    device_node.add_child(coupler_node)
                else:
                    if coupler_node is not None:
                        parent_path = deepcopy(coupler_node.path)
                        coupler_node.add_child(IOTreeNode(slave, parent_path))
                    else:
                        parent_path = deepcopy(device_node.path)
                        device_node.add_child(IOTreeNode(slave, parent_path))
        logger.debug(f"EtherCAT system tree has {server_node.tree_height()} levels.")

        return server_node

    async def introspect_io_server(self) -> None:
        """
        Gather information about the EtherCAT I/O server (inc. name, version and build),
        identify the registered EtherCAT devices and associated slaves,
        and print out to the console the EtherCAT device chains.

        The EtherCAT Master Device is assumed to be the first device \
            in the list of devices registered with the I/O server.
        """
        self.ioserver: IOServer = await self._get_io_server()
        logger.info(
            f"ADS device info: \tname={self.ioserver.name}, "
            + f"version={self.ioserver.version}, build={self.ioserver.build}"
        )
        logger.info(f"Number of I/O devices: {self.ioserver.num_devices}")
        assert self.ioserver.num_devices != 0, (
            "No device is registered with the I/O server"
        )

        self._ecdevices = await self._get_ethercat_devices()
        logger.info(f"Available I/O devices: {self._ecdevices}")

        self.master_device_id = next(iter(self._ecdevices))
        logger.info(
            f"Device id {self.master_device_id} registered as EtherCAT Master device."
        )

        await self._get_ethercat_chains()

    #################################################################
    ### I/O MONITORS: STATES, COUNTERS, FRAMES ----------------------
    #################################################################

    async def _get_ioserver_states(self) -> tuple[np.uint16, np.uint16]:
        """
        Read the ADS status of the I/O server.

        :returns: a tuple comprising both the ads link status and the ads device status
        """
        return await self._get_states(
            netid=self.__target_ams_net_id, port=IO_SERVER_PORT
        )

    async def _get_states(
        self, netid: AmsNetId, port: int
    ) -> tuple[np.uint16, np.uint16]:
        """
        Read the ADS status.

        :param netid: the ams netid of the service to query the state from
        :param port: the ams port of the service to query the state from

        :returns: a tuple comprising both the ads link status and the ads device status
        """
        response = await self._ads_command(
            AdsReadStateRequest(), netid=netid, port=port
        )

        return response.ads_state, response.device_state

    async def check_ads_states(self) -> None:
        """
        Check that the ADS communication status with the IO server and devices is valid.

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )
        try:
            io_adsstate, io_devstate = await self._get_ioserver_states()
            logger.debug(f"IO states: ads={io_adsstate}, dev={io_devstate}")
            assert io_adsstate == AdsState.ADSSTATE_RUN, "IO device is not in run mode"

            for device in self._ecdevices.values():
                ec_adsstate, ec_devstate = await self._get_states(
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                logger.debug(
                    f"DEV{device.id} states: ads={ec_adsstate}, dev={ec_devstate}"
                )
                assert ec_devstate == SlaveLinkState.SLAVE_LINK_STATE_OK, (
                    "ADS link to EtherCAT device is not good"
                )

        except AssertionError as err:
            logger.critical(f"Problem during ADS communication status check -> {err}")
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
            response = await self._ads_command(
                AdsReadRequest.read_slave_states(slave_address),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            state = SlaveState.from_bytes(response.data)
            assert state.ecat_state == SlaveStateMachine.SLAVE_STATE_OP, (
                "A slave terminal is not in operational state"
            )

            assert state.link_status == SlaveLinkState.SLAVE_LINK_STATE_OK, (
                "EtherCAT link for a slave terminal isn't in a good state"
            )

        except AssertionError as err:
            logger.critical(
                f"Problem during status check of an EtherCAT slave -> {err}"
            )
            raise

        return state

    async def get_device_slaves_states(self, device_id: int) -> Sequence[SlaveState]:
        """
        Read the current states values of all slaves for a given EtherCAT device.

        :param device_id: the id of the EtherCAT device which the slaves belong to

        :returns: a list of SlaveState objects corresponding to each slave terminal
        """
        device = self._ecdevices[device_id]
        response = await self._ads_command(
            AdsReadRequest.read_slaves_states(device.slave_count),
            netid=device.netid,
            port=ADS_MASTER_PORT,
        )
        return np.frombuffer(
            response.data,
            dtype=SlaveState,
            count=int(device.slave_count),
        ).tolist()

    def update_device_slaves_states(
        self,
        device_id: int,
        slaves_states: Sequence[SlaveState],
    ) -> None:
        """
        Update the states values for each registered slave terminal
        (each slave comprises two state readings: machine state and link status)
        Also check whether all slave terminals are currently in a valid state.

        param device_id: the id of the EtherCAT device which the slave belongs to
        param slaves_states: a container with the current slave terminal states
        """
        device = self._ecdevices[device_id]
        # Only update slave attributes if the states values have changed.
        if not np.array_equal(device.slaves_states, slaves_states):
            device.slaves_states = slaves_states
            logger.warning(
                f"{device.name}: slaves states have changed and been updated."
            )

            for states, slave in list(
                zip(
                    device.slaves_states,
                    device.slaves,
                    strict=True,
                )
            ):
                slave.states.ecat_state = states.ecat_state
                slave.states.link_status = states.link_status

            self.check_slaves_states_validity(device.slaves, device.slaves_states)

    def check_slaves_states_validity(
        self, slaves: Sequence[IOSlave], slave_states: Sequence[SlaveState]
    ) -> bool:
        """
        Flag any slave terminal which is not operating as expected.

        :param slaves: the list of slave terminals registered with the EtherCAT device
        :param slave_states: a container with the current states of the slave terminals

        :returns: true if the states of the slave terminals are ok, false otherwise
        """

        status = True
        states = np.array(slave_states, dtype=SlaveState)
        if not np.all(states["ecat_state"] == SlaveStateMachine.SLAVE_STATE_OP):
            status = False
            bad_ecat = np.nonzero(
                states["ecat_state"] != SlaveStateMachine.SLAVE_STATE_OP
            )[0]
            assert bad_ecat.size
            for idx in bad_ecat:
                slave: IOSlave = slaves[int(idx)]
                logger.critical(
                    f"Slave terminal '{slave.name}' isn't in operational state."
                )

        if not np.all(states["link_status"] == SlaveLinkState.SLAVE_LINK_STATE_OK):
            status = False
            bad_link = np.nonzero(
                states["link_status"] != SlaveLinkState.SLAVE_LINK_STATE_OK
            )[0]
            assert bad_link.size
            for idx in bad_link:
                slave: IOSlave = slaves[int(idx)]
                logger.critical(
                    f"EtherCAT link for slave terminal '{slave.name}' isn't "
                    + "in a good state."
                )

        return status

    async def poll_states(
        self,
    ) -> None:
        """
        Read the current ADS state of the EtherCAT devices and their associated slaves.
        """
        while not self._ecdevices:
            logger.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                # Check the device operation state.
                dev_response = await self._ads_command(
                    AdsReadRequest.read_device_state(),
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                dev_state = int.from_bytes(
                    bytes=dev_response.data, byteorder="little", signed=False
                )
                logger.debug(f"{device.name} state: {dev_state}")
                assert dev_state == DeviceStateMachine.DEVSTATE_OP, (
                    f"{device.name} is not operational, {DeviceStateMachine(dev_state)}"
                )

                # Check the slaves operation states.
                slave_response = await self._ads_command(
                    AdsReadRequest.read_slaves_states(device.slave_count),
                    netid=device.netid,
                    port=ADS_MASTER_PORT,
                )
                states = np.frombuffer(
                    slave_response.data,
                    dtype=[("ecat_state", np.uint8), ("link_status", np.uint8)],
                    count=int(device.slave_count),
                )

                # If any slave terminal is not operating as expected, update its status.
                if not np.all(states["ecat_state"] == SlaveStateMachine.SLAVE_STATE_OP):
                    bad_ecat = np.nonzero(
                        states["ecat_state"] != SlaveStateMachine.SLAVE_STATE_OP
                    )[0]
                    assert bad_ecat.size
                    for idx in bad_ecat:
                        slave: IOSlave = (device.slaves)[int(idx)]
                        logger.critical(
                            f"Slave terminal '{slave.name}' isn't in operational state."
                        )
                        slave.states.ecat_state = states["ecat_state"][idx]
                if not np.all(
                    states["link_status"] == SlaveLinkState.SLAVE_LINK_STATE_OK
                ):
                    bad_link = np.nonzero(
                        states["link_status"] != SlaveLinkState.SLAVE_LINK_STATE_OK
                    )[0]
                    assert bad_link.size
                    for idx in bad_link:
                        slave: IOSlave = (device.slaves)[int(idx)]
                        logger.critical(
                            f"EtherCAT link for slave terminal '{slave.name}' isn't "
                            + "in a good state."
                        )
                        slave.states.link_status = states["link_status"][idx]

        except AssertionError as err:
            logger.critical(f"Problem polling an EtherCAT device state -> {err}")
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
            response = await self._ads_command(
                AdsReadRequest.read_slave_crc(slave_address),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            # Padding is required in case some of the communication ports aren't used.
            return SlaveCRC.from_bytes(response.data.ljust(32, b"\0"))

        except AssertionError as err:
            logger.critical(f"Problem reading a slave CRC value -> {err}")
            raise

    async def get_slave_crc_error_counters(
        self, device_id: SupportsInt, address: SupportsInt
    ) -> SlaveCRC:
        """
        Read the current cyclic redundancy check error counters for a given terminal.

        :param device_id: the id of the EtherCAT device which the terminal belongs to
        :param address: EtherCAT address of the terminal

        :returns: the EtherCAT terminal's CRC error counters
        """
        response = await self._ads_command(
            AdsReadRequest.read_slave_crc(address),
            netid=self._ecdevices[device_id].netid,
            port=ADS_MASTER_PORT,
        )
        # Padding is required for the communication ports which aren't used.
        return SlaveCRC.from_bytes(response.data.ljust(32, b"\0"))

    async def get_device_slaves_crcs(self, device_id: int) -> Sequence[np.uint32]:
        """
        Read the current error sum counter values of the slaves' CRC for a given \
            EtherCAT device.

        :param device_id: the id of the EtherCAT device which the slave belongs to

        :returns: a list of slave crc error sum counters for the EtherCAT device
        """
        device = self._ecdevices[device_id]
        response = await self._ads_command(
            AdsReadRequest.read_slaves_crc(device.slave_count),
            netid=device.netid,
            port=ADS_MASTER_PORT,
        )
        return np.frombuffer(
            response.data,
            dtype=np.uint32,
            count=int(device.slave_count),
        ).tolist()

    def update_device_slaves_crcs(
        self, device_id: int, slaves_crcs: Sequence[np.uint32]
    ) -> None:
        """
        Update the crc error sum counter value for each slave terminal \
            registered with a given EtherCAT device.

        param device_id: the id of the EtherCAT device which the slave belongs to
        param slaves_crcs: a list with the slave crc error sum counters for the device
        """
        device = self._ecdevices[device_id]
        # Only update slave attributes if the crc values have changed.
        if not np.array_equal(device.slaves_crc_counters, slaves_crcs):
            device.slaves_crc_counters = slaves_crcs
            logger.warning(
                f"{device.name}: slave CRC sum counters have changed and been updated."
            )

            for crc, slave in list(
                zip(device.slaves_crc_counters, device.slaves, strict=True)
            ):
                slave.crc_error_sum = crc

    async def poll_crc_counters(self) -> None:
        """
        Read the current error sum counter values of the slaves' CRC for each device.
        """
        while not self._ecdevices:
            logger.warning(
                "... waiting for EtherCAT devices initialisation before "
                + "polling CRC counters"
            )
            await asyncio.sleep(1)

        for device in self._ecdevices.values():
            device_id = int(device.id)
            slaves_crc = await self.get_device_slaves_crcs(device_id)
            self.update_device_slaves_crcs(device_id, slaves_crc)

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
            response = await self._ads_command(
                AdsReadRequest.read_device_frame_counters(),
                netid=device.netid,
                port=ADS_MASTER_PORT,
            )
            device.frame_counters = DeviceFrames.from_bytes(response.data)

        except AssertionError as err:
            logger.critical(f"Problem reading a device frame counter value -> {err}")
            raise

    async def poll_frame_counters(self) -> None:
        """
        Get the current frame counter values of all registered EtherCAT devices.
        """
        while not self._ecdevices:
            logger.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                await self.get_device_frames(device.id)
                logger.debug(
                    f"{device.name} frame counters: "
                    + f"cyclic_sent={device.frame_counters.cyclic_sent}, "
                    + f"cyclic_lost={device.frame_counters.cyclic_lost}, "
                    + f"acyclic_sent={device.frame_counters.acyclic_sent}, "
                    + f"acyclic_lost={device.frame_counters.acyclic_lost}, "
                )
        except AssertionError as err:
            logger.critical(f"Problem polling device frame counter values -> {err}")
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
            logger.critical(f"Problem resetting a device frame counter value -> {err}")
            raise

    async def reset_frame_counters(self) -> None:
        """
        Reset the frame counters of all EtherCAT devices registered with the I/O server.
        """
        while not self._ecdevices:
            logger.warning(
                "... waiting for EtherCAT devices initialisation before polling states"
            )
            await asyncio.sleep(1)
        try:
            for device in self._ecdevices.values():
                await self.reset_device_frames(device.id)
                logger.info(f"Frame counters for {device.name} have been reset.")
        except AssertionError as err:
            logger.critical(f"Problem resetting device frame counter values -> {err}")
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
        # TO DO: ideally, a device would be defined with its ads port info and netid
        # ads_port = self._ecdevices[device_id].port

        # Get the length of the symbol table
        response = await self._ads_command(
            AdsReadRequest.get_length_symbol_table(),
            netid=self.__target_ams_net_id,
            port=self.__target_ams_port,
            # to be updated if device ads port info can be accessed somehow
        )
        symbol_table = AdsSymbolTableInfo.from_bytes(response.data)

        # Get a list of the defined symbol nodes
        response = await self._ads_command(
            AdsReadRequest.fetch_symbol_table(symbol_table.table_length),
        )
        nodes = self._parse_symbol_table_entry(
            device_id, int(symbol_table.symbol_count), response.data
        )

        # Get a list of the available symbols
        symbols: list[AdsSymbol] = []
        for node in nodes:
            symbols.extend(symbol_lookup(node))

        # Adjust the device symbol names to include the device name as prefix
        # Unfortunately, counter correction is required in 'add_device_notification()'
        device_name = self._ecdevices[device_id].name
        for symbol in symbols:
            if symbol.name.startswith("Inputs") or symbol.name.startswith("Outputs"):
                symbol.name = f"{device_name}.{symbol.name}"

        self._ecsymbols[device_id] = symbols
        logger.info(
            f"{symbol_table.symbol_count} entries in the symbol table returned "
            + f"a total of {len(symbols)} available symbols."
        )

    async def get_all_symbols(self) -> dict[SupportsInt, Sequence[AdsSymbol]]:
        """
        Get all ADS symbols available on the EtherCAT I/O server.

        :raises ValueError: if no EtherCAT device is defined with the ADS client
        """
        if not self._ecdevices:
            raise ValueError(
                "EtherCAT devices have not been defined with the ADS client yet."
            )

        # to be removed if device ads port info can be accessed somehow
        assert len(self._ecdevices) == 1, (
            "Only one EtherCAT device is supported for the moment."
        )
        dev_id = next(iter(self._ecdevices.keys()))

        # for id, device in self._ecdevices.items():
        await self.get_device_symbols(dev_id)

        return self._ecsymbols

    async def read_ads_symbol(self, symbol: AdsSymbol) -> tuple[str, npt.NDArray]:
        """
        Read the value of an ADS symbol configured with an EtherCAT device.

        :param symbol: the ADS symbol to read

        :returns: a tuple comprising the symbol name and its current value
        """
        logger.debug(f"Reading current value of symbol '{symbol.name}'.")
        response = await self._ads_command(
            AdsReadRequest.read_symbol(symbol.group, symbol.offset, symbol.nbytes),
        )
        return (
            symbol.name,
            np.frombuffer(response.data, symbol.datatype, count=1),
        )

    async def write_ads_symbol(self, symbol: AdsSymbol, value: Any) -> bool:
        """
        Write a value to an ADS symbol configured with an EtherCAT master device.
        The command is ignored if the requested value to set is invalid.

        :param symbol: the ADS symbol to write to
        :param value: the value to write to the ADS symbol
        """
        logger.debug(f"Writing value {value} to symbol '{symbol.name}'.")
        if isinstance(value, Sequence) and not (len(value) == symbol.size):
            logger.error(
                f"Symbol Write Value Error: value for '{symbol.name}' expects a "
                + f"collection of {symbol.size} elements, got {len(value)} instead."
            )
        try:
            val = np.array(value, dtype=symbol.datatype)
            await self._ads_command(
                AdsWriteRequest.write_symbol(symbol.group, symbol.offset, val.tobytes())
            )
            return True
        except ValueError:
            logger.error(
                f"Symbol Write Type Error: wrong value type provided for {symbol.name}:"
                + f" expected '{symbol.dtype}' but got '{type(value)}'."
            )
        return False

    async def readwrite_ads_symbol(
        self, symbol: AdsSymbol, value: Any
    ) -> tuple[str, npt.NDArray]:
        """
        Read the value of an ADS symbol configured with the EtherCAT master device,
        then write a new value to it.

        :param symbol: the ADS symbol to read and write to
        :param value: the value to write to the ADS symbol

        :returns: a tuple comprising the symbol name and its current value
        """
        logger.debug(
            f"Reading current value of symbol '{symbol.name}' "
            + f"and writing new value {value}."
        )
        if isinstance(value, Sequence) and not (len(value) == symbol.size):
            logger.error(
                f"Symbol ReadWrite Value Error: value for '{symbol.name}' expects a "
                + f"collection of {symbol.size} elements, got {len(value)} instead."
            )
        try:
            new_val = np.array(value, dtype=symbol.datatype)
            response = await self._ads_command(
                AdsReadWriteRequest.readwrite_symbol(
                    symbol.group, symbol.offset, symbol.nbytes, new_val.tobytes()
                )
            )
            old_val = np.frombuffer(response.data, symbol.datatype, count=1)
            return (
                symbol.name,
                old_val,
            )
        except ValueError:
            logger.error(
                f"Symbol Write Type Error: wrong value type provided for {symbol.name}:"
                + f" expected '{symbol.dtype}' but got '{type(value)}'."
            )
        logger.warning(
            f"ReadWrite command failed on symbol '{symbol.name}'. "
            + "Reverting to read only."
        )
        return await self.read_ads_symbol(symbol)

    def _get_sumread_responses(
        self, sum_data: bytes, read_lengths: Sequence[np.uint32]
    ) -> Sequence[AdsReadResponse]:
        """
        Parse a general ADS SumRead response into individual AdsReadResponse objects.

        :param sum_data: the data byte stream from the ADS SumRead response
        :param read_lengths: the length of the data in bytes for each expected \
            ADSReadResponse object

        :returns: a list of AdsReadResponse objects
        """
        responses = []
        s_err = np.dtype(ErrorCode).itemsize
        start = 0
        num_responses = len(read_lengths)
        offset = s_err * num_responses
        for length in read_lengths:
            body = (
                sum_data[start : start + s_err]
                + length.tobytes()
                + sum_data[offset : offset + length]
            )
            responses.append(AdsReadResponse.from_bytes(body))
            start = start + s_err
            offset = offset + length
        return responses

    async def sumread_ads_symbols(
        self, symbols: Sequence[AdsSymbol]
    ) -> dict[str, npt.NDArray]:
        """
        Used as a container in which multiple AdsRead subcommands are transported
        in the same ADS stream.

        :param symbols: a list of ADS symbols to read

        :returns: a dictionary mapping the symbol and its associated read value
        """
        read_subcommands: list[AdsReadRequest] = []
        for symbol in symbols:
            logger.debug(f"SUM read symbol: {symbol.name}")
            read_subcommands.append(
                AdsReadRequest.read_symbol(symbol.group, symbol.offset, symbol.nbytes),
            )

        sum_response = await self._ads_command(
            AdsReadWriteRequest.sumread_symbols(
                read_subcommands,
            )
        )
        read_lengths = [request.read_length for request in read_subcommands]
        read_responses = self._get_sumread_responses(sum_response.data, read_lengths)

        zipped = list(zip(symbols, read_responses, strict=True))

        reads = {}
        for symbol, read in zipped:
            if not (read.result == ErrorCode.ERR_NOERROR):
                logger.error(
                    f"ADS Read error with '{symbol.name}': {ErrorCode(read.result)}"
                )
            reads[symbol.name] = np.frombuffer(read.data, symbol.datatype, count=1)

        return reads

    def _get_sumwrite_responses(self, sum_data: bytes) -> Sequence[AdsWriteResponse]:
        """
        Parse a general ADS SumWrite response into individual AdsWriteResponse objects.

        :param sum_data: the data byte stream from the ADS SumWrite response

        :returns: a list of AdsWriteResponse objects
        """
        n = np.dtype(ErrorCode).itemsize

        return [
            AdsWriteResponse.from_bytes(sum_data[i : i + n])
            for i in range(0, len(sum_data), n)
        ]

    async def sumwrite_ads_symbols(
        self, targets: Sequence[tuple[AdsSymbol, Any]]
    ) -> dict[str, bool]:
        """
        Used as a container in which multiple AdsWrite subcommands are transported \
            in the same ADS stream.
        The write command is ignored for any symbol whose requested value is invalid.

        :param targets: a list of tuples, each comprising an ADS symbol and the \
            associated value to write

        :returns: a dictionary mapping the success of the write command to each symbol
        """
        processed_writes = len(targets)
        processed_targets = targets
        write_status = {}
        write_subcommands: list[AdsWriteRequest] = []

        for symbol, value in targets:
            logger.debug(f"SUM write symbol: {symbol.name}, {value}")
            if isinstance(value, Sequence) and not (len(value) == symbol.size):
                logger.error(
                    f"Symbol Write Value Error: value for '{symbol.name}' expects a "
                    + f"collection of {symbol.size} elements, got {len(value)} instead."
                )
                processed_writes -= 1
                processed_targets = filter(lambda target: target[0] != symbol, targets)
                write_status[symbol.name] = False
                continue

            try:
                val = np.array(value, dtype=symbol.datatype)
                write_subcommands.append(
                    AdsWriteRequest.write_symbol(
                        symbol.group, symbol.offset, val.tobytes()
                    ),
                )
            except ValueError:
                logger.error(
                    f"Write error: wrong value type provided for {symbol.name}: "
                    + f"expected '{symbol.dtype}' but got '{type(value)}'."
                )
                processed_writes -= 1
                processed_targets = filter(lambda target: target[0] != symbol, targets)
                write_status[symbol.name] = False
                continue

        assert write_subcommands, "No valid AdsWrite subcommand to process."
        sum_response = await self._ads_command(
            AdsReadWriteRequest.sumwrite_symbols(
                write_subcommands,
            )
        )
        write_responses = self._get_sumwrite_responses(sum_response.data)
        assert len(write_responses) == processed_writes, (
            "Mismatch between number of 'SumWrite' commands and supplied responses."
        )

        zipped = list(zip(processed_targets, write_responses, strict=True))

        for target, response in zipped:
            assert response.result == ErrorCode.ERR_NOERROR, (
                f"ADS Write error with '{target[0].name}': \
                    {ErrorCode(response.result)}"
            )
            write_status[target[0].name] = True

        return write_status

    def _get_sumreadwrite_responses(
        self, sum_data: bytes, read_lengths: Sequence[np.uint32]
    ) -> Sequence[AdsReadWriteResponse]:
        """
        Parse a general ADS SumReadWrite response into individual
        AdsReadWriteResponse objects.

        :param sum_data: the data byte stream from the ADS SumReadWrite response

        :returns: a list of AdsReadWriteResponse objects
        """
        responses = []
        l_err = np.dtype(ErrorCode).itemsize
        l_data = np.dtype(np.uint32).itemsize
        start = 0
        num_responses = len(read_lengths)
        offset = (l_err + l_data) * num_responses
        for length in read_lengths:
            assert sum_data[start + l_err : start + l_err + l_data] == length, (
                f"Mismatch between read lengths: expected {length} bytes, \
                    got {sum_data[start + l_err : start + l_err + l_data]} bytes"
            )
            body = (
                sum_data[start : start + l_err + l_data]
                + sum_data[offset : offset + length]
            )
            responses.append(AdsReadWriteResponse.from_bytes(body))
            start = start + l_err + l_data
            offset = offset + length
        return responses

    async def sumreadwrite_symbols(
        self, targets: Sequence[tuple[AdsSymbol, Any]]
    ) -> dict[str, npt.NDArray]:
        """
        Used as a container in which multiple AdsReadWrite subcommands are transported \
            in the same ADS stream.

        :param targets: a list of tuples, each comprising an ADS symbol and \
            the associated value to write

        :returns: a dictionary mapping the current read value of the symbols \
            which have successfully been written to
        """
        processed_readwrites = len(targets)
        processed_targets = targets
        readwrite_status = {}
        rw_subcommands: list[AdsReadWriteRequest] = []
        for symbol, value in targets:
            logger.debug(f"SUM readwrite symbol: {symbol.name}, {value}")
            if isinstance(value, Sequence) and not (len(value) == symbol.size):
                logger.error(
                    f"Symbol ReadWrite Value Error: value for '{symbol.name}' "
                    + f"expects a collection of {symbol.size} elements, "
                    + f"got {len(value)} instead."
                )
                processed_readwrites -= 1
                processed_targets = filter(lambda target: target[0] != symbol, targets)
                readwrite_status[symbol.name] = False
                continue

            try:
                val = np.array(value, dtype=symbol.datatype)
                rw_subcommands.append(
                    AdsReadWriteRequest.readwrite_symbol(
                        symbol.group, symbol.offset, symbol.nbytes, val.tobytes()
                    ),
                )
            except ValueError:
                logger.error(
                    f"ReadWrite error: wrong value type provided for {symbol.name}: "
                    + f"expected '{symbol.dtype}' but got '{type(value)}'."
                )
                processed_readwrites -= 1
                processed_targets = filter(lambda target: target[0] != symbol, targets)
                readwrite_status[symbol.name] = False
                continue

        read_lengths = [
            readwrite_request.read_length for readwrite_request in rw_subcommands
        ]

        assert rw_subcommands, "No valid AdsReadWrite subcommand to process."
        sum_response = await self._ads_command(
            AdsReadWriteRequest.sumreadwrite_symbols(
                rw_subcommands,
            )
        )
        rw_responses = self._get_sumreadwrite_responses(sum_response.data, read_lengths)
        assert len(rw_responses) == processed_readwrites, (
            "Mismatch between number of 'SumReadWrite' commands and supplied responses."
        )

        zipped = list(zip(processed_targets, rw_responses, strict=True))

        reads = {}
        for target, response in zipped:
            assert response.result == ErrorCode.ERR_NOERROR, (
                f"ADS ReadWrite error with '{target[0].name}': \
                    {ErrorCode(response.result)}"
            )
            readwrite_status[target[0].name] = True
            reads[target[0].name] = np.frombuffer(
                response.data, target[0].datatype, count=1
            )

        logger.debug(f"ReadWrite command statuses: {readwrite_status}")

        return reads

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
    ) -> np.uint32:
        """
        Subscribe to notifications from the server for a given device symbol variable.

        :param symbol: the symbol variable to subscribe to.

        :param max_delay_ms: maximum time in milliseconds after which the ads device \
            notification is called.
            The smallest possible value is the task cycle time

        :param cycle_time_ms: periodic time slice in milliseconds at which the ads \
            server checks if the value changes.
            If 0, then the server will check the value with every task cycle

        :returns: the notification handle assigned to the symbol variable
        """
        assert symbol in self._ecsymbols[symbol.parent_id], (
            f"Symbol '{symbol.name}' not found in the symbol list \
                of device {self._ecdevices[symbol.parent_id].name}."
        )

        variable_handle = self.__variable_handles.get(symbol.name, None)
        if variable_handle is None:
            # Adjust the stored device symbol names, i.e. remove the device name prefix
            device_name = self._ecdevices[symbol.parent_id].name
            if symbol.name.startswith(f"{device_name}."):
                symbol_name = symbol.name.split(".", 1)[1]
            else:
                symbol_name = symbol.name
            # Add the variable handle to the dictionary
            variable_handle = await self.get_handle_by_name(name=symbol_name)
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
        logger.debug(
            f"Notification subscription for Device{symbol.parent_id} symbol "
            + f"'{symbol.name}' completed with handle {symbol.handle}."
        )

        self.__notif_templates = {}

        return response.handle

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

        logger.info(
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
                f"{symbol.name} notifications are not registered as an active "
                + "ADS subscription."
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
        logger.debug(
            f"Deleted notification handle {symbol.handle} for symbol '{symbol.name}' "
            + f"on device '{self._ecdevices[symbol.parent_id].name}'"
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
                logger.error(
                    f"Notification deletion for {symbol.name} failed -> {err}."
                )

        if err_counter:
            logger.error(
                f"Failed to unsubscribe notifications for {err_counter} "
                + f"symbols out of {len(all_symbols)}."
            )
        else:
            logger.info(
                f"Successfully deleted client subscription to {len(all_symbols)} "
                + "symbol notifications."
            )

    def start_notification_monitor(self, flush_period: float) -> None:
        """
        Trigger the appending of received ADS notifications into the buffer and \
            enable periodic flushing.

        :param flush_period: period in seconds when the notification data is flushed \
            to a queue
        """
        self.__num_notif_streams = 0
        self.__notif_templates = {}
        self.__buffer = bytearray()
        self.__flush_notifications_task = asyncio.create_task(
            self._periodic_flush(flush_period)
        )

    def stop_notification_monitor(self) -> None:
        """
        Disable periodic flushing which will also stop the appending of received \
            ADS notifications into the buffer.
        """
        if self.__flush_notifications_task is not None:
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
                            "Flushing period is too short, "
                            + "notification data has not been initialised yet."
                        )
                        dev_id = next(iter(self._ecdevices.keys()))

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
                                self._ecdevices[dev_id].name,
                                self.__device_notification_handles,
                            )
                        else:
                            # All requested notifications are reported in a single
                            # ADS notification stream.
                            template_data = self.__notif_templates[0]
                            streams = AdsNotificationStream.from_bytes(template_data)
                            streams_dtype = streams.get_notification_dtype(
                                self._ecdevices[dev_id].name,
                                self.__device_notification_handles,
                            )

                        first_flush = False

                    # Wait for the notification buffer to be complete (i.e. includes all
                    # notifications from the cycle), then add it to the queue.
                    # Ignore process when no buffer is available,
                    # e.g. when flush period < notification cycle time
                    if not len(self.__buffer) == 0:
                        buffer = self.__buffer
                        self.__buffer = bytearray()
                        # print("TEMPLATE SIZES:")
                        # print([(k, len(v)) for k, v in self.__notif_templates.items()
                        #  ])
                        assert len(buffer) % len(template_data) == 0, (
                            "Request to flush an incomplete notification buffer "
                            + "(size mismatch)."
                        )
                        self.__notification_queue.put_nowait(
                            await self._get_notifications_from_buffer(
                                streams_dtype, buffer
                            )
                        )
                        assert streams_dtype.fields
                        logger.debug(
                            f"Notification stream added to the queue: "
                            f"qsize={self.__notification_queue.qsize()}, "
                            f"streams_nb={self.__num_notif_streams}, "
                            f"notifs_fields={len(streams_dtype.fields)}"
                        )

            except AssertionError as err:
                logger.error(f"Notification flushing error: {err}")
                self.__buffer = None
                break
            except asyncio.CancelledError:
                # Add the last notification buffer to the queue despite the flushing
                # period not having completed.
                if self.__buffer is not None:
                    buffer = self.__buffer
                    self.__buffer = None
                    self.__notification_queue.put_nowait(
                        await self._get_notifications_from_buffer(streams_dtype, buffer)
                    )
                logger.info("...periodic flushing of notifications has ended.")
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

    async def get_notifications(self, timeout: int) -> npt.NDArray:
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
                logger.debug(
                    f"Got {len(notifs)} notifications with "
                    + f"{(len(notifs.dtype.fields) - num_header_fields) // 3} "
                    + "I/O terminal values."
                )
                return notifs
        except TimeoutError as err:
            raise TimeoutError(
                f"...no notification added to the queue for the past {timeout} seconds!"
            ) from err

    # #################################################################
    # ### DEVICE CoE SETTINGS ----------------------------------------
    # #################################################################

    async def set_io_coe_parameter(
        self,
        device: IODevice | IOSlave,
        index: str,
        subindex: str,
        value: Any,
        timeout: int = 5,
    ) -> bool:
        """
        Set a CAN-over-EtherCAT parameter to a given value.

        :param device: the Master EtherCAT device or one of its slave terminal
        :param index: the CoE index assigned to the parameter (HIWORD=0xYYYY0000)
        :param subindex: the CoE subindex assigned to the parameter (LOBYTE=0x000000YY)
        :param value: the value to assign to the CoE parameter
        :param timeout: timeout value in seconds

        :returns: true if the CoE write operation was successful
        """
        if isinstance(device, IODevice):
            netid = self.__target_ams_net_id
            port = ADS_MASTER_PORT
        elif isinstance(device, IOSlave):
            netid = self._ecdevices[self.master_device_id].netid
            port = (int)(device.address)

        try:
            val = np.array(value)
            dtype = val.dtype

            async with asyncio.timeout(timeout):
                # Read existing value
                response = await self._ads_command(
                    AdsReadRequest.read_coe_value(index, subindex, dtype),
                    netid=netid,
                    port=port,
                )
                logger.debug(
                    f"Converting byte stream '{response.data.hex(' ')}' to {dtype}."
                )
                old_value = np.frombuffer(response.data, dtype)

                # Write new value
                response = await self._ads_command(
                    AdsWriteRequest.write_coe_value(
                        index,
                        subindex,
                        val.tobytes(),
                    ),
                    netid=netid,
                    port=port,
                )

                # Read new value
                response = await self._ads_command(
                    AdsReadRequest.read_coe_value(index, subindex, dtype),
                    netid=netid,
                    port=port,
                )
                logger.debug(
                    f"Converting byte stream '{response.data.hex(' ')}' to {dtype}."
                )
                new_value = np.frombuffer(response.data, dtype)

                logger.info(
                    f"{device.name}: CoE parameter at index '{index}:{subindex}' was "
                    + f"changed from value {old_value} to value {new_value}."
                )

                return True

        except ValueError:
            logger.error(
                "Write Type Error: wrong value type provided for CoE parameter "
                + f"at index '{index}:{subindex}' for device {device.name}."
            )

        except TimeoutError:
            logger.error(
                f"{device.name}:Timeout: CoE parameter at index "
                + f"'{index}:{subindex}' couldn't be modified."
            )

        return False

    # #################################################################
    # ### UTILITY METHODS (FOR TESTING) -------------------------------
    # #################################################################

    def find_slave_in_master_device(self, slave_type: str) -> None | IOSlave:
        """
        Find a slave object of the given type available on the EtherCAT Master device.

        :param slave_type: the name of the slave terminal to look for

        :returns: the slave object of the requested type or None if not available
        """
        id = self.master_device_id
        for slave in self._ecdevices[id].slaves:
            if slave_type in slave.name:
                return slave
        return None

    @staticmethod
    def _check_system(function: FuncType):
        """Confirm that devices on the EtherCAT system have been registered \
            with the CATio client."""

        async def wrapper(self, *args, **kwargs):
            if not self._ecdevices:
                logger.error("Problem with CATio client, no EtherCAT device found.")
                raise RuntimeError
            return await function(self, *args, **kwargs)

        return wrapper

    def read_device_id_from_name(self, device_name: str) -> int | None:
        """"""
        assert re.compile(r"(^([A-Z]*[a-z]*)+)(\d+)$").match(device_name) is not None, (
            "Device name format is invalid, device id cannot be found."
        )
        # return int(re.sub(r"(^([A-Z]*[a-z]*)+)", "", device_name))
        matches = re.search(r"\d+$", device_name)
        if matches:
            return int(matches.group(0))

        return None

    #################################################################
    ### API FUNCTIONS -----------------------------------------------
    #################################################################

    async def command(self, command: str, *args, **kwargs) -> Any:
        """
        Call the API method associated with a given command.

        :param command: a string which will translate to a specific 'set_' method
        :param args: possible positional arguments required by the called method
        :param kwargs: possible keyword arguments required by the called method

        :returns: the associated function call response

        :raises ValueError: if the requested API method doesn't exist
        """
        set = f"set_{command.lower()}"
        if hasattr(self, set) and callable(func := getattr(self, set)):
            # assignment := means 'set the value of variable \
            # and evaluate the result of expression in a single line'
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        raise ValueError(f"No API method found for command '{command}'.")

    async def query(self, message: str, *args, **kwargs) -> Any:
        """
        Call the API method associated with a given message.

        :param message: a string which will translate to a specific 'get_' method
        :param args: possible positional arguments required by the called method
        :param kwargs: possible keyword arguments required by the called method

        :returns: the associated function call response

        :raises ValueError: if the requested API method doesn't exist
        """
        get = f"get_{message.lower()}"
        if hasattr(self, get) and callable(func := getattr(self, get)):
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        raise ValueError(f"No API method found for query message '{message}'.")

    def get_system_tree(self, *args, **kwargs) -> IOTreeNode:
        """
        Get a tree representation of the whole EtherCAT I/O system.

        :returns: an IOTreeNode object representing the root server and all
            its child nodes
        """
        return self._generate_system_tree()

    def get_io_from_map(
        self, identifier: int, io_group: str, io_name: str = ""
    ) -> IOServer | IODevice | IOSlave:
        """
        Get the I/O object (server, device or terminal) associated with the given id.
        If the id is not registered yet, it will be added to the internal map.

        :param identifier: the unique id associated with the I/O object
        :param io_group: the type of I/O object, one of "server", "device", "terminal
        :param io_name: the name of the I/O object, e.g. "Device5", "Term145"

        :returns: the I/O object associated with the given id
        :raises NameError: if the given id cannot be associated with any I/O object
        """
        if identifier not in self.fastcs_io_map:
            match io_group:
                case "server":
                    self.fastcs_io_map[identifier] = self.ioserver
                    return self.ioserver
                case "device":
                    matches = re.search(r"(\d+)$", io_name)
                    if matches:
                        dev_id = int(matches.group(0))
                    else:
                        dev_id = next(iter(self._ecdevices))
                    self.fastcs_io_map[identifier] = self._ecdevices[dev_id]
                    return self._ecdevices[dev_id]
                case "terminal":
                    terminal: IOSlave | None = None
                    for device in self._ecdevices.values():
                        for slave in device.slaves:
                            if slave.name == io_name:
                                terminal = slave
                                break
                        if terminal is not None:
                            break
                    assert terminal is not None, (
                        f"Terminal '{io_name}' isn't defined with any EtherCAT device."
                    )
                    self.fastcs_io_map[identifier] = terminal
                    return terminal
                case _:
                    raise NameError(
                        f"No valid catio reference to object id "
                        f"'{identifier}: {io_group}'."
                    )
        else:
            raise KeyError(f"{identifier} is already registered in the I/O map.")

    @_check_system
    async def get_device_framecounters_attr(
        self, controller_id: int | None = None
    ) -> npt.NDArray[np.uint32]:
        """
        Get the frame counters for a given EtherCAT device.

        :param controller_id: the unique identifier of the fastCS device controller

        :returns: an array comprising the frame counters

        :raises KeyError: if no EtherCAT device is registered against \
            the given controller id
        :raises ValueError: if the controller id is not provided
        """
        if controller_id is not None:
            device = self.fastcs_io_map.get(controller_id, None)
            assert isinstance(device, IODevice)
            if device is not None:
                logger.debug(
                    f"Reading frame counters for EtherCAT device '{device.name}'"
                )
                await self.get_device_frames(device.id)
                return np.array(
                    [
                        device.frame_counters.time,
                        device.frame_counters.cyclic_sent,
                        device.frame_counters.cyclic_lost,
                        device.frame_counters.acyclic_sent,
                        device.frame_counters.acyclic_lost,
                    ],
                )
            raise KeyError(
                f"No EtherCAT device registered against controller id {controller_id}."
            )
        raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_device_slavecount_attr(self, controller_id: int | None = None) -> int:
        """
        Get the total number of slaves registered with a given device.

        :param controller_id: the unique identifier of the fastCS device controller

        :returns: the total number of slaves registered with the device

        :raises KeyError: if no EtherCAT device is registered against \
            the given controller id
        :raises ValueError: if the controller id is not provided
        """
        if controller_id is not None:
            device = self.fastcs_io_map.get(controller_id, None)
            assert isinstance(device, IODevice)
            if device is not None:
                logger.debug(
                    "Reading the total number of slaves registered with "
                    + f"EtherCAT device '{device.name}'"
                )
                count = await self._get_slave_count([device.netid])
                expected_count = device.slave_count
                current_count = count[0]

                if current_count != expected_count:
                    logger.critical(
                        f"Number of configured slaves on {device.name} "
                        + f"has changed from {expected_count} to {current_count}"
                    )
                return current_count
            raise KeyError(
                f"No EtherCAT device registered against controller id {controller_id}."
            )
        raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_device_slavesstates_attr(
        self, controller_id: int | None = None
    ) -> npt.NDArray[np.uint8]:
        """
        Get the states for all slaves registered with a given device.

        :param controller_id: the unique identifier of the fastCS device controller

        :returns: an array comprising the states for all slaves

        :raises KeyError: if no EtherCAT device is registered against \
            the given controller id
        :raises ValueError: if the controller id is not provided
        """
        if controller_id is not None:
            device = self.fastcs_io_map.get(controller_id, None)
            assert isinstance(device, IODevice)
            if device is not None:
                logger.debug(
                    "Reading states values for all slaves registered with "
                    + f"EtherCAT device '{device.name}'"
                )
                states = await self.get_device_slaves_states(int(device.id))
                self.update_device_slaves_states(int(device.id), states)
                assert len(states) == len(device.slaves), (
                    f"{device.name}: mismatch between the number of slave states "
                    + "readings and the number of registered slaves."
                )
                return np.array(states, dtype=np.uint8).flatten()
            raise KeyError(
                f"No EtherCAT device registered against controller id {controller_id}."
            )
        raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_device_slavescrccounters_attr(
        self, controller_id: int | None = None
    ) -> npt.NDArray[np.uint32]:
        """
        Get the CRC error counters for all slaves registered with a given device.

        :param controller_id: the unique identifier of the fastCS device controller

        :returns: an array comprising the CRC error counters for all slaves

        :raises KeyError: if no EtherCAT device is registered against \
            the given controller id
        :raises ValueError: if the controller id is not provided
        """
        if controller_id is not None:
            device = self.fastcs_io_map.get(controller_id, None)
            assert isinstance(device, IODevice)
            if device is not None:
                logger.debug(
                    "Reading crc error counters for all slaves registered with "
                    + f"EtherCAT device '{device.name}'"
                )
                crcs = await self.get_device_slaves_crcs(int(device.id))
                self.update_device_slaves_crcs(int(device.id), crcs)
                assert len(crcs) == len(device.slaves), (
                    f"{device.name}: mismatch between the number of slave crc readings "
                    + "and the number of registered slaves."
                )
                return np.array(crcs, dtype=np.uint32)
            raise KeyError(
                f"No EtherCAT device registered against controller id {controller_id}."
            )
        raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_terminal_crcerrorcounters_attr(
        self, controller_id: int | None = None
    ) -> npt.NDArray[np.uint32]:
        """
        Get the CRC error counters across all ports for a given slave terminal.

        :param controller_id: the unique identifier of the fastCS terminal controller

        :returns: an array comprising the terminal CRC error counters across all ports

        :raises KeyError: if no EtherCAT terminal is registered against \
            the given controller id
        :raises ValueError: if the controller id is not provided
        """
        if controller_id is not None:
            terminal = self.fastcs_io_map.get(controller_id, None)
            if terminal is not None:
                assert isinstance(terminal, IOSlave)
                crcs = await self.get_slave_crc_error_counters(
                    terminal.parent_device, terminal.address
                )
                return np.array(
                    [crcs.port_a_crc, crcs.port_b_crc, crcs.port_c_crc, crcs.port_d_crc]
                )
            else:
                raise KeyError(
                    "No EtherCAT terminal registered against "
                    + f"controller id {controller_id}."
                )
        else:
            raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_terminal_crcerrorsum_attr(
        self, controller_id: int | None = None
    ) -> int:
        """
        Get the sum of CRC errors across all ports for a given slave terminal.

        :param controller_id: the unique identifier of the fastCS terminal controller

        :returns: the sum of CRC errors across all ports for the terminal
        """
        if controller_id is not None:
            terminal = self.fastcs_io_map.get(controller_id, None)
            if terminal is not None:
                assert isinstance(terminal, IOSlave)
                return int(terminal.crc_error_sum)
            else:
                raise KeyError(
                    "No EtherCAT terminal registered against "
                    + f"controller id {controller_id}."
                )
        else:
            raise ValueError("Missing information about controller identification.")

    @_check_system
    async def get_terminal_states_attr(
        self, controller_id: int | None = None
    ) -> npt.NDArray[np.uint8]:
        """
        Get the EtherCAT state and link status of a given slave terminal.

        :param controller_id: the unique identifier of the fastCS terminal controller

        :returns: an array comprising the EtherCAT state and link status of the terminal
        """
        if controller_id is not None:
            terminal = self.fastcs_io_map.get(controller_id, None)
            if terminal is not None:
                assert isinstance(terminal, IOSlave)
                return np.array(
                    [terminal.states.ecat_state, terminal.states.link_status]
                )
            else:
                raise KeyError(
                    "No EtherCAT terminal registered against "
                    + f"controller id {controller_id}."
                )
        else:
            raise ValueError("Missing information about controller identification.")
