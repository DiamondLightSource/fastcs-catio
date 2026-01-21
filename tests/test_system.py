"""
End-to-end system tests using the ADS simulator.

These tests launch the simulator subprocess and validate its behavior.
They serve as integration tests to ensure the full system works correctly.

Run the tests with:
```bash
pytest tests/test_system.py -v
```

To use an externally launched simulator instead:
```bash
pytest tests/test_system.py -v --external-simulator
```
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest
import pytest_asyncio
from fastcs.launch import FastCS

from ads_sim.ethercat_chain import EtherCATChain

# To enable debug logging
# instead of doing this use `pytest --log-cli-level=DEBUG`


@pytest.fixture(scope="session")
def expected_chain() -> EtherCATChain:
    """Load and return the expected EtherCAT chain configuration."""
    config_path = Path(__file__).parent / "ads_sim" / "ethercat_chain.yaml"
    return EtherCATChain(config_path)


@pytest.fixture(scope="session")
def simulator_process(request):
    """Launch the ADS simulator and return pexpect child process.

    This is a session-scoped fixture so the simulator is started once
    and shared across all tests in the session.

    If --external-simulator flag is passed, this fixture will not launch
    a simulator but instead assume one is already running externally.
    """
    # Check if using external simulator
    use_external = request.config.getoption("--external-simulator")

    if use_external:
        # No simulator to launch, just return None for both child and output
        # Tests should handle this gracefully
        print("\nUsing externally launched simulator")
        yield None, ""
        # No cleanup needed
        return

    # Launch the simulator subprocess with verbose logging
    cmd = [sys.executable, "-m", "tests.ads_sim", "--log-level", "DEBUG"]
    process = subprocess.Popen(cmd)

    # Give it a moment to start and print initial output
    time.sleep(1)

    yield process

    # Cleanup: terminate the simulator
    process.terminate()
    process.wait(timeout=2)

    # make sure the client has time to close
    time.sleep(1)


@pytest_asyncio.fixture(scope="function")
async def fastcs_catio_controller(simulator_process):
    """Create fastcs-catio controller and test basic connection.

    This fixture depends on simulator_process to ensure the simulator is running first.
    Note: We only test connection, not full initialization which hangs.
    """
    from fastcs_catio.catio_controller import CATioServerController
    from fastcs_catio.client import RemoteRoute

    # Give simulator a moment to be ready
    time.sleep(0.5)

    # Create controller instance
    # ip = "172.23.242.42"
    ip = "127.0.0.1"
    target_port = 27905
    poll_period = 1.0
    notification_period = 0.2

    route = RemoteRoute(ip)
    controller = CATioServerController(
        ip, route, target_port, poll_period, notification_period
    )
    launcher = FastCS(controller, transports=[])

    try:
        asyncio.create_task(launcher.serve())
    except Exception as e:
        pytest.fail(f"Failed to start fastcs client: {e}")

    # wait until the controller is ready
    await controller.wait_for_startup(timeout=50.0)
    # make sure the notification system is enabled
    # meaning the scan routine has started
    while controller.notification_enabled is False:
        await asyncio.sleep(0.5)
    yield controller

    # Cleanup: close the connection
    try:
        await controller.disconnect()
    except TimeoutError:
        print("WARNING: Connection close timed out")
    except Exception as e:
        print(f"WARNING: Error during cleanup: {e}")


class TestFastcsCatioConnection:
    """Test fastcs-catio IOC connection to simulator."""

    @pytest.mark.asyncio
    async def test_ioc_connects_and_discovers_symbols(
        self, fastcs_catio_controller, expected_chain: EtherCATChain
    ):
        """Test that fastcs-catio IOC connects to the simulator.

        Validates that the IOC:
        - Successfully connects to the simulator
        - Retrieves basic IO server information
        Note: Full device/slave introspection is skipped due to hanging
        in _get_slave_identities().
        """

        # Access the client to check IO server info
        client = fastcs_catio_controller.connection.client
        assert client is not None, "ADS client not initialized"

        # Validate IO server info was retrieved
        assert hasattr(client, "ioserver"), "IO server not discovered"
        assert client.ioserver.num_devices == 1, (
            f"Expected 1 device, got {client.ioserver.num_devices}"
        )

        assert client.ioserver.name == expected_chain.server_info.name, (
            f"Unexpected IOC server name: {client.ioc_server.name}"
        )

        assert len(client.fastcs_io_map) == expected_chain.total_slave_count + 2, (
            f"Expected {expected_chain.total_slave_count + 2} IO map entries, "
            f"got {len(client.fastcs_io_map)}"
        )

        # TODO Where do I get the symbol count from in the client?
        # assert client.ioc_server.num_symbols == expected_chain.total_symbol_count, (
        #     f"Expected {expected_chain.total_symbol_count} symbols, "
        #     f"got {client.ioc_server.num_symbols}"
        # )
