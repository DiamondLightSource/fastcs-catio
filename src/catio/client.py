from __future__ import annotations

import asyncio
from typing import Union

import numpy as np
from py_ads_client import ADSSymbol
from py_ads_client.ams.ads_add_device_notification import (
    ADSAddDeviceNotificationRequest,
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
from py_ads_client.ams.ams_header import AMSHeader
from py_ads_client.constants.command_id import ADSCommand
from py_ads_client.constants.index_group import IndexGroup
from py_ads_client.constants.return_code import ADSErrorCode
from py_ads_client.constants.state_flag import StateFlag
from py_ads_client.constants.transmission_mode import TransmissionMode
from py_ads_client.types import PLCData

ADS_TCP_PORT = 48898
# https://infosys.beckhoff.com/content/1033/ipc_security_win7/11019143435.html


ADSResponse = Union[
    ADSReadResponse,
    ADSReadDeviceInfoResponse,
    ADSReadWriteResponse,
    ADSWriteResponse,
    ADSAddDeviceNotificationResponse,
    ADSDeleteDeviceNotificationResponse,
    ADSReadStateResponse,
    ADSWriteControlResponse,
]


class AsyncioADSClient:
    def __init__(
        self,
        local_ams_net_id: str,
        target_ams_net_id: str,
        target_ams_port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.__local_ams_net_id = local_ams_net_id
        self.__local_ams_port = 8000
        self.__target_ams_net_id = target_ams_net_id
        self.__target_ams_port = target_ams_port
        self.__reader = reader
        self.__writer = writer
        self.__current_invoke_id = np.uint32(0)
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

    async def _send_ams_packet(self, *, command: ADSCommand, payload: bytes) -> None:
        self.__current_invoke_id += 1
        ams_header = AMSHeader(
            target_net_id=self.__target_ams_net_id,
            target_port=self.__target_ams_port,
            source_net_id=self.__local_ams_net_id,
            source_port=self.__local_ams_port,
            command_id=command,
            state_flags=StateFlag.AMSCMDSF_ADSCMD,
            length=len(payload),
            error_code=ADSErrorCode.ERR_NOERROR,
            invoke_id=self.__current_invoke_id,
        )

        header_raw = ams_header.to_bytes()
        total_length = len(header_raw) + len(payload)
        length_bytes = total_length.to_bytes(4, byteorder="little", signed=False)
        self.__writer.write(b"\x00\x00" + length_bytes + header_raw + payload)
        await self.__writer.drain()

    async def _recv_ams_packet(self) -> ADSResponse:
        assert await self.__reader.readexactly(2) == b"\x00\x00"
        length = int.from_bytes(
            await self.__reader.readexactly(4), byteorder="little", signed=False
        )
        packet = await self.__reader.readexactly(length)
        AMS_HEADER_LENGTH = 32
        header = AMSHeader.from_bytes(packet[:AMS_HEADER_LENGTH])
        assert header.error_code == ADSErrorCode.ERR_NOERROR, header.error_code
        ads_body = packet[AMS_HEADER_LENGTH:]
        if header.command_id == ADSCommand.ADSSRVID_READDEVICEINFO:
            response = ADSReadDeviceInfoResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_READ:
            response = ADSReadResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_WRITE:
            response = ADSWriteResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_READSTATE:
            response = ADSReadStateResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_WRITECTRL:
            response = ADSWriteControlResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_ADDDEVICENOTE:
            response = ADSAddDeviceNotificationResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_DELDEVICENOTE:
            response = ADSDeleteDeviceNotificationResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_DEVICENOTE:
            response = ADSDeviceNotificationResponse.from_bytes(ads_body)
        elif header.command_id == ADSCommand.ADSSRVID_READWRITE:
            response = ADSReadWriteResponse.from_bytes(ads_body)
        return response

    async def get_handle_by_name(self, name: str) -> int:
        # TODO: if get handle by name is called by multiple client, is the handle unique?
        request = ADSReadWriteRequest.get_handle_by_name(name=name)
        request_raw = request.to_bytes()
        await self._send_ams_packet(
            command=ADSCommand.ADSSRVID_READWRITE, payload=request_raw
        )
        response = await self._recv_ams_packet()
        assert isinstance(response, ADSReadWriteResponse), response
        handle = int.from_bytes(bytes=response.data, byteorder="little", signed=False)
        return handle

    async def add_device_notification(
        self, symbol: ADSSymbol, max_delay_ms: int = 0, cycle_time_ms: int = 0
    ) -> int:
        variable_handle = self.__variable_handles.get(symbol.name, None)
        if variable_handle is None:
            variable_handle = await self.get_handle_by_name(name=symbol.name)
            self.__variable_handles[symbol.name] = variable_handle
        request = ADSAddDeviceNotificationRequest(
            index_group=IndexGroup.SYMVAL_BYHANDLE,
            index_offset=variable_handle,
            length=symbol.plc_t.bytes_length,
            max_delay_ms=max_delay_ms,
            cycle_time_ms=cycle_time_ms,
            transmission_mode=TransmissionMode.ADSTRANS_SERVERCYCLE,
        )
        request_raw = request.to_bytes()
        await self._send_ams_packet(
            command=ADSCommand.ADSSRVID_ADDDEVICENOTE, payload=request_raw
        )
        response = await self._recv_ams_packet()
        assert isinstance(response, ADSAddDeviceNotificationResponse)
        self.__device_notification_handles[response.handle] = symbol
        return response.handle

    async def get_notifications(self, n=1000):
        for _ in range(n):
            response = await self._recv_ams_packet()
            assert isinstance(response, ADSDeviceNotificationResponse)
        print(f"Got {n} notifications")
