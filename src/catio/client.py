from __future__ import annotations

import asyncio
from typing import SupportsInt, TypeVar, Union

import numpy as np
from py_ads_client import ADSSymbol
from py_ads_client.ams.ads_add_device_notification import (
    ADSAddDeviceNotificationResponse,
)
from py_ads_client.ams.ads_delete_device_notification import (
    ADSDeleteDeviceNotificationResponse,
)
from py_ads_client.ams.ads_device_notification import (
    ADSDeviceNotificationResponse,
)
from py_ads_client.ams.ads_read import ADSReadResponse
from py_ads_client.ams.ads_read_device_info import ADSReadDeviceInfoResponse
from py_ads_client.ams.ads_read_state import ADSReadStateResponse
from py_ads_client.ams.ads_read_write import ADSReadWriteRequest, ADSReadWriteResponse
from py_ads_client.ams.ads_write import ADSWriteResponse
from py_ads_client.ams.ads_write_control import (
    ADSWriteControlResponse,
)
from py_ads_client.types import PLCData

from .messages import (
    RESPONSE_CLASS,
    ADSAddDeviceNotification,
    AMSHeader,
    CommandId,
    ErrorCode,
    IndexGroup,
    Message,
    StateFlag,
    TransmissionMode,
)

ADS_TCP_PORT = 48898
# https://infosys.beckhoff.com/content/1033/ipc_security_win7/11019143435.html


def netid_from_str(net_id: str) -> list[int]:
    return [int(x) for x in net_id.split(".")]


MessageT = TypeVar("MessageT", bound=Message)


class ResponseEvent:
    def __init__(self):
        self._event = asyncio.Event()
        self._value: Message | None = None

    def set(self, response: Message):
        self._value = response
        self._event.set()

    async def get(self, cls: type[MessageT]) -> MessageT:
        await self._event.wait()
        assert self._value and isinstance(
            self._value, cls
        ), f"Expected {cls}, got {self._value}"
        return self._value


class AsyncioADSClient:
    def __init__(
        self,
        local_ams_net_id: str,
        target_ams_net_id: str,
        target_ams_port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.__local_ams_net_id = netid_from_str(local_ams_net_id)
        self.__local_ams_port = 8000
        self.__target_ams_net_id = netid_from_str(target_ams_net_id)
        self.__target_ams_port = target_ams_port
        self.__reader = reader
        self.__writer = writer
        self.__current_invoke_id = np.uint32(0)
        self.__response_events: dict[SupportsInt, ResponseEvent] = {}
        self.__variable_handles: dict[
            str, int
        ] = {}  # key is variable name, value is handle
        self.__device_notification_handles: dict[
            int, ADSSymbol[PLCData]
        ] = {}  # key is handle

    @classmethod
    async def connected_to(
        cls,
        target_ip: str,
        local_ams_net_id: str,
        target_ams_net_id: str,
        target_ams_port: int,
    ) -> AsyncioADSClient:
        reader, writer = await asyncio.open_connection(target_ip, ADS_TCP_PORT)
        return cls(local_ams_net_id, target_ams_net_id, target_ams_port, reader, writer)

    async def _send_ams_message(
        self, command: CommandId, message: Message
    ) -> ResponseEvent:
        self.__current_invoke_id += 1
        payload = message.to_bytes()
        ams_header = AMSHeader(
            target_net_id=self.__target_ams_net_id,
            target_port=self.__target_ams_port,
            source_net_id=self.__local_ams_net_id,
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
        await self.__writer.drain()
        ev = ResponseEvent()
        self.__response_events[self.__current_invoke_id] = ev
        return ev

    async def _recv_task(self):
        while True:
            header, body = await self._recv_ams_message()
            assert header.error_code == ErrorCode.ERR_NOERROR, header.error_code
            if header.command_id == CommandId.ADSSRVID_DEVICENOTE:
                pass
            else:
                cls = RESPONSE_CLASS[header.command_id]
                response = cls.from_bytes(body)
                self.__response_events[header.invoke_id].set(response)

    async def _recv_ams_message(self) -> tuple[AMSHeader, bytes]:
        assert await self.__reader.readexactly(2) == b"\x00\x00"
        length = int.from_bytes(
            await self.__reader.readexactly(4), byteorder="little", signed=False
        )
        packet = await self.__reader.readexactly(length)
        AMS_HEADER_LENGTH = 32
        header = AMSHeader.from_bytes(packet[:AMS_HEADER_LENGTH])
        body = packet[AMS_HEADER_LENGTH:]
        return header, body

    async def get_handle_by_name(self, name: str) -> int:
        # TODO: if get handle by name is called by multiple client, is the handle unique?
        ev = await self._send_ams_message(
            CommandId.ADSSRVID_READWRITE,
            ADSReadWriteRequest.get_handle_by_name(name=name),
        )
        response = await ev.get(ADSReadWriteResponse)
        handle = int.from_bytes(bytes=response.data, byteorder="little", signed=False)
        return handle

    async def add_device_notification(
        self, symbol: ADSSymbol, max_delay_ms: int = 0, cycle_time_ms: int = 0
    ) -> int:
        variable_handle = self.__variable_handles.get(symbol.name, None)
        if variable_handle is None:
            variable_handle = await self.get_handle_by_name(name=symbol.name)
            self.__variable_handles[symbol.name] = variable_handle
        request = ADSAddDeviceNotification(
            index_group=IndexGroup.SYMVAL_BYHANDLE,
            index_offset=variable_handle,
            length=symbol.plc_t.bytes_length,
            max_delay_ms=max_delay_ms,
            cycle_time_ms=cycle_time_ms,
            transmission_mode=TransmissionMode.ADSTRANS_SERVERCYCLE,
        )
        ev = await self._send_ams_message(CommandId.ADSSRVID_ADDDEVICENOTE, request)
        response = await ev.get(ADSAddDeviceNotificationResponse)
        self.__device_notification_handles[response.handle] = symbol
        return response.handle

    async def get_notifications(self, n=1000):
        lengths = set()
        for _ in range(n):
            response = await self._recv_ams_message()
            assert isinstance(response, ADSDeviceNotificationResponse)
            lengths.add(len(response.samples))
        print(f"Got {n} notifications with {lengths} samples in each")
