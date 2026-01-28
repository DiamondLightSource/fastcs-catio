"""
ADS Simulation Server implementation.

This module provides a standalone ADS server that simulates a Beckhoff TwinCAT device
with an EtherCAT chain, supporting all ADS messages used by the CATio client.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.ads_sim.ethercat_chain import (
    COE_OPERATIONAL_PARAMS_BASE,
    EtherCATChain,
    EtherCATDevice,
)

logger = logging.getLogger(__name__)


# ADS Constants (matching fastcs_catio._constants)
class CommandId:
    """ADS Command IDs."""

    ADSSRVID_READDEVICEINFO = 0x1
    ADSSRVID_READ = 0x2
    ADSSRVID_WRITE = 0x3
    ADSSRVID_READSTATE = 0x4
    ADSSRVID_WRITECTRL = 0x5
    ADSSRVID_ADDDEVICENOTE = 0x6
    ADSSRVID_DELETEDEVICENOTE = 0x7
    ADSSRVID_DEVICENOTE = 0x8
    ADSSRVID_READWRITE = 0x9


class StateFlag:
    """AMS State Flags."""

    AMSCMDSF_RESPONSE = 0x1
    AMSCMDSF_ADSCMD = 0x4


class AdsState:
    """ADS State values."""

    ADSSTATE_INVALID = 0
    ADSSTATE_IDLE = 1
    ADSSTATE_RUN = 5
    ADSSTATE_STOP = 6


class ErrorCode:
    """ADS Error codes."""

    ERR_NOERROR = 0x0
    ADSERR_DEVICE_ERROR = 0x700
    ADSERR_DEVICE_SRVNOTSUPP = 0x701
    ADSERR_DEVICE_INVALIDGRP = 0x702
    ADSERR_DEVICE_INVALIDOFFSET = 0x703
    ADSERR_DEVICE_INVALIDACCESS = 0x704
    ADSERR_DEVICE_INVALIDSIZE = 0x705
    ADSERR_DEVICE_INVALIDDATA = 0x706
    ADSERR_DEVICE_NOTREADY = 0x707
    ADSERR_DEVICE_BUSY = 0x708
    ADSERR_DEVICE_INVALIDINTERFACE = 0x70E


class IndexGroup:
    """ADS Index Groups."""

    ADSIGRP_MASTER_STATEMACHINE = 0x0003
    ADSIGRP_MASTER_COUNT_SLAVE = 0x0006
    ADSIGRP_MASTER_SLAVE_ADDRESSES = 0x0007
    ADSIGRP_SLAVE_STATEMACHINE = 0x0009
    ADSIGRP_MASTER_FRAME_COUNTERS = 0x000C
    ADSIGRP_MASTER_SLAVE_IDENTITY = 0x0011
    ADSIGRP_SLAVE_CRC_COUNTERS = 0x0012
    ADSIGR_IODEVICE_STATE_BASE = 0x5000
    ADSIGR_GET_SYMHANDLE_BYNAME = 0xF003
    ADSIGR_GET_SYMVAL_BYHANDLE = 0xF005
    ADSIGRP_RELEASE_SYMHANDLE = 0xF006
    ADSIGRP_IOIMAGE_RWIB = 0xF020
    ADSIGRP_IOIMAGE_RWIX = 0xF021
    ADSIGRP_IOIMAGE_RISIZE = 0xF025
    ADSIGRP_IOIMAGE_RWOB = 0xF030
    ADSIGRP_IOIMAGE_RWOX = 0xF031
    ADSIGRP_IOIMAGE_RWOSIZE = 0xF035
    ADSIGRP_SUMUP_READ = 0xF080
    ADSIGRP_SUMUP_WRITE = 0xF081
    ADSIGRP_SUMUP_READWRITE = 0xF082
    ADSIGRP_SYM_UPLOAD = 0xF00B
    ADSIGRP_SYM_UPLOADINFO2 = 0xF00F
    ADSIGRP_COE_LINK = 0xF302


# Standard ADS ports
ADS_TCP_PORT = 48898
ADS_UDP_PORT = 48899
IO_SERVER_PORT = 300
ADS_MASTER_PORT = 65535
SYSTEM_SERVICE_PORT = 10000

# UDP Service IDs
ADSSVCID_READSERVICEINFO = 0x1
ADSSVCID_ADDROUTE = 0x6
ADSSVCID_DELROUTE = 0xB001
ADSSCVID_RESPONSE = 0x80000000

# UDP Cookie - must match client expectation (0x71146603)
UDP_COOKIE = 0x71146603


class UDPProtocol(asyncio.DatagramProtocol):
    """UDP Protocol handler for ADS service discovery."""

    def __init__(self, server: ADSSimServer):
        self.server = server
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        """Called when the UDP socket is ready."""
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle incoming UDP datagrams."""
        if len(data) < 12:
            logger.warning(f"UDP packet too short from {addr}")
            return

        # Parse UDP header
        udp_cookie, invoke_id, service_id = struct.unpack("<III", data[:12])
        logger.info(
            f"UDP incoming from {addr}: cookie={udp_cookie:#x}, "
            f"service={service_id:#x}, invoke={invoke_id}, len={len(data)}"
        )

        # Validate cookie - client sends 0x71146603
        if udp_cookie != UDP_COOKIE:
            logger.warning(
                f"Invalid UDP cookie: {udp_cookie:#x}, expected {UDP_COOKIE:#x}"
            )
            return

        logger.debug(f"UDP request: service={service_id:#x}, invoke={invoke_id}")

        # Handle service requests
        if service_id == ADSSVCID_READSERVICEINFO:
            response = self._handle_read_service_info(invoke_id)
        elif service_id == ADSSVCID_ADDROUTE:
            response = self._handle_add_route(invoke_id, data[12:])
        elif service_id == ADSSVCID_DELROUTE:
            response = self._handle_del_route(invoke_id, data[12:])
        else:
            logger.warning(f"Unknown UDP service: {service_id:#x}")
            return

        if self.transport and response:
            # Parse response for logging
            resp_cookie, resp_invoke_id, resp_service_id = struct.unpack(
                "<III", response[:12]
            )
            logger.info(
                f"UDP outgoing to {addr}: cookie={resp_cookie:#x}, "
                "service={resp_service_id:#x}, invoke={resp_invoke_id}, "
                "len={len(response)}"
            )
            self.transport.sendto(response, addr)

    def _handle_read_service_info(self, invoke_id: int) -> bytes:
        """Handle ReadServiceInfo request - returns server NetID."""
        # Get the first device's netid or use a default
        if self.server.chain.devices:
            device = next(iter(self.server.chain.devices.values()))
            netid_bytes = device.get_netid_bytes()
        else:
            netid_bytes = bytes([127, 0, 0, 1, 1, 1])

        # Build response
        # UDP header: cookie (4) + invoke_id (4) + service_id (4)
        response_service_id = ADSSVCID_READSERVICEINFO | ADSSCVID_RESPONSE
        udp_header = struct.pack(
            "<III",
            UDP_COOKIE,
            invoke_id,
            response_service_id,
        )

        # Response data: netid (6) + port (2) + count (4) + data
        response_data = struct.pack(
            "<6sHI",
            netid_bytes,
            SYSTEM_SERVICE_PORT,
            0,  # count of additional info items
        )

        return udp_header + response_data

    def _handle_add_route(self, invoke_id: int, data: bytes) -> bytes:
        """Handle AddRoute request."""
        logger.info("UDP AddRoute request received (simulated success)")

        # Build response
        response_service_id = ADSSVCID_ADDROUTE | ADSSCVID_RESPONSE
        udp_header = struct.pack(
            "<III",
            UDP_COOKIE,
            invoke_id,
            response_service_id,
        )

        # Get the first device's netid
        if self.server.chain.devices:
            device = next(iter(self.server.chain.devices.values()))
            netid_bytes = device.get_netid_bytes()
        else:
            netid_bytes = bytes([127, 0, 0, 1, 1, 1])

        # Response data: netid (6) + port (2) + count (4) + tag info
        # Tag info: tag_id (2) + length (2) + data (4 = error code)
        tag_id = 1  # Result tag
        tag_length = 4
        error_code = ErrorCode.ERR_NOERROR

        response_data = struct.pack(
            "<6sHIHHI",
            netid_bytes,
            SYSTEM_SERVICE_PORT,
            1,  # count of info items
            tag_id,
            tag_length,
            error_code,
        )

        return udp_header + response_data

    def _handle_del_route(self, invoke_id: int, data: bytes) -> bytes:
        """Handle DeleteRoute request."""
        logger.info("UDP DeleteRoute request received (simulated success)")

        # Build response
        response_service_id = ADSSVCID_DELROUTE | ADSSCVID_RESPONSE
        udp_header = struct.pack(
            "<III",
            UDP_COOKIE,
            invoke_id,
            response_service_id,
        )

        # Get the first device's netid
        if self.server.chain.devices:
            device = next(iter(self.server.chain.devices.values()))
            netid_bytes = device.get_netid_bytes()
        else:
            netid_bytes = bytes([127, 0, 0, 1, 1, 1])

        # Response data: netid (6) + port (2) + error_code (4)
        response_data = struct.pack(
            "<6sHI",
            netid_bytes,
            SYSTEM_SERVICE_PORT,
            ErrorCode.ERR_NOERROR,  # error code in count field for del route
        )

        return udp_header + response_data


class ADSSimServer:
    """
    ADS Simulation Server that emulates a Beckhoff TwinCAT device.

    Supports all ADS messages used by fastcs_catio.client including:
    - ReadDeviceInfo
    - ReadState
    - Read (device info, slave info, CoE parameters, etc.)
    - Write
    - ReadWrite
    - AddDeviceNotification
    - DeleteDeviceNotification
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = ADS_TCP_PORT,
        config_path: str | Path | None = None,
        enable_notifications: bool = True,
    ):
        """
        Initialize the ADS simulation server.

        Args:
            host: Host address to bind to.
            port: Port to listen on.
            config_path: Path to YAML config file for EtherCAT chain.
            enable_notifications: Whether to enable the notification system.
        """
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.udp_transport: asyncio.DatagramTransport | None = None
        self.running = False
        self.enable_notifications = enable_notifications

        # Load EtherCAT chain configuration
        self.chain = EtherCATChain(config_path)

        # ADS state
        self.ads_state = AdsState.ADSSTATE_RUN
        self.device_state = 0

        # Notification management
        self._notification_handles: dict[int, dict[str, Any]] = {}
        self._next_handle = 1
        self._notification_task: asyncio.Task | None = None
        self._notification_writers: dict[
            tuple[bytes, int], asyncio.StreamWriter
        ] = {}  # (netid, port) -> writer

        # Symbol handle management
        self._symbol_handles: dict[int, str] = {}
        self._next_symbol_handle = 0x1000

        # Command handlers by port
        self._handlers: dict[int, Callable] = {
            CommandId.ADSSRVID_READDEVICEINFO: self._handle_read_device_info,
            CommandId.ADSSRVID_READSTATE: self._handle_read_state,
            CommandId.ADSSRVID_READ: self._handle_read,
            CommandId.ADSSRVID_WRITE: self._handle_write,
            CommandId.ADSSRVID_READWRITE: self._handle_read_write,
            CommandId.ADSSRVID_ADDDEVICENOTE: self._handle_add_notification,
            CommandId.ADSSRVID_DELETEDEVICENOTE: self._handle_delete_notification,
        }

    async def start(self) -> None:
        """Start the ADS simulation server (TCP and UDP)."""
        # Start TCP server
        self.server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )

        # Start UDP server for service discovery
        loop = asyncio.get_event_loop()
        self.udp_transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=(self.host, ADS_UDP_PORT),
        )

        self.running = True

        # Start notification streaming task (if enabled)
        if self.enable_notifications:
            self._notification_task = asyncio.create_task(self._notification_streamer())
            logger.info("Notification system enabled")
        else:
            logger.info("Notification system disabled")

        logger.info(f"ADS Simulation server started on {self.host}:{self.port} (TCP)")
        logger.info(f"ADS UDP discovery service on {self.host}:{ADS_UDP_PORT}")
        self.chain.print_chain()

    async def stop(self) -> None:
        """Stop the ADS simulation server."""
        self.running = False

        if self._notification_task:
            self._notification_task.cancel()
            try:
                await self._notification_task
            except asyncio.CancelledError:
                pass
            self._notification_task = None

        if self.udp_transport:
            self.udp_transport.close()
            self.udp_transport = None

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("ADS Simulation server stopped")

    async def serve_forever(self) -> None:
        """Run the server until cancelled."""
        if not self.server:
            await self.start()
        async with self.server:  # type: ignore[union-attr]
            await self.server.serve_forever()  # type: ignore[union-attr]

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a new client connection."""
        addr = writer.get_extra_info("peername")
        logger.info(f"Client connected from {addr}")
        client_key: tuple[bytes, int] | None = None

        try:
            while True:
                # Read AMS/TCP header (6 bytes: 2 reserved + 4 length)
                # Wait indefinitely for first byte, then timeout for remaining bytes
                first_byte = await reader.readexactly(1)
                if not first_byte:
                    break

                # Now that we have activity, read remaining 5 bytes with timeout
                try:
                    remaining_bytes = await asyncio.wait_for(
                        reader.readexactly(5), timeout=5.0
                    )
                except TimeoutError:
                    logger.warning(
                        f"Client {addr} timeout reading TCP header "
                        f"(first byte was {first_byte})"
                    )
                    break

                header_bytes = first_byte + remaining_bytes

                # Validate reserved bytes
                if header_bytes[:2] != b"\x00\x00":
                    logger.warning(f"Invalid TCP header: {header_bytes[:2].hex()}")
                    continue

                # Get frame length
                frame_length = int.from_bytes(header_bytes[2:], byteorder="little")

                # Read AMS header (32 bytes) with timeout
                ams_header = await asyncio.wait_for(reader.readexactly(32), timeout=5.0)

                # Extract source info for notification tracking
                source_netid = ams_header[6:12]
                source_port = int.from_bytes(ams_header[12:14], "little")
                client_key = (source_netid, source_port)
                self._notification_writers[client_key] = writer

                # Read payload (frame_length - 32) with timeout
                payload_length = frame_length - 32
                if payload_length > 0:
                    payload = await asyncio.wait_for(
                        reader.readexactly(payload_length), timeout=5.0
                    )
                else:
                    payload = b""

                # Process message and send response
                response = await self._process_ams_message(
                    ams_header, payload, writer, client_key
                )
                if response:
                    logger.debug(f"Sending response to {addr}, len={len(response)}")
                    writer.write(response)
                    await writer.drain()

        except TimeoutError:
            logger.warning(f"Client {addr} timeout reading message")
        except asyncio.IncompleteReadError:
            logger.info(f"Client {addr} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}", exc_info=True)
        finally:
            # Clean up notification writer
            if client_key and client_key in self._notification_writers:
                del self._notification_writers[client_key]
            writer.close()
            await writer.wait_closed()

    async def _process_ams_message(
        self,
        ams_header: bytes,
        payload: bytes,
        writer: asyncio.StreamWriter,
        client_key: tuple[bytes, int],
    ) -> bytes | None:
        """Process an incoming AMS message and generate response."""
        # Parse AMS header
        (
            target_netid,
            target_port,
            source_netid,
            source_port,
            command_id,
            state_flags,
            length,
            error_code,
            invoke_id,
        ) = struct.unpack("<6sH6sHHHIII", ams_header)

        logger.info(
            f"TCP Incoming AMS message: cmd={command_id:#x}, port={target_port}, "
            f"len={length}, invoke_id={invoke_id}"
        )

        # Get handler
        handler = self._handlers.get(command_id)
        if not handler:
            logger.warning(f"No handler for command {command_id:#x}")
            return self._build_error_response(
                source_netid,
                source_port,
                target_netid,
                target_port,
                command_id,
                invoke_id,
                ErrorCode.ADSERR_DEVICE_SRVNOTSUPP,
            )

        # Determine target device from netid
        target_netid_str = ".".join(str(b) for b in target_netid)
        device = self.chain.get_device_by_netid(target_netid_str)

        logger.debug(
            f"Processing command={command_id:#x} for "
            f"device={target_netid_str}, invoke_id={invoke_id}"
        )
        # Process command
        try:
            response_payload = await handler(
                payload, target_port, target_netid_str, device
            )
        except Exception as e:
            logger.error(f"Handler error: {e}", exc_info=True)
            response_payload = struct.pack("<I", ErrorCode.ADSERR_DEVICE_ERROR)

        # Build response
        return self._build_response(
            source_netid,
            source_port,
            target_netid,
            target_port,
            command_id,
            invoke_id,
            response_payload,
        )

    def _build_response(
        self,
        target_netid: bytes,
        target_port: int,
        source_netid: bytes,
        source_port: int,
        command_id: int,
        invoke_id: int,
        payload: bytes,
    ) -> bytes:
        """Build a complete AMS response packet."""
        # AMS header
        ams_header = struct.pack(
            "<6sH6sHHHIII",
            target_netid,
            target_port,
            source_netid,
            source_port,
            command_id,
            StateFlag.AMSCMDSF_RESPONSE | StateFlag.AMSCMDSF_ADSCMD,
            len(payload),
            ErrorCode.ERR_NOERROR,
            invoke_id,
        )

        # AMS/TCP header
        frame_length = len(ams_header) + len(payload)
        tcp_header = b"\x00\x00" + frame_length.to_bytes(4, "little")

        response = tcp_header + ams_header + payload
        logger.info(
            f"Built response: cmd={command_id:#x}, invoke={invoke_id}, "
            f"payload_len={len(payload)}"
        )
        return response

    def _build_error_response(
        self,
        target_netid: bytes,
        target_port: int,
        source_netid: bytes,
        source_port: int,
        command_id: int,
        invoke_id: int,
        error_code: int,
    ) -> bytes:
        """Build an AMS error response."""
        # Error response payload (just the error code)
        payload = struct.pack("<I", error_code)
        return self._build_response(
            target_netid,
            target_port,
            source_netid,
            source_port,
            command_id,
            invoke_id,
            payload,
        )

    # ===================================================================
    # ADS Command Handlers
    # ===================================================================

    async def _handle_read_device_info(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle ReadDeviceInfo command."""
        # Response: result (4) + major (1) + minor (1) + build (2) + name (16)
        return struct.pack(
            "<IBBH16s",
            ErrorCode.ERR_NOERROR,
            self.chain.server_info.major_version,
            self.chain.server_info.minor_version,
            self.chain.server_info.build,
            self.chain.server_info.get_name_bytes(),
        )

    async def _handle_read_state(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle ReadState command."""
        # Response: result (4) + ads_state (2) + device_state (2)
        return struct.pack(
            "<IHH",
            ErrorCode.ERR_NOERROR,
            self.ads_state,
            self.device_state,
        )

    async def _handle_read(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle Read command for various index groups."""
        if len(payload) < 12:
            return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDSIZE, 0)

        index_group, index_offset, read_length = struct.unpack("<III", payload[:12])
        logger.info(
            f"Read: group={index_group:#x}, offset={index_offset:#x}, len={read_length}"
        )

        # Handle symbol table requests (any port, including target AMS port)
        if index_group == IndexGroup.ADSIGRP_SYM_UPLOADINFO2:
            return await self._handle_symbol_upload_info(read_length)
        if index_group == IndexGroup.ADSIGRP_SYM_UPLOAD:
            return await self._handle_symbol_upload(read_length)

        # Route to appropriate handler based on port and index group
        if port == IO_SERVER_PORT:
            return await self._handle_io_server_read(
                index_group, index_offset, read_length
            )
        elif port == ADS_MASTER_PORT and device:
            return await self._handle_master_read(
                device, index_group, index_offset, read_length
            )
        else:
            # Try to find device by netid
            device = self.chain.get_device_by_netid(netid)
            if device:
                return await self._handle_master_read(
                    device, index_group, index_offset, read_length
                )

        return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDGRP, 0)

    async def _handle_io_server_read(
        self, index_group: int, index_offset: int, read_length: int
    ) -> bytes:
        """Handle Read commands to I/O Server port (300)."""
        base_group = IndexGroup.ADSIGR_IODEVICE_STATE_BASE

        # Device count query
        if index_group == base_group and index_offset == 0x2:
            data = self.chain.device_count.to_bytes(4, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Device IDs query
        if index_group == base_group and index_offset == 0x1:
            data = len(self.chain.device_ids).to_bytes(2, "little")
            for dev_id in self.chain.device_ids:
                data += dev_id.to_bytes(2, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Per-device queries (group = base + device_id)
        if index_group > base_group:
            device_id = index_group - base_group
            device = self.chain.get_device(device_id)
            if device:
                return await self._handle_device_info_read(
                    device, index_offset, read_length
                )

        return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDGRP, 0)

    async def _handle_device_info_read(
        self, device: EtherCATDevice, index_offset: int, read_length: int
    ) -> bytes:
        """Handle Read commands for device-specific information."""
        # Device name
        if index_offset == 0x1:
            data = device.get_name_bytes()
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Device NetID
        if index_offset == 0x5:
            data = device.get_netid_bytes()
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Device type
        if index_offset == 0x7:
            data = device.type.to_bytes(2, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)

    async def _handle_master_read(
        self,
        device: EtherCATDevice,
        index_group: int,
        index_offset: int,
        read_length: int,
    ) -> bytes:
        """Handle Read commands to Master port (65535)."""
        # Slave count
        if index_group == IndexGroup.ADSIGRP_MASTER_COUNT_SLAVE:
            data = device.slave_count.to_bytes(2, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Slave addresses
        if index_group == IndexGroup.ADSIGRP_MASTER_SLAVE_ADDRESSES:
            data = b"".join(
                addr.to_bytes(2, "little") for addr in device.get_slave_addresses()
            )
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Slave identity
        if index_group == IndexGroup.ADSIGRP_MASTER_SLAVE_IDENTITY:
            slave = device.get_slave_by_address(index_offset)
            if slave:
                data = slave.identity.to_bytes()
                return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data
            return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)

        # Master state machine
        if index_group == IndexGroup.ADSIGRP_MASTER_STATEMACHINE:
            data = device.master_state.to_bytes(2, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Slave state machine
        if index_group == IndexGroup.ADSIGRP_SLAVE_STATEMACHINE:
            if index_offset == 0:
                # All slaves
                data = b"".join(slave.get_state_bytes() for slave in device.slaves)
            else:
                # Single slave
                slave = device.get_slave_by_address(index_offset)
                if slave:
                    data = slave.get_state_bytes()
                else:
                    return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Frame counters
        if index_group == IndexGroup.ADSIGRP_MASTER_FRAME_COUNTERS:
            data = device.get_frame_counters_bytes()
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # CRC counters
        if index_group == IndexGroup.ADSIGRP_SLAVE_CRC_COUNTERS:
            if index_offset == 0:
                # Sum CRC for all slaves
                data = b"".join(
                    sum(slave.crc_counters).to_bytes(4, "little")
                    for slave in device.slaves
                )
            else:
                # Detailed CRC for single slave
                slave = device.get_slave_by_address(index_offset)
                if slave:
                    data = slave.get_crc_bytes()
                else:
                    return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # CoE link (CAN over EtherCAT)
        if index_group == IndexGroup.ADSIGRP_COE_LINK:
            return await self._handle_coe_read(device, index_offset, read_length)

        return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDGRP, 0)

    async def _handle_coe_read(
        self, device: EtherCATDevice, index_offset: int, read_length: int
    ) -> bytes:
        """Handle CoE (CAN over EtherCAT) read requests."""
        # Extract CoE index and subindex from offset
        # Format: 0xYYYY00ZZ where YYYY is index, ZZ is subindex
        coe_index = (index_offset >> 16) & 0xFFFF
        coe_subindex = index_offset & 0xFF

        # Device identity (0x1018)
        if coe_index == 0x1018:
            device_identity = device.identity
            if coe_subindex == 0x01:
                data = device_identity.vendor_id_bytes()
            elif coe_subindex == 0x02:
                data = device_identity.product_code_bytes()
            elif coe_subindex == 0x03:
                data = device_identity.revision_number_bytes()
            elif coe_subindex == 0x04:
                data = device_identity.serial_number_bytes()
            else:
                return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Slave operational parameters (0x8000+)
        if coe_index >= COE_OPERATIONAL_PARAMS_BASE:
            slave_index = coe_index - COE_OPERATIONAL_PARAMS_BASE
            slave = device.get_slave_by_index(slave_index)
            if slave:
                # Subindex 0x02 = type, 0x03 = name
                if coe_subindex == 0x02:
                    data = slave.get_type_bytes()
                    data = data.ljust(read_length, b"\x00")[:read_length]
                elif coe_subindex == 0x03:
                    data = slave.get_name_bytes()
                    data = data.ljust(read_length, b"\x00")[:read_length]
                else:
                    data = b"\x00" * read_length
                return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDOFFSET, 0)

    async def _handle_symbol_upload_info(self, read_length: int) -> bytes:
        """Handle symbol upload info request (index group 0xF00F).

        Returns info about the symbol table: count, length, and reserved bytes.
        """
        # Generate symbol table if not cached
        symbol_table = self._build_symbol_table()

        # AdsSymbolTableInfo format: symbol_count (4) + table_length (4) + reserved (12)
        symbol_count = len(self._symbol_entries)
        table_length = len(symbol_table)

        data = struct.pack(
            "<II12s",
            symbol_count,
            table_length,
            b"\x00" * 12,  # reserved
        )

        return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

    async def _handle_symbol_upload(self, read_length: int) -> bytes:
        """Handle symbol upload request (index group 0xF00B).

        Returns the complete symbol table data.
        """
        # Generate symbol table if not cached
        symbol_table = self._build_symbol_table()

        header = struct.pack("<II", ErrorCode.ERR_NOERROR, len(symbol_table))
        return header + symbol_table

    def _build_symbol_table(self) -> bytes:
        """Build the symbol table from EtherCAT chain configuration.

        Uses the terminal type definitions from the YAML config.
        """
        if hasattr(self, "_symbol_table_cache"):
            return self._symbol_table_cache

        # Get symbols from the chain (using terminal type definitions)
        self._symbol_entries = self.chain.get_all_symbols()
        symbol_data = b""

        for sym in self._symbol_entries:
            entry = self._build_symbol_entry(sym)
            symbol_data += entry

        self._symbol_table_cache = symbol_data
        logger.info(
            f"Built symbol table: {len(self._symbol_entries)} symbols, "
            f"{len(symbol_data)} bytes"
        )
        return symbol_data

    def _build_symbol_entry(self, sym: dict[str, Any]) -> bytes:
        """Build a single symbol table entry."""
        name = sym["name"].encode("utf-8") + b"\x00"
        type_name = sym["type_name"].encode("utf-8") + b"\x00"
        comment = sym.get("comment", "").encode("utf-8") + b"\x00"

        # Calculate entry length: header (30 bytes) + name + type + comment
        header_size = 30
        entry_length = header_size + len(name) + len(type_name) + len(comment)

        # Build entry header matching AdsSymbolTableEntry dtype:
        # read_length (u4), index_group (u4), index_offset (u4), size (u4),
        # ads_type (u4), flag (u4), name_size (u2), type_size (u2), comment_size (u2)
        header = struct.pack(
            "<IIIIIIHHH",
            entry_length,  # read_length (u4)
            sym["index_group"],  # index_group (u4)
            sym["index_offset"],  # index_offset (u4)
            sym["size"],  # size (u4)
            sym["ads_type"],  # ads_type (u4)
            0,  # flag (u4)
            len(name) - 1,  # name_size (u2) - without null terminator
            len(type_name) - 1,  # type_size (u2) - without null terminator
            len(comment) - 1,  # comment_size (u2) - without null terminator
        )

        return header + name + type_name + comment

    async def _handle_write(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle Write command."""
        if len(payload) < 12:
            return struct.pack("<I", ErrorCode.ADSERR_DEVICE_INVALIDSIZE)

        index_group, index_offset, write_length = struct.unpack("<III", payload[:12])

        logger.debug(
            f"Write: group={index_group:#x}, offset={index_offset:#x}, "
            f"len={write_length}"
        )

        # Handle frame counter reset
        if index_group == IndexGroup.ADSIGRP_MASTER_FRAME_COUNTERS:
            if device:
                device.frame_time = 0
                device.cyclic_sent = 0
                device.cyclic_lost = 0
                device.acyclic_sent = 0
                device.acyclic_lost = 0
            return struct.pack("<I", ErrorCode.ERR_NOERROR)

        # Default: acknowledge write
        return struct.pack("<I", ErrorCode.ERR_NOERROR)

    async def _handle_read_write(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle ReadWrite command."""
        if len(payload) < 16:
            return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDSIZE, 0)

        index_group, index_offset, read_length, write_length = struct.unpack(
            "<IIII", payload[:16]
        )
        write_data = payload[16 : 16 + write_length]

        logger.debug(
            f"ReadWrite: group={index_group:#x}, offset={index_offset:#x}, "
            f"read_len={read_length}, write_len={write_length}"
        )

        # Symbol handle by name
        if index_group == IndexGroup.ADSIGR_GET_SYMHANDLE_BYNAME:
            symbol_name = write_data.rstrip(b"\x00").decode("cp1252")
            handle = self._next_symbol_handle
            self._symbol_handles[handle] = symbol_name
            self._next_symbol_handle += 1
            data = handle.to_bytes(4, "little")
            return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

        # Sum read
        if index_group == IndexGroup.ADSIGRP_SUMUP_READ:
            return await self._handle_sum_read(index_offset, write_data, read_length)

        # Sum write
        if index_group == IndexGroup.ADSIGRP_SUMUP_WRITE:
            return await self._handle_sum_write(index_offset, write_data, read_length)

        # Default: return zeros
        data = b"\x00" * read_length
        return struct.pack("<II", ErrorCode.ERR_NOERROR, len(data)) + data

    async def _handle_sum_read(
        self, count: int, write_data: bytes, read_length: int
    ) -> bytes:
        """Handle SumRead (multiple reads in one request)."""
        # Each sub-request is 12 bytes (group, offset, length)
        results = []
        data_parts = []
        offset = 0

        for _ in range(count):
            if offset + 12 > len(write_data):
                break
            sub_group, sub_offset, sub_length = struct.unpack(
                "<III", write_data[offset : offset + 12]
            )
            offset += 12

            # Return zeros for each sub-request
            results.append(ErrorCode.ERR_NOERROR)
            data_parts.append(b"\x00" * sub_length)

        # Build response: error codes, then data
        response_data = b"".join(
            err.to_bytes(4, "little") for err in results
        ) + b"".join(data_parts)
        return (
            struct.pack("<II", ErrorCode.ERR_NOERROR, len(response_data))
            + response_data
        )

    async def _handle_sum_write(
        self, count: int, write_data: bytes, read_length: int
    ) -> bytes:
        """Handle SumWrite (multiple writes in one request)."""
        # Return success for each sub-request
        results = [ErrorCode.ERR_NOERROR] * count
        response_data = b"".join(err.to_bytes(4, "little") for err in results)
        return (
            struct.pack("<II", ErrorCode.ERR_NOERROR, len(response_data))
            + response_data
        )

    async def _handle_add_notification(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle AddDeviceNotification command."""
        if len(payload) < 40:
            return struct.pack("<II", ErrorCode.ADSERR_DEVICE_INVALIDSIZE, 0)

        (
            index_group,
            index_offset,
            length,
            transmission_mode,
            max_delay,
            cycle_time,
        ) = struct.unpack("<IIIIII", payload[:24])
        # Remaining 16 bytes are reserved

        handle = self._next_handle
        self._next_handle += 1

        self._notification_handles[handle] = {
            "index_group": index_group,
            "index_offset": index_offset,
            "length": length,
            "transmission_mode": transmission_mode,
            "max_delay": max_delay,
            "cycle_time": cycle_time,
        }

        logger.debug(f"Added notification handle {handle}")
        return struct.pack("<II", ErrorCode.ERR_NOERROR, handle)

    async def _handle_delete_notification(
        self,
        payload: bytes,
        port: int,
        netid: str,
        device: EtherCATDevice | None,
    ) -> bytes:
        """Handle DeleteDeviceNotification command."""
        if len(payload) < 4:
            return struct.pack("<I", ErrorCode.ADSERR_DEVICE_INVALIDSIZE)

        (handle,) = struct.unpack("<I", payload[:4])

        if handle in self._notification_handles:
            del self._notification_handles[handle]
            logger.debug(f"Deleted notification handle {handle}")

        return struct.pack("<I", ErrorCode.ERR_NOERROR)

    async def _notification_streamer(self) -> None:
        """Background task that sends notification data to clients.

        Sends notifications at regular intervals (every 100ms) for all
        registered notification handles.

        Notification format (AdsNotificationStream):
          - length (UINT32): Size of stamps+data in bytes
          - stamps (UINT32): Number of AdsStampHeader elements (always 1)
          - AdsStampHeader:
            - timestamp (UINT64): 100ns intervals since Windows epoch (01.01.1601)
            - samples (UINT32): Number of AdsNotificationSample elements
            - AdsNotificationSample[]:
              - handle (UINT32): Notification handle
              - size (UINT32): Size of data in bytes
              - data (bytes): Actual data
        """
        import time

        notification_interval = 0.1  # 100ms

        # Windows epoch offset (100ns intervals from 01.01.1601 to 01.01.1970)
        windows_epoch_offset = 116444736000000000

        while self.running:
            await asyncio.sleep(notification_interval)

            if not self._notification_handles or not self._notification_writers:
                continue

            # Get current timestamp in 100ns units since Windows epoch (01.01.1601)
            unix_time = time.time()
            timestamp = int(unix_time * 10_000_000) + windows_epoch_offset

            # Build notification samples for each handle
            samples_data = b""
            num_samples = 0
            for handle, handle_info in self._notification_handles.items():
                # Generate simulated data (zeros for now)
                data_length = handle_info["length"]
                data = b"\x00" * data_length

                # AdsNotificationSample: handle (4) + size (4) + data
                samples_data += struct.pack("<II", handle, data_length) + data
                num_samples += 1

            if num_samples == 0:
                continue

            # Build AdsStampHeader: timestamp (8) + samples_count (4) + samples_data
            stamp_header = struct.pack("<QI", timestamp, num_samples) + samples_data

            # Build AdsNotificationStream: length (4) + stamps (4) + stamp_header
            # length = size of (stamps field + stamp_header)
            stamps_count = 1  # Always 1 stamp per notification
            payload_length = 4 + len(stamp_header)  # stamps (4) + stamp_header
            notification_payload = struct.pack("<II", payload_length, stamps_count)
            notification_payload += stamp_header

            # Send to all connected clients
            for (client_netid, client_port), writer in list(
                self._notification_writers.items()
            ):
                if writer.is_closing():
                    continue

                try:
                    # Get first device's netid for source
                    if self.chain.devices:
                        device = next(iter(self.chain.devices.values()))
                        source_netid = device.get_netid_bytes()
                    else:
                        source_netid = bytes([10, 0, 0, 1, 3, 1])

                    # Build AMS notification message
                    # Command ID 0x8 = ADSSRVID_DEVICENOTE
                    ams_header = struct.pack(
                        "<6sH6sHHHIII",
                        client_netid,  # target netid
                        client_port,  # target port
                        source_netid,  # source netid
                        SYSTEM_SERVICE_PORT,  # source port
                        CommandId.ADSSRVID_DEVICENOTE,  # command
                        StateFlag.AMSCMDSF_ADSCMD,  # state flags (no response expected)
                        len(notification_payload),  # length
                        ErrorCode.ERR_NOERROR,  # error code
                        0,  # invoke id (not used for notifications)
                    )

                    # AMS/TCP header
                    frame_length = len(ams_header) + len(notification_payload)
                    tcp_header = b"\x00\x00" + frame_length.to_bytes(4, "little")

                    # Send notification
                    notification_message = (
                        tcp_header + ams_header + notification_payload
                    )
                    client_netid_str = ".".join(str(b) for b in client_netid)
                    logger.debug(
                        f"Notification outgoing to {client_netid_str}:{client_port}: "
                        f"samples={num_samples}, timestamp={timestamp}, "
                        f"len={len(notification_message)}"
                    )
                    writer.write(notification_message)
                    await writer.drain()

                except Exception as e:
                    logger.debug(f"Failed to send notification to client: {e}")
