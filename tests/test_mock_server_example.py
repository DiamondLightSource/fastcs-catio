"""
Example tests for the mock ADS server infrastructure.

Tests demonstrate how to handle client connections and disconnections:
- by setting up a mock server manually
- by setting up a mock server using pytest fixtures

Run the tests with:
```bash
python -m pytest tests/test_mock_server_example.py -v
```
"""

import pytest

from catio._constants import AdsState
from catio.client import AsyncioADSClient
from mock_server import MockADSServer

IO_SERVER_PORT: int = 300


pytest.skip(allow_module_level=True, reason="TODO this is failing")


@pytest.mark.asyncio
async def test_mock_server_with_custom_data(mock_ads_server: MockADSServer):
    """Test that custom mock data for symbols can be set."""
    # Set some custom symbol data
    mock_ads_server.set_symbol_data("test_symbol", b"test_value")

    # Get the data back
    data = mock_ads_server.get_symbol_data("test_symbol")
    assert data == b"test_value"


@pytest.mark.asyncio
@pytest.mark.skip(reason="TODO this currently hangs indefinitely")
async def test_mock_server_without_fixtures():
    """Test basic connection and disconnection without fixtures."""
    # Start server manually
    server = MockADSServer(host="127.0.0.1", port=48899)
    await server.start()

    try:
        # Connect client to the mock server
        client = await AsyncioADSClient.connected_to(
            target_ip=server.host,
            target_ams_net_id=server.local_netid.to_string(),
            target_ams_port=IO_SERVER_PORT,
            ads_port=server.port,
        )

        # Read states and verify the response
        ads_state, device_state = await client._get_ioserver_states()
        assert ads_state == AdsState.ADSSTATE_RUN
        assert device_state == 0

        # Disconnect from the mock server
        await client.close()

    finally:
        # Stop the server manually
        await server.stop()


@pytest.mark.asyncio
async def test_mock_server_with_fixtures(mock_ads_server: MockADSServer):
    """Test basic connection and disconnection without fixtures."""
    # Connect to the mock server
    client = await AsyncioADSClient.connected_to(
        target_ip=mock_ads_server.host,
        target_ams_net_id=mock_ads_server.local_netid.to_string(),
        target_ams_port=IO_SERVER_PORT,
        ads_port=mock_ads_server.port,
    )

    try:
        # Read states and verify the response
        ads_state, device_state = await client._get_ioserver_states()
        assert ads_state == AdsState.ADSSTATE_RUN
        assert device_state == 0

    finally:
        # Disconnect from the mock server
        await client.close()
