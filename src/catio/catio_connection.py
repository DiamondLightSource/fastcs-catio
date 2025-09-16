import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Self, SupportsInt

import numpy.typing as npt

from catio.catio_adapters import CATioFastCSRequest
from catio.devices import AdsSymbol

from .client import AsyncioADSClient


class DisconnectedError(Exception):
    """Raised if the IP connection is disconnected."""

    pass


@dataclass
class CATioConnectionSettings:
    """
    Settings required to establish a TCP connection with a CATio server.
    """

    ip: str
    """The IP address of the TwinCAT server to connect to."""
    ams_netid: str
    """The Ams netid of the TwinCAT server to connect to."""
    ams_port: int
    """The Ams port of the TwinCAT server to connect to."""


@dataclass
class CATioStreamConnection:
    """
    For setting up a CATio client able to read and write to a stream.
    Act as a wrapper for interacting with an AsyncioADSClient \
        and handling I/O communications.
    """

    _catio_client: AsyncioADSClient
    _notification_symbols: dict[SupportsInt, Sequence[AdsSymbol]] = field(
        default_factory=dict
    )
    _subscribed_symbols: list[AdsSymbol] = field(default_factory=list)

    @classmethod
    async def connect(cls, settings: CATioConnectionSettings) -> Self:
        """
        Create a client which will connect to the TwinCAT server and \
            support ADS communication with the attached I/O devices.
        """
        client = await AsyncioADSClient.connected_to(
            target_ip=settings.ip,
            target_ams_net_id=settings.ams_netid,
            target_ams_port=settings.ams_port,
        )
        return cls(client)

    def __post_init__(self):
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()

    async def initialise(self):
        """
        Update the ads client with the current I/O server configuration.
        This includes the detection of all configured hardware in the EtherCAT system
        and of all accessible ads symbol variables.
        """
        await self._catio_client.introspect_IO_server()
        self._notification_symbols = await self._catio_client.get_all_symbols()

    async def query(self, message: CATioFastCSRequest) -> Any:
        response = ""
        try:
            # logging.debug(f"Querying {message} from CATio client")
            response = await self._catio_client.query(
                message.command, *message.args, **message.kwargs
            )
        except ValueError as err:
            logging.debug(f"API call exception:: {err}")

        # Only use this debug logging in last resort, as it can be very verbose.
        # logging.debug(f"Response: {response}")
        return response

    async def add_notifications(self, device_id: int) -> None:
        """
        Register symbol notifications with the ads client for a given device.
        This will include all ads symbols available to this device.

        :params device_id: the id of the EtherCAT device to subscribe to
        """
        # Currently limit to 20 notifications to get system running
        # PROBLEM when too many (? accumulation in queue during time between connect and scan)
        subscription_symbols = self._notification_symbols[device_id][:20]
        for symbol in subscription_symbols:
            print(f"SYMBOL: {symbol.name}")

        await self._catio_client.add_notifications(
            subscription_symbols,  # max_delay_ms=1000, cycle_time_ms=1000)
        )

        self._subscribed_symbols = list(subscription_symbols)
        # Allow a bit of time for the subscription process to complete.
        await asyncio.sleep(0.3)

    def monitor_notifications(self, enabled: bool, flush_period: float = 0.5) -> None:
        """
        Enable or disable the periodic monitoring of symbol notifications by the client.

        :param enabled: True to enable notification monitoring, False to disable it
        :param flush_period: the period (in seconds) at which notifications are flushed
        """
        if enabled:
            self._catio_client.start_notification_monitor(flush_period)
        else:
            self._catio_client.stop_notification_monitor()

    async def get_notifications(self, timeout: int = 60) -> npt.NDArray:
        """
        Get the latest ads symbol notifications from the ads client.

        :param timeout: the maximum time to wait for notifications (in seconds)

        :returns: a numpy array containing the latest notifications
        """
        return await self._catio_client.get_notifications(timeout)

    async def delete_all_notifications(self) -> None:
        """
        Delete the existing ads symbol notifications.

        :params device_id: the id of the EtherCAT device to subscribe to
        """
        logging.info("...deleting active notifications...")
        await self._catio_client.delete_notifications(self._subscribed_symbols)

    async def close(self):
        await self.delete_all_notifications()
        await asyncio.sleep(1)

        await self._catio_client.close()


class CATioConnection:
    """For connecting to a Beckhoff TwinCAT server using a TCP connection."""

    def __init__(self):
        self.__connection: CATioStreamConnection | None = None

    @property
    def _connection(self) -> CATioStreamConnection:
        if self.__connection is None:  # await connection.send_message(message)
            # return await connection.receive_response()
            raise DisconnectedError(
                "Need to call connect() before using a CATioConnection."
            )
        return self.__connection

    async def connect(self, settings: CATioConnectionSettings) -> None:
        """Establish a TCP connection and enable stream communication."""
        self.__connection = await CATioStreamConnection.connect(settings)
        logging.info(
            f"Opened stream communication with ADS server at {time.strftime('%X')}"
        )

    async def initialise(
        self,
    ) -> None:
        """Initialise the client connection with the current server settings."""
        await self._connection.initialise()

    async def send_query(self, message: CATioFastCSRequest) -> Any:
        async with self._connection as connection:
            return await connection.query(message)

    async def close(self):
        """Stop the communication stream and close the TCP connection \
            with the TwinCAT server."""
        async with self._connection as connection:
            await connection.close()
            self.__connection = None
        logging.info(
            f"Closed stream communication with ADS server at {time.strftime('%X')}"
        )

    async def add_notifications(self, device_id: int) -> None:
        """
        Add symbol notifications for an EtherCAT device on the I/O server.

        :params device_id: the id of the device whose notifications must be setup
        """
        await self._connection.add_notifications(device_id)

    async def get_notification_streams(self, timeout: int = 60) -> npt.NDArray:
        """
        Get the latest ads symbol notifications from the connection stream.

        :param timeout: the maximum time to wait for notifications (in seconds)

        :returns: a numpy array containing the latest notifications
        """
        return await self._connection.get_notifications(timeout)

    def enable_notification_monitoring(
        self, enabled: bool, flush_period: float = 0.5
    ) -> None:
        """
        Enable or disable the periodic monitoring of notifications.

        :param enabled: True to enable notification monitoring, False to disable it
        :param flush_period: the period (in seconds) at which notifications are flushed
        """
        if enabled:
            self._connection.monitor_notifications(True, flush_period)
        else:
            self._connection.monitor_notifications(False)
