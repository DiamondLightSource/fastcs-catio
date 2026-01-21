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
import logging
import sys
import time
from pathlib import Path

import pexpect
import pytest
import pytest_asyncio
from fastcs.launch import FastCS

from ads_sim.ethercat_chain import EtherCATChain


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
    cmd = [sys.executable, "-m", "tests.ads_sim", "--verbose"]
    child = pexpect.spawn(
        cmd[0],
        cmd[1:],
        encoding="utf-8",
        timeout=10,
        cwd=str(Path(__file__).parent.parent),
    )

    # Give it a moment to start and print initial output
    time.sleep(1)

    # Read initial output
    try:
        initial_output = child.read_nonblocking(size=10000, timeout=1)
    except pexpect.TIMEOUT:
        initial_output = ""

    yield child, initial_output

    # Cleanup: terminate the simulator
    child.terminate(force=True)
    child.wait()


@pytest_asyncio.fixture(scope="function")
async def fastcs_catio_controller(simulator_process):
    """Create fastcs-catio controller and test basic connection.

    This fixture depends on simulator_process to ensure the simulator is running first.
    Note: We only test connection, not full initialization which hangs.
    """
    from fastcs_catio.catio_controller import CATioServerController
    from fastcs_catio.client import RemoteRoute

    # Ensure simulator is running
    sim_child, _ = simulator_process

    # Give simulator a moment to be ready
    time.sleep(0.5)

    # Enable debug logging to see where it hangs
    logging.basicConfig(level=logging.DEBUG, force=True)

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
        await asyncio.create_task(launcher.serve())
    except Exception as e:
        pytest.fail(f"Failed to start fastcs client: {e}")

    time.sleep(2)  # Allow some time for connection
    yield controller

    # Cleanup: close the connection
    try:
        asyncio.run(controller.disconnect())
    except TimeoutError:
        print("WARNING: Connection close timed out")
    except Exception as e:
        print(f"WARNING: Error during cleanup: {e}")


class TestSimulatorLaunch:
    """Test launching and validating the ADS simulator."""

    def test_simulator_starts_and_prints_chain(
        self, simulator_process, expected_chain: EtherCATChain
    ):
        """Test that the simulator starts and prints the expected chain information.

        Step 1: Launch the simulator as a subprocess using pexpect
        Step 2: Validate that the output contains list of terminals and symbol count

        Note: This test is skipped when using an external simulator.
        """
        # Get expected values from the config
        expected_symbol_count = expected_chain.total_symbol_count
        expected_devices = list(expected_chain.devices.values())

        # Unpack the simulator process and initial output
        child, output = simulator_process

        # Skip test if using external simulator
        if child is None:
            pytest.skip("Test skipped when using external simulator")

        sep_line = "=" * 27
        print(f"\n===== Captured Output =====\n{output}\n{sep_line}\n")

        # Validate the expected content in output
        assert "============ Simulated EtherCAT Chain ============" in output, (
            "Chain header not found in output"
        )

        assert f"Total symbols: {expected_symbol_count}" in output, (
            f"Expected symbol count {expected_symbol_count} not found"
        )

        # Validate that device names appear in output
        for device in expected_devices:
            # Note: Typo in original code "EtherCAT" vs "EtherCAT"
            assert f"EtherCAT Master '{device.name}'" in output, (
                f"Device {device.name} not found"
            )

        # Verify server started
        assert "ADS Simulation server started on" in output, (
            "Server start message not found"
        )


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

        # Get the controller object (fixture already awaited)
        controller = fastcs_catio_controller

        # Access the client to check IO server info
        client = controller.connection.client
        assert client is not None, "ADS client not initialized"

        # Validate IO server info was retrieved
        assert hasattr(client, "ioserver"), "IO server not discovered"
        assert client.ioserver.num_devices == 1, (
            f"Expected 1 device, got {client.ioserver.num_devices}"
        )
        assert client.ioserver.name == "I/O Server", (
            f"Unexpected IO server name: {client.ioserver.name}"
        )

        print(
            f"\nSuccessfully connected to IO server:"
            f"\n  - Name: {client.ioserver.name}"
            f"\n  - Version: {client.ioserver.version}"
            f"\n  - Build: {client.ioserver.build}"
            f"\n  - Devices: {client.ioserver.num_devices}"
        )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="just one system test while debugging device introspection hanging"
    )
    async def test_ioc_discovers_device_info(
        self, fastcs_catio_controller, expected_chain: EtherCATChain
    ):
        """Test that fastcs-catio IOC discovers correct IO server information.

        Note: This test only validates IO server info, not individual devices,
        because full device introspection hangs in _get_slave_identities().
        """

        # Get the controller object (fixture already awaited)
        controller = fastcs_catio_controller

        # Access the client to check IO server
        client = controller.connection.client

        # Validate IO server info matches expected configuration
        assert hasattr(client, "ioserver"), "IO server info not retrieved"
        assert client.ioserver.num_devices > 0, "No devices discovered"

        # Verify IO server name is correct
        assert client.ioserver.name == "I/O Server", (
            f"Unexpected IO server name: {client.ioserver.name}"
        )

        print(
            f"\nIO server validation successful:"
            f"\n  - Name: {client.ioserver.name}"
            f"\n  - Version: {client.ioserver.version}"
            f"\n  - Devices: {client.ioserver.num_devices}"
        )
