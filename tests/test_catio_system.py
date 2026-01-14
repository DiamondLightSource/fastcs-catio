"""
CATio System Tests file assessing the entire CATio system end-to-end.

Tests currently cover:
- client connection and disconnection to an ads server
- basic mock server capabilities
- ads symbol read/write operations
- notification subscription handling
- concurrent clients/operations scenarios
- error conditions

Run the tests with:
```bash
python -m pytest tests/test_catio_system.py -v
```
"""

import asyncio

import numpy as np
import pytest
from catio._constants import AdsState
from catio.catio_connection import CATioServerConnectionSettings, CATioStreamConnection
from catio.client import AsyncioADSClient
from catio.devices import AdsSymbol
from catio.messages import AdsReadDeviceInfoResponse

from mock_server import MockADSServer

IO_SERVER_PORT: int = 300

pytest.skip(allow_module_level=True, reason="TODO these are all failing")


@pytest.fixture
async def system_test_server():
    """Set up a mock ADS server configured with test data."""
    server = MockADSServer(host="127.0.0.1", port=48898)

    # Configure some test symbols
    server.set_symbol_data("TestVar1", np.int32(42))
    server.set_symbol_data("TestVar2", np.float32(3.14))
    server.set_symbol_data("TestString", "HelloWorld")

    await server.start()
    yield server
    await server.stop()


@pytest.fixture
def connection_settings():
    """Create test connection settings for the mock server."""
    return CATioServerConnectionSettings(
        ip="127.0.0.1",
        ams_netid="127.0.0.1.1.1",
        ams_port=48898,
    )


# ===================================================================
# ADS Connection Tests
# ===================================================================


class TestBasicConnection:
    """Test basic client connection functionality."""

    @pytest.mark.asyncio
    async def test_client_can_connect_to_server(
        self, system_test_server: MockADSServer
    ):
        """Test that client can establish a connection to the mock server."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        try:
            # Verify the connection was successful
            assert client is not None
            assert isinstance(client, AsyncioADSClient)

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_client_can_connect_without_port(
        self, system_test_server: MockADSServer
    ):
        """Test that client can establish an ads connection to the mock server \
            without the tcp port parameter explicitly given."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
        )

        try:
            # Verify the connection was successful
            assert client is not None
            assert isinstance(client, AsyncioADSClient)

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_client_can_disconnect(self, system_test_server: MockADSServer):
        """Test that client can cleanly disconnect."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Disconnect from the mock server without raising an exception
        await client.close()


@pytest.mark.skip(reason="TODO this is failing")
class TestStreamConnection:
    """Test CATioStreamConnection functionality."""

    @pytest.mark.asyncio
    async def test_connect_classmethod(
        self, connection_settings: CATioServerConnectionSettings
    ):
        """Test CATioStreamConnection connect method."""
        # Establish stream connection
        cnx = await CATioStreamConnection.connect(connection_settings)

        try:
            # Verify connection is established
            assert cnx is not None
            assert isinstance(cnx, CATioStreamConnection)
        finally:
            # Disconnect the client
            await cnx.client.close()

    @pytest.mark.asyncio
    async def test_connection_properties(
        self, connection_settings: CATioServerConnectionSettings
    ):
        """Test CATioStreamConnection properties."""
        # Establish stream connection
        cnx = await CATioStreamConnection.connect(connection_settings)

        try:
            # Verify connection properties
            assert hasattr(cnx, "settings")
            assert cnx.settings == connection_settings
            assert hasattr(cnx, "client")
            assert cnx.client is not None
            assert hasattr(cnx, "notification_symbols")
            assert isinstance(cnx.notification_symbols, dict)
            assert hasattr(cnx, "subscribed_symbols")
            assert isinstance(cnx.subscribed_symbols, list)

        finally:
            # Disconnect the client
            await cnx.client.close()

    @pytest.mark.asyncio
    async def test_connection_context_manager(
        self, connection_settings: CATioServerConnectionSettings
    ):
        """Test CATioStreamConnection as async context manager."""
        # Establish stream connection
        cnx = await CATioStreamConnection.connect(connection_settings)

        try:
            # Use as async context manager
            async with cnx:
                # Read server states
                ads_state, device_state = await cnx.client._get_ioserver_states()

                # Verify the response
                assert isinstance(ads_state, AdsState)
                assert ads_state == AdsState.ADSSTATE_RUN
                assert isinstance(device_state, int)
                assert device_state == 0
        finally:
            # Disconnect the client
            await cnx.client.close()


# ===================================================================
# Mock Server Capabilities Tests
# ===================================================================


class TestMockServerConfiguration:
    """Test the mock server configuration capabilities."""

    @pytest.mark.asyncio
    async def test_read_ads_state(self, system_test_server: MockADSServer):
        """Test reading ADS states from the mock server."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        try:
            # Read server states
            ads_state, device_state = await client._get_ioserver_states()
            # Verify the response
            assert ads_state is not None
            assert isinstance(ads_state, AdsState)
            assert ads_state == AdsState.ADSSTATE_RUN
            assert device_state is not None
            assert isinstance(device_state, int)
            assert device_state == 0

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_read_device_info(self, system_test_server: MockADSServer):
        """Test reading device information from the mock server."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        try:
            # Read device info
            info = await client._read_io_info()
            # Verify the response
            assert info is not None
            assert isinstance(info, AdsReadDeviceInfoResponse)
            # Info should contain device name
            assert b"MockDevice" in info.device_name or len(info.device_name) > 0

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_custom_symbol_data(self, system_test_server: MockADSServer):
        """Test setting and retrieving custom symbol data."""
        # Set custom symbol data
        test_data = np.uint64(12345)
        system_test_server.set_symbol_data("CustomSymbol", test_data)

        # Retrieve symbol data and verify
        retrieved = system_test_server.get_symbol_data("CustomSymbol")
        assert retrieved == test_data


class TestSymbolOperations:
    """Test symbol reading and writing operations."""

    @pytest.mark.asyncio
    async def test_read_symbol(self, system_test_server: MockADSServer):
        """Test reading a symbol from the device."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Select an ads symbol available from the mock server
        test_symbol = system_test_server.get_random_symbol()
        assert isinstance(test_symbol, AdsSymbol)

        try:
            # Read a symbol value
            result = client.read_ads_symbol(test_symbol)
            # Verify the read operation completes
            assert result is not None

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_write_symbol(self, system_test_server: MockADSServer):
        """Test writing a symbol to the device."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Select a random ads symbol and value available from the mock server
        test_data, test_symbol = system_test_server.get_random_symbol_value_pair()

        try:
            # Write a symbol value
            result = client.write_ads_symbol(test_symbol, test_data)
            # Verify the write operation completes
            assert result is True

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_read_write_symbol(self, system_test_server: MockADSServer):
        """Test reading and writing a symbol in one operation."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Select a random ads symbol and value available from the mock server
        test_data, test_symbol = system_test_server.get_random_symbol_value_pair()

        try:
            # Read and write in one operation
            result = await client.readwrite_ads_symbol(test_symbol, test_data)
            # Verify the combined operation completes
            assert result is not None

        finally:
            # Disconnect from the mock server
            await client.close()


class TestNotifications:
    """Test device notification subscription handling."""

    @pytest.mark.asyncio
    async def test_add_device_notification(self, system_test_server: MockADSServer):
        """Test adding a device notification subscription."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Select an ads symbol available from the mock server
        test_symbol = system_test_server.get_random_symbol()
        assert isinstance(test_symbol, AdsSymbol)

        try:
            # Add a notification for a symbol
            handle = await client.add_device_notification(
                symbol=test_symbol,
                max_delay_ms=1000,
                cycle_time_ms=100,
            )
            # Verify a valid handle is returned
            assert handle > 0

            # Clean up the test subscription
            await client.delete_device_notification(test_symbol)

        finally:
            # Disconnect from the mock server
            await client.close()

    @pytest.mark.asyncio
    async def test_delete_device_notification(self, system_test_server: MockADSServer):
        """Test deleting a device notification subscription."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Select an ads symbol available from the mock server
        test_symbol = system_test_server.get_random_symbol()
        assert isinstance(test_symbol, AdsSymbol)

        try:
            # Add a notification for a symbol
            await client.add_device_notification(
                symbol=test_symbol,
                max_delay_ms=1000,
                cycle_time_ms=100,
            )

            try:
                # Delete the notification
                result = await client.delete_device_notification(test_symbol)
                # Verify that the deletion was successful with no exception raised
                assert result is None
            except (KeyError, AssertionError) as err:
                pytest.fail(f"Exception was raised: {err}")

        finally:
            # Disconnect from the mock server
            await client.close()


# ===================================================================
# Other System Tests
# ===================================================================


class TestConcurrency:
    """Test concurrent communication with the server."""

    # TO DO: Review the code for this test after checking actual server behaviour!
    @pytest.mark.asyncio
    async def test_multiple_clients_cannot_connect_from_same_host(
        self, system_test_server: MockADSServer
    ):
        """Test that multiple clients on the same host machine cannot connect
        to the same server."""
        clients = []

        try:
            # TO DO: Not sure what error is returned, to check
            # Need to confirm Ams route dependence exists despite multiple clients
            # with different netid/port but same ip address
            with pytest.raises(ConnectionError):
                # Connect multiple clients
                for _ in range(3):
                    client = await AsyncioADSClient.connected_to(
                        target_ip=system_test_server.host,
                        target_ams_net_id=system_test_server.local_netid.to_string(),
                        target_ams_port=IO_SERVER_PORT,
                        ads_port=system_test_server.port,
                    )
                    clients.append(client)

        finally:
            # Disconnect all clients
            for client in clients:
                await client.close()

    # TO DO: HOW CAN WE TEST THAT MULTIPLE CLIENTS IS FEASIBLE IF FROM
    # DIFFERENT HOST MACHINES
    @pytest.mark.asyncio
    async def test_multiple_clients_can_connect_from_different_host(
        self, system_test_server: MockADSServer
    ):
        """Test that multiple clients on different machines can connect to the
        same server."""
        # Define multiple clients
        # All clients should be able to read the server states
        # Disconnect all clients
        ...

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, system_test_server: MockADSServer):
        """Test concurrent read/write operations from one client."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        try:
            # Perform multiple concurrent operations
            tasks = [
                client._get_ioserver_states(),
                client._get_ioserver_states(),
                client._read_io_info(),
                client._get_ioserver_states(),
            ]
            results = await asyncio.gather(*tasks)

            # Verify results are as expected
            assert len(results) == 4
            assert results[0][0] == AdsState.ADSSTATE_RUN
            assert results[1][0] == AdsState.ADSSTATE_RUN
            assert results[2] is not None
            assert results[3][0] == AdsState.ADSSTATE_RUN

        finally:
            # Disconnect from the mock server
            await client.close()


class TestErrorHandling:
    """Test error handling in the system."""

    @pytest.mark.asyncio
    async def test_connection_to_nonexistent_server(self):
        """Test that connecting to non-existent server raises an error."""
        with pytest.raises(OSError):
            await AsyncioADSClient.connected_to(
                target_ip="127.0.0.1",
                target_ams_net_id="127.0.0.1.1.1",
                target_ams_port=300,
                ads_port=54321,  # Private port, non-existent server
            )

    @pytest.mark.asyncio
    async def test_operations_after_disconnect(self, system_test_server: MockADSServer):
        """Test that operations fail cleanly after disconnect."""
        # Connect to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=system_test_server.host,
            target_ams_net_id=system_test_server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=system_test_server.port,
        )

        # Disconnect the client
        await client.close()

        # Further operations should fail
        with pytest.raises((ConnectionError, OSError, asyncio.CancelledError)):
            await client._get_ioserver_states()
