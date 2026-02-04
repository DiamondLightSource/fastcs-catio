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
import socket
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


def _is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use by trying to connect to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            # Try to connect - if successful, something is listening
            s.connect((host, port))
            return True
        except (TimeoutError, ConnectionRefusedError, OSError):
            # Connection refused or timeout means nothing is listening
            return False


@pytest.fixture(scope="session")
def expected_chain() -> EtherCATChain:
    """Load and return the expected EtherCAT chain configuration."""
    config_path = Path(__file__).parent / "ads_sim" / "server_config.yaml"
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

    # Check if simulator port is already in use
    simulator_port = 48898  # ADS_TCP_PORT
    if _is_port_in_use(simulator_port):
        pytest.fail(
            f"Port {simulator_port} is already in use. "
            "A simulator may already be running. "
            "Stop it before running tests or use --external-simulator flag."
        )

    # Launch the simulator subprocess with verbose logging
    cmd = [
        sys.executable,
        "-m",
        "tests.ads_sim",
        "--log-level",
        "INFO",
        "--disable-notifications",
        "--port",
        str(simulator_port),
    ]
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Wait for the READY log before yielding
    start_time = time.time()
    timeout = 10.0  # 10 seconds timeout
    ready = False

    assert process.stdout is not None, "stdout should be captured"
    while not ready and time.time() - start_time < timeout:
        line = process.stdout.readline()
        if line:
            print(line.rstrip())  # Echo output for debugging
            if "READY" in line:
                ready = True
                break
        if process.poll() is not None:
            pytest.fail(
                f"Simulator process exited prematurely with code {process.returncode}"
            )
        time.sleep(0.01)

    if not ready:
        if process.stdout:
            process.stdout.close()
        process.terminate()
        process.wait(timeout=2)
        pytest.fail(f"Simulator did not become ready within {timeout}s")

    # Close stdout now that we've read the READY line - we don't need it anymore
    if process.stdout:
        process.stdout.close()

    yield process

    # Cleanup: terminate the simulator and ensure pipes are closed
    process.terminate()
    try:
        process.wait(timeout=2)
    finally:
        # Ensure all pipes are closed
        if process.stdout and not process.stdout.closed:
            process.stdout.close()
        if process.stderr and not process.stderr.closed:
            process.stderr.close()

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
    # ip = "172.23.242.40"
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
    # TODO this requires https://github.com/DiamondLightSource/FastCS/pull/308
    # await controller.wait_for_startup(timeout=10.0)

    # make sure the notification system is enabled
    # meaning the scan routine has started
    timeout = 120.0  # 60 seconds timeout for startup
    start_time = asyncio.get_event_loop().time()
    while controller.notification_enabled is False:
        if asyncio.get_event_loop().time() - start_time > timeout:
            pytest.fail(
                f"Controller startup timed out after {timeout}s waiting for "
                "notification_enabled to become True"
            )
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
        - Retrieves basic IO server info
        - Validates the number of devices and symbols discovered
        """

        # Access the client to check IO server info
        client = fastcs_catio_controller.connection.client
        assert client is not None, "ADS client not initialized"

        # Validate IO server info was retrieved
        assert hasattr(client, "ioserver"), "IO server not discovered"

        # Validate EtherCAT device count
        # Note: num_devices from the IO server may include non-EtherCAT devices
        # We verify the number of discovered EtherCAT devices matches expected
        assert len(client._ecdevices) == expected_chain.device_count, (
            f"Expected {expected_chain.device_count} EtherCAT device(s), "
            f"got {len(client._ecdevices)}"
        )

        assert client.ioserver.name == expected_chain.server_info.name, (
            f"Unexpected IOC server name: {client.ioc_server.name}"
        )

        assert len(client.fastcs_io_map) == expected_chain.total_slave_count + 2, (
            f"Expected {expected_chain.total_slave_count + 2} IO map entries, "
            f"got {len(client.fastcs_io_map)}"
        )

        # Validate total symbol count across all devices
        # TODO this sees 426 symbols, got 502
        total_symbols = sum(len(symbols) for symbols in client._ecsymbols.values())
        assert total_symbols == expected_chain.total_symbol_count, (
            f"Expected {expected_chain.total_symbol_count} symbols, got {total_symbols}"
        )

    @pytest.mark.asyncio
    async def test_discovered_terminals_match_yaml_config(
        self, fastcs_catio_controller, expected_chain: EtherCATChain
    ):
        """Test that discovered EtherCAT terminals match the YAML configuration.

        Validates that:
        - The number of terminals matches the expected count from YAML
        - Each terminal type matches the expected configuration
        - Terminal addresses and positions are correct
        """
        client = fastcs_catio_controller.connection.client
        assert client is not None, "ADS client not initialized"

        # Get all discovered devices
        devices = client._ecdevices
        assert len(devices) > 0, "No EtherCAT devices discovered"

        # Validate total slave count across all devices
        total_discovered_slaves = sum(len(device.slaves) for device in devices.values())
        assert total_discovered_slaves == expected_chain.total_slave_count, (
            f"Expected {expected_chain.total_slave_count} slaves, "
            f"got {total_discovered_slaves}"
        )

        # Validate each device's slaves match the expected configuration
        for device_id, device in devices.items():
            expected_device = expected_chain.get_device(device_id)
            assert expected_device is not None, (
                f"Device {device_id} found in client but not in expected config"
            )

            assert len(device.slaves) == len(expected_device.slaves), (
                f"Device {device_id}: Expected {len(expected_device.slaves)} slaves, "
                f"got {len(device.slaves)}"
            )

            # Validate each slave terminal
            for discovered_slave, expected_slave in zip(
                device.slaves, expected_device.slaves, strict=True
            ):
                assert discovered_slave.type == expected_slave.type, (
                    f"Terminal type mismatch: expected {expected_slave.type}, "
                    f"got {discovered_slave.type}"
                )

                assert discovered_slave.address == expected_slave.address, (
                    f"Terminal {expected_slave.type} address mismatch: "
                    f"expected {expected_slave.address}, got {discovered_slave.address}"
                )
