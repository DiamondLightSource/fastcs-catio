import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Self, SupportsInt

import numpy.typing as npt
from fastcs.tracer import Tracer

from catio.devices import AdsSymbol

from .client import AsyncioADSClient


class CATioFastCSRequest:
    """
    Request object sent to the catio client (string subclass).
    Used to encapsulate all the information needed to perform a query.
    """

    def __init__(self, command: str, *args, **kwargs):
        self.command = command
        """The command to be executed by the CATio client."""
        self.args = args
        """Optional positional arguments for the command."""
        self.kwargs = kwargs
        """Optional keyword arguments for the command."""

    def __repr__(self) -> str:
        """Return a string representation of the CATio request."""
        return repr(
            self.command
            + "("
            + ", ".join(self.args)
            + ", "
            + ", ".join([f"{k}={v!r}" for k, v in self.kwargs.items()])
            + ")"
        )


@dataclass
class CATioFastCSResponse:
    """
    Response object received by the catio client.
    Used to potentially manipulate the received information.
    """

    value: Any
    """The response received from the CATio client."""

    def to_string(self) -> str:
        """Attempt to return a string representation of the CATio response.

        :returns: the CATio response to a query as a string

        :raises ValueError: if the received response cannot be stringified
        """
        try:
            return repr(self.value)
        except Exception as err:
            raise ValueError from err


class DisconnectedError(Exception):
    """Raised if the IP connection is disconnected."""

    pass


@dataclass
class CATioServerConnectionSettings:
    """
    Settings required to establish a TCP connection with a CATio server.
    Act as a wrapper for connection parameters.
    """

    ip: str = "127.0.0.1"
    """The IP address of the TwinCAT server to connect to."""
    ams_netid: str = "127.0.0.1.1.1"
    """The Ams netid of the TwinCAT server to connect to."""
    ams_port: int = 25565
    """The Ams port of the TwinCAT server to connect to."""

    def __repr__(self) -> str:
        return f"TCP connection to remote server with netid {self.ams_netid}, \
            at address {self.ip}, on port {self.ams_port}"


@dataclass
class CATioStreamConnection:
    """
    For setting up a CATio client able to read and write to a stream.
    Act as a wrapper for interacting with an AsyncioADSClient \
        and handling I/O communications.
    One instance of this class should be created per TCP connection.
    One instance of AsyncioADSClient will be created and managed internally.
    """

    _connection_settings: CATioServerConnectionSettings
    """The connection settings used to connect to the CATio server."""
    _catio_client: AsyncioADSClient
    """The ADS client used to communicate with the CATio server."""
    _notification_symbols: dict[SupportsInt, Sequence[AdsSymbol]] = field(
        default_factory=dict
    )
    """A mapping of device ids to their corresponding notification symbols."""
    _subscribed_symbols: list[AdsSymbol] = field(default_factory=list)
    """The list of currently subscribed notification symbols."""

    @property
    def settings(self) -> CATioServerConnectionSettings:
        """The connection settings used to connect to the CATio server."""
        return self._connection_settings

    @property
    def client(self) -> AsyncioADSClient:
        """The ADS client used to communicate with the CATio server."""
        return self._catio_client

    @property
    def notification_symbols(self) -> dict[SupportsInt, Sequence[AdsSymbol]]:
        """A mapping of device ids to their corresponding notification symbols."""
        return self._notification_symbols

    @property
    def subscribed_symbols(self) -> list[AdsSymbol]:
        """The list of currently subscribed notification symbols."""
        return self._subscribed_symbols

    @classmethod
    async def connect(cls, settings: CATioServerConnectionSettings) -> Self:
        """
        Create a client which will connect to the TwinCAT server and \
            support ADS communication with the attached I/O devices.

        :param settings: the connection settings to use for connecting to the server

        :returns: an instance of CATioStreamConnection with an active client
        """
        ads_client = await AsyncioADSClient.connected_to(
            target_ip=settings.ip,
            target_ams_net_id=settings.ams_netid,
            target_ams_port=settings.ams_port,
        )
        return cls(settings, ads_client)

    def __post_init__(self) -> None:
        """
        Initialise the asyncio lock for managing concurrent access to the client.
        """
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        """
        Acquire the asyncio lock to ensure exclusive access to the client.
        """
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Release the asyncio lock to allow other coroutines to access the client.
        """
        self._lock.release()
        # pass

    async def initialise(self) -> None:
        """
        Update the ads client with the current I/O server configuration.
        This includes the detection of all configured hardware in the EtherCAT system
        and of all accessible ads symbol variables.

        If the server configuration changes, this method should be called again.
        """
        await self.client.introspect_io_server()
        self._notification_symbols = await self.client.get_all_symbols()

    async def command(self, command: str, *args, **kwargs) -> None:
        """
        Send a message command to the CATio client.
        This message command will be translated as an API function call.

        :param command: the command to send to the client
        :param args: positional arguments for the command
        :param kwargs: keyword arguments for the command
        """
        try:
            await self.client.command(command, *args, **kwargs)
        except ValueError as err:
            logging.debug(f"API call failed with error: {err}")

    async def query(self, message: CATioFastCSRequest) -> CATioFastCSResponse:
        """
        Send a message request to the catio client.
        This message request will be translated as an API function call.

        :param message: a CATio request message which will be routed via the client.

        :returns: the response to the query as received by the CATio client
        """
        response = ""
        try:
            response = await self.client.query(
                message.command, *message.args, **message.kwargs
            )
        except ValueError as err:
            logging.debug(f"API call failed with error: {err}")

        # # Very verbose logging!
        # logging.debug(f"CATio client response to '{message}' query: {response}")
        return CATioFastCSResponse(response)

    async def add_notifications(self, device_id: int) -> None:
        """
        Register symbol notifications with the ads client for a given device.
        This will include all ads symbols available to this device.

        :param device_id: the id of the EtherCAT device to subscribe to

        :raises ValueError: if no notification symbols are found for the device
        """
        if device_id not in self.notification_symbols:
            raise ValueError(
                f"No notification symbols found for device id {device_id}."
            )
        subscription_symbols = self.notification_symbols[device_id]
        self._subscribed_symbols = list(subscription_symbols)

        await self.client.add_notifications(
            subscription_symbols,  # max_delay_ms=1000, cycle_time_ms=1000
        )
        logging.info(
            f"Subscribed to {len(subscription_symbols)} symbols "
            + f"for device id {device_id}."
        )
        # Small delay to avoid overloading the server after the subscription process.
        await asyncio.sleep(0.3)

    def monitor_notifications(self, enabled: bool, flush_period: float = 0.5) -> None:
        """
        Enable or disable the periodic monitoring of symbol notifications by the client.
        This will start/stop a background task which periodically checks for new
        notifications and processes them.

        :param enabled: True to enable notification monitoring, False to disable it
        :param flush_period: the period (in seconds) at which notifications are flushed
        """
        if enabled:
            self.client.start_notification_monitor(flush_period)
        else:
            self.client.stop_notification_monitor()

    async def get_notifications(self, timeout: int = 60) -> npt.NDArray:
        """
        Get the latest ads symbol notifications from the ads client.
        This will wait for new notifications to arrive, up to the specified timeout.

        :param timeout: the maximum time to wait for notifications (in seconds)

        :returns: a numpy array containing the latest notifications
        """
        return await self.client.get_notifications(timeout)

    async def delete_all_notifications(self) -> None:
        """
        Delete the existing ads symbol notifications.
        This will unsubscribe from all currently subscribed symbols.

        :param device_id: the id of the EtherCAT device to subscribe to
        """
        logging.info("...deleting active notifications...")
        await self.client.delete_notifications(self._subscribed_symbols)

    async def close(self) -> None:
        """
        Stop any background tasks related to notification monitoring, \
            unsubscribe to all symbol notifications \
                and close the client connection with the catio server.
        """
        await self.delete_all_notifications()
        await asyncio.sleep(1)

        await self.client.close()


class CATioConnection(Tracer):
    """
    For connecting to a Beckhoff TwinCAT server using a TCP connection.
    This class manages a CATioStreamConnection instance \
        which handles the underlying ADS communication.
    One instance of this class should be created per TCP connection.
    """

    def __init__(self, connection: CATioStreamConnection | None = None):
        super().__init__()
        self.__connection: CATioStreamConnection | None = connection
        """The underlying CATio stream connection."""

    @property
    def _connection(self) -> CATioStreamConnection:
        """
        The underlying CATio stream connection.

        :raises DisconnectedError: if no connection is established
        """
        if self.__connection is None:
            raise DisconnectedError(
                "No open connection with the CATio system. Call connect() first."
            )
        return self.__connection

    @_connection.setter
    def _connection(self, value: CATioStreamConnection | None) -> None:
        """
        Set the underlying CATio stream connection.

        :param value: the new connection to set, or None to disconnect
        """
        self.__connection = value

    @property
    def settings(self) -> CATioServerConnectionSettings:
        """The connection settings used to connect to the CATio server."""
        return self._connection.settings

    @property
    def client(self) -> AsyncioADSClient:
        """The ADS client used to communicate with the CATio server."""
        return self._connection.client

    def is_defined(self) -> bool:
        """
        Check if a valid CATio connection has been defined.

        :returns: True if a connection is established, False otherwise
        """
        return self.__connection is not None

    async def connect(self, settings: CATioServerConnectionSettings) -> None:
        """
        Establish a TCP connection and enable stream communication.

        :param settings: the connection settings to use for connecting to the server
        """
        self._connection = await CATioStreamConnection.connect(settings)
        logging.info(
            f"Opened stream communication with ADS server at {time.strftime('%X')}"
        )

    async def initialise(self) -> None:
        """
        Initialise the client connection with the current server settings.
        This includes the detection of all configured hardware in the EtherCAT system \
            and of all accessible ads symbol variables.
        """
        await self._connection.initialise()

    async def send_command(self, message: CATioFastCSRequest) -> None:
        """
        Send a message command to the CATio client.
        This message command will be translated as an API function call to the client.

        :param message: a CATio request message which will be routed via the client
        """
        async with self._connection as connection:
            await connection.command(message.command, *message.args, **message.kwargs)

    async def send_query(self, message: CATioFastCSRequest) -> Any:
        """
        Send a message request to the CATio client and return the response.
        This message request will be translated as an API function call to the client.

        param message: a CATio request message which will be routed via the client.

        :returns: the response to the query as received by the CATio client
        """
        async with self._connection as connection:
            response = await connection.query(message)
            self.log_event(
                "Received query response",
                query=message.command,
                response=response.to_string(),
            )
            return response.value

    async def close(self) -> None:
        """
        Stop the communication stream and \
            close the TCP connection with the TwinCAT server.
        """
        async with self._connection as connection:
            await connection.close()
            self._connection = None
        logging.info(
            f"Closed stream communication with ADS server at {time.strftime('%X')}"
        )

    async def add_notifications(self, device_id: int) -> None:
        """
        Add symbol notifications for a given EtherCAT device on the I/O server.
        This will include all ads symbols available to this device.

        :param device_id: the id of the device whose notifications must be setup
        """
        await self._connection.add_notifications(device_id)

    async def get_notification_streams(self, timeout: int = 60) -> npt.NDArray:
        """
        Get the latest ads symbol notifications from the connection stream.
        This will wait for new notifications to arrive, up to the specified timeout.

        :param timeout: the maximum time to wait for notifications (in seconds)

        :returns: a numpy array containing the latest notifications
        """
        return await self._connection.get_notifications(timeout)

    def enable_notification_monitoring(
        self, enabled: bool, flush_period: float = 0.5
    ) -> None:
        """
        Enable or disable the periodic monitoring of notifications.
        This will start/stop a background task which periodically checks for \
            new notifications and processes them.

        :param enabled: True to enable notification monitoring, False to disable it
        :param flush_period: the period (in seconds) at which notifications are flushed
        """
        if enabled:
            self._connection.monitor_notifications(True, flush_period)
            logging.debug("Notification monitoring enabled.")
        else:
            self._connection.monitor_notifications(False)
            logging.debug("Notification monitoring disabled.")
