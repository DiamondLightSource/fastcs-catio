"""
Mock ADS Server for testing CATio client connections.

This module provides a mock ADS (Automation Device Specification) server
that can simulate responses to client requests, enabling testing without
a real Beckhoff device.

Use the mock server in the tests by:
1. Adding `@pytest.mark.asyncio` to the async test functions
2. Using the `mock_ads_server` fixture as a parameter
3. Connecting the client to `127.0.0.1:48898` with netid `127.0.0.1.1.1`
"""

from __future__ import annotations

import asyncio
import logging
import random
import struct
from collections.abc import Callable
from typing import Any, SupportsInt

import numpy as np

from fastcs_catio._constants import (
    AdsState,
    CommandId,
    ErrorCode,
    StateFlag,
)
from fastcs_catio._types import AmsNetId
from fastcs_catio.devices import AdsSymbol
from fastcs_catio.messages import (
    AdsAddDeviceNotificationResponse,
    AdsDeleteDeviceNotificationResponse,
    AdsReadDeviceInfoResponse,
    AdsReadResponse,
    AdsReadStateResponse,
    AdsReadWriteResponse,
    AdsWriteResponse,
)
from fastcs_catio.utils import get_local_netid_str

logger = logging.getLogger(__name__)


class MockADSServer:
    """
    A mock ADS server that simulates a Beckhoff TwinCAT device.

    This server accepts AMS connections over TCP and responds to ADS commands with
    mock data, allowing testing of the CATio client without a real device.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 48898):
        """
        Initialize the mock ADS server.

        :param host: Host address to bind to (default: 127.0.0.1)
        :param port: Port to listen on (default: 48898)
        """
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.local_netid = AmsNetId.from_string(get_local_netid_str())
        self.running = False

        # Mock data info
        self.symbols: dict[AdsSymbol, bytes] = {}
        self.device_info = {
            "DeviceName": b"MockDevice",
            "DeviceVersion": b"1.0.0",
        }
        self.ads_state = AdsState.ADSSTATE_RUN

        # Notification handles and subscriptions
        self._notification_handles: dict[int, dict[str, Any]] = {}
        self._next_handle = 1

        # Message handlers
        self._handlers: dict[CommandId, Callable] = {
            CommandId.ADSSRVID_READSTATE: self._handle_read_state,
            CommandId.ADSSRVID_READDEVICEINFO: self._handle_read_device_info,
            CommandId.ADSSRVID_READ: self._handle_read,
            CommandId.ADSSRVID_WRITE: self._handle_write,
            CommandId.ADSSRVID_READWRITE: self._handle_read_write,
            CommandId.ADSSRVID_ADDDEVICENOTE: self._handle_add_notification,
            CommandId.ADSSRVID_DELETEDEVICENOTE: self._handle_delete_notification,
        }

    async def start(self) -> None:
        """Start the mock ADS server."""
        self.server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        self.running = True
        logger.info(f"Mock ADS server started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the mock ADS server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.running = False
            logger.info("Mock ADS server stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle a new client connection.

        :param reader: Stream reader for incoming data
        :param writer: Stream writer for outgoing data
        """
        addr = writer.get_extra_info("peername")
        logger.debug(f"Client connected from {addr}")

        try:
            while True:
                # Read frame size
                size_bytes = await reader.readexactly(2)
                if not size_bytes:
                    break

                # Read frame length
                length_bytes = await reader.readexactly(4)
                frame_length = int.from_bytes(length_bytes, byteorder="little")

                # Read AMS header
                header_bytes = await reader.readexactly(32)

                # Read payload
                payload_bytes = await reader.readexactly(frame_length - 32)

                # Process message
                response = await self._process_ams_message(header_bytes, payload_bytes)

                # Send response
                writer.write(response)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.debug(f"Client {addr} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_ams_message(
        self, header_bytes: bytes, payload_bytes: bytes
    ) -> bytes:
        """
        Process an incoming AMS message and generate a response.

        :param header_bytes: Raw AMS header bytes
        :param payload_bytes: Raw payload bytes

        :returns: Raw response bytes
        """
        try:
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
            ) = struct.unpack("<6sHH6sHHHHI", header_bytes)

            command_id = CommandId(command_id)
            invoke_id = np.uint32(invoke_id)

            # Get handler for this command
            handler = self._handlers.get(command_id)
            if not handler:
                logger.warning(f"No handler for command {command_id}")
                response_payload = b""
            else:
                response_payload = await handler(payload_bytes)

            # Build response header
            response_header = struct.pack(
                "<6sHH6sHHHHI",
                source_netid,  # target becomes source
                source_port,
                target_netid,  # source becomes target
                target_port,
                command_id.value,
                StateFlag.AMSCMDSF_RESPONSE.value | StateFlag.AMSCMDSF_ADSCMD.value,
                len(response_payload),
                ErrorCode.ERR_NOERROR.value,
                invoke_id,
            )

            # Build complete response
            frame_length = len(response_header) + len(response_payload)
            frame_length_bytes = frame_length.to_bytes(4, byteorder="little")

            response = (
                b"\x00\x00" + frame_length_bytes + response_header + response_payload
            )

            logger.debug(f"Sending response for command {command_id}")
            return response

        except Exception as e:
            logger.error(f"Error processing AMS message: {e}")
            return b""

    # ===================================================================
    # ADS symbol data management
    # ===================================================================

    def set_symbol_data(self, name: str, value: Any, offset: SupportsInt = 0x1) -> None:
        """
        Set mock data for a symbol.

        :param name: Symbol name
        :param value: Symbol value
        """
        # Convert input to numpy ndarray if not already
        if not isinstance(value, np.ndarray):
            value = np.array(value)

        symbol = AdsSymbol(
            parent_id=1,
            name=name,
            dtype=value.dtype,
            size=value.size,
            group=0x0001,
            offset=offset,
            comment="default test symbol settings",
            handle=None,
        )

        try:
            b_val = value.tobytes()
        except Exception as err:
            raise TypeError("Cannot convert data to NumPy array") from err

        self.symbols[symbol] = b_val

    def get_symbol_data(self, name: str) -> bytes | None:
        """
        Get mock data for a symbol.

        :param name: Symbol name

        :returns: Symbol data as bytes, or None if not found
        """
        for s in self.symbols.keys():
            if s.name is name:
                return self.symbols.get(s)
        return None

    def get_symbol_by_name(self, name: str) -> AdsSymbol | None:
        """
        Get an AdsSymbol by its name.

        :param name: Symbol name

        :returns: AdsSymbol instance, or None if not found
        """
        for symbol in self.symbols.keys():
            if symbol.name == name:
                return symbol
        return None

    def get_random_symbol(self) -> AdsSymbol:
        """
        Get a random symbol from the mock server.

        :returns: An AdsSymbol instance

        :raises ValueError: If no symbol data is available in the mock server
        """
        if not self.symbols:
            raise ValueError("No symbol data available in mock server")

        return random.choice(list(self.symbols.keys()))

    def get_random_value(self, symbol: AdsSymbol) -> Any:
        """
        Generate a random value for a given ads symbol.
        Supports floats, integers, and booleans.

        :param symbol: The AdsSymbol to generate a value for

        :returns: A random value matching the ads symbol dtype

        :raises TypeError: If the dtype is unsupported
        """
        dtype = symbol.dtype
        rng = np.random.default_rng()

        # Handle floating-point types
        if np.issubdtype(dtype, np.floating):
            # NumPy supports dtype directly for float32 and float64
            if dtype in (np.float32, np.float64):
                return rng.random(dtype=dtype)
            else:
                # For other float types, generate as float64 and cast
                return np.array(rng.random(dtype=np.float64)).astype(dtype)

        # Handle integer types
        elif np.issubdtype(dtype, np.integer):
            info = np.iinfo(dtype)
            return rng.integers(low=info.min, high=info.max, dtype=dtype)

        # Handle boolean
        elif np.issubdtype(dtype, np.bool_):
            return rng.choice([True, False])

        else:
            raise TypeError(f"Unsupported dtype: {dtype}")

    def get_random_symbol_value_pair(self) -> tuple[AdsSymbol, Any]:
        """
        Get a random symbol and its corresponding random value.

        :returns: A tuple of (AdsSymbol, value)
        """
        symbol = self.get_random_symbol()
        value = self.get_random_value(symbol)

        return (symbol, value)

    # ===================================================================
    # Message Handlers for common ADS commands
    # ===================================================================

    async def _handle_read_state(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_READSTATE request.

        :returns: a series of bytes representing the device state
        """
        response = AdsReadStateResponse(
            result=ErrorCode.ERR_NOERROR,
            ads_state=self.ads_state,
            device_state=0,
        )
        return response.to_bytes()

    async def _handle_read_device_info(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_READDEVICEINFO request.

        :returns: a series of bytes representing the device information
        """
        response = AdsReadDeviceInfoResponse(
            result=ErrorCode.ERR_NOERROR,
            major_version=1,
            minor_version=0,
            version_build=1234,
            device_name=self.device_info["DeviceName"],
        )
        return response.to_bytes()

    async def _handle_read(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_READ request.

        :returns: a series of bytes representing the response to symbol reads \
            (read response value is set to zero by default)
        """
        # Parse read request
        index_group, index_offset, length = struct.unpack("<HHI", payload[:8])

        # Get symbol data
        symbol_data = b"\x00" * length

        response = AdsReadResponse(
            result=ErrorCode.ERR_NOERROR,
            length=len(symbol_data),
            data=symbol_data,
        )
        return response.to_bytes()

    async def _handle_write(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_WRITE request.

        :returns: a series of bytes representing the response to symbol writes \
            (write response value is set to 'no error' by default)
        """
        # Parse write request
        index_group, index_offset, length = struct.unpack("<HHI", payload[:8])

        response = AdsWriteResponse(result=ErrorCode.ERR_NOERROR)
        return response.to_bytes()

    async def _handle_read_write(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_READWRITE request.

        :returns: a series of bytes representing the response to combined \
            read/write operation (read response value is set to zero by default)
        """
        # Parse read-write request
        index_group, index_offset, read_len, write_len = struct.unpack(
            "<HHII", payload[:12]
        )

        # Get symbol data
        symbol_data = b"\x00" * read_len

        response = AdsReadWriteResponse(
            result=ErrorCode.ERR_NOERROR,
            length=len(symbol_data),
            data=symbol_data,
        )
        return response.to_bytes()

    async def _handle_add_notification(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_ADDDEVICENOTIFICATION request.

        :returns: a series of bytes representing the response to subscription additions\
             (notification handle is automatically incremented by default)
        """
        # Allocate a notification handle
        handle = self._next_handle
        self._next_handle += 1

        # Parse add notification request
        index_group, index_offset, length, transmission_mode, max_delay, cycle_time = (
            struct.unpack("<HHIHII", payload[:20])
        )

        # Store notification subscription
        self._notification_handles[handle] = {
            "index_group": index_group,
            "index_offset": index_offset,
            "length": length,
            "transmission_mode": transmission_mode,
            "max_delay": max_delay,
            "cycle_time": cycle_time,
        }

        response = AdsAddDeviceNotificationResponse(
            result=ErrorCode.ERR_NOERROR,
            handle=handle,
        )
        return response.to_bytes()

    async def _handle_delete_notification(self, payload: bytes) -> bytes:
        """
        Handle ADSSRVID_DELDEVICENOTIFICATION request.

        :returns: a series of bytes representing the response to subscription deletions\
             ('no error' response is returned by default)
        """
        # Parse delete notification request
        (handle,) = struct.unpack("<I", payload[:4])

        # Remove notification subscription
        if handle in self._notification_handles:
            del self._notification_handles[handle]

        response = AdsDeleteDeviceNotificationResponse(result=ErrorCode.ERR_NOERROR)
        return response.to_bytes()
