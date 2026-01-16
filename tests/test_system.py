"""
End-to-end system tests using the ADS simulator.

These tests launch the simulator subprocess and validate its behavior.
They serve as integration tests to ensure the full system works correctly.

Run the tests with:
```bash
pytest tests/test_system.py -v
```
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pexpect
import pytest

from ads_sim.ethercat_chain import EtherCATChain


@pytest.fixture(scope="session")
def expected_chain() -> EtherCATChain:
    """Load and return the expected EtherCAT chain configuration."""
    config_path = Path(__file__).parent / "ads_sim" / "ethercat_chain.yaml"
    return EtherCATChain(config_path)


@pytest.fixture(scope="session")
def simulator_process():
    """Launch the ADS simulator and return pexpect child process.

    This is a session-scoped fixture so the simulator is started once
    and shared across all tests in the session.
    """
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


class TestSimulatorLaunch:
    """Test launching and validating the ADS simulator."""

    def test_simulator_starts_and_prints_chain(
        self, simulator_process, expected_chain: EtherCATChain
    ):
        """Test that the simulator starts and prints the expected chain information.

        Step 1: Launch the simulator as a subprocess using pexpect
        Step 2: Validate that the output contains list of terminals and symbol count
        """
        # Get expected values from the config
        expected_symbol_count = expected_chain.total_symbol_count
        expected_devices = list(expected_chain.devices.values())

        # Unpack the simulator process and initial output
        child, output = simulator_process

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
            # Note: Typo in original code "EherCAT" vs "EtherCAT"
            assert f"EherCAT Master '{device.name}'" in output, (
                f"Device {device.name} not found"
            )

        # Verify server started
        assert "ADS Simulation server started on" in output, (
            "Server start message not found"
        )

    def test_simulator_output_contains_terminal_types(
        self, simulator_process, expected_chain: EtherCATChain
    ):
        """Test that the simulator output includes terminal type information."""
        # Get sample terminal types from first device
        expected_devices = list(expected_chain.devices.values())
        if not expected_devices or not expected_devices[0].slaves:
            pytest.skip("No devices or slaves in configuration")

        sample_slaves = expected_devices[0].slaves[:3]  # Check first 3 slaves

        # Unpack the simulator process and initial output
        child, output = simulator_process

        # Check that terminal types appear in the output
        for slave in sample_slaves:
            # Terminal types should appear in format like:
            # "|----- 1::1 -> EK1100 Term 1 (EK1100)"
            # or "|----- 1::2 -> EL2004 Term 2 (EL2004)"
            assert slave.type in output, f"Terminal type {slave.type} not found"
