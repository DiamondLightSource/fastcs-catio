#!/usr/bin/env python3
"""
Diagnostic script to enumerate EtherCAT devices on real hardware.

This script connects to a CATio server and enumerates all discovered
devices and slaves, allowing comparison with the expected configuration.

Usage:
    python tests/diagnose_hardware.py [--ip IP_ADDRESS]
    python tests/diagnose_hardware.py --ip 172.23.242.42 --output config.yaml
    python tests/diagnose_hardware.py --ip 172.23.242.42 --dump-symbols
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add tests to path for simulator imports
sys.path.insert(0, str(Path(__file__).parent))

from fastcs_catio.client import AsyncioADSClient, get_remote_address
from fastcs_catio.devices import AdsSymbol, IODevice, IOServer

try:
    from ads_sim.ethercat_chain import EtherCATChain

    SIMULATOR_AVAILABLE = True
except ImportError:
    EtherCATChain = None  # type: ignore[assignment,misc]
    SIMULATOR_AVAILABLE = False


# Add numpy type converters for YAML serialization
def numpy_int_representer(dumper, data):
    """Convert numpy integers to Python int."""
    return dumper.represent_int(int(data))


def numpy_float_representer(dumper, data):
    """Convert numpy floats to Python float."""
    return dumper.represent_float(float(data))


# Register numpy type handlers
for np_type in [
    np.int8,
    np.int16,
    np.int32,
    np.int64,
    np.uint8,
    np.uint16,
    np.uint32,
    np.uint64,
]:
    yaml.add_representer(np_type, numpy_int_representer)

for np_type in [np.float16, np.float32, np.float64]:
    yaml.add_representer(np_type, numpy_float_representer)


def generate_yaml_config(
    ioserver: IOServer,
    devices: dict[Any, IODevice],
) -> dict[str, Any]:
    """Generate a YAML-serializable configuration dict from discovered hardware.

    Args:
        ioserver: The IO Server information.
        devices: Dictionary of discovered EtherCAT devices.

    Returns:
        Dictionary suitable for YAML serialization matching
        server_config_CX7000_cs2.yaml format.
    """
    # Convert version string: replace hyphens with dots for proper version format
    version_str = str(ioserver.version).replace("-", ".")

    config: dict[str, Any] = {
        "server": {
            "name": str(ioserver.name),
            "version": version_str,
            "build": int(ioserver.build),
        },
        "devices": [],
    }

    for device_id, device in devices.items():
        # Build slave list with node/position tracking
        slaves_config = []
        current_node = -1

        for slave in device.slaves:
            node = int(slave.loc_in_chain.node)
            position = int(slave.loc_in_chain.position)

            slave_entry: dict[str, Any] = {
                "type": str(slave.type),
                "name": str(slave.name),
                "node": node,
                "position": position,
            }
            slaves_config.append(slave_entry)

            # Track node changes for comments
            if node != current_node:
                current_node = node

        # Ensure device.type is a native Python int
        device_type = int(
            device.type.value if hasattr(device.type, "value") else device.type
        )

        device_config: dict[str, Any] = {
            "id": int(device_id),
            "name": str(device.name),
            "type": device_type,
            "netid": str(device.netid),
            "identity": {
                "vendor_id": int(device.identity.vendor_id),
                "product_code": int(device.identity.product_code),
                "revision_number": int(device.identity.revision_number),
                "serial_number": int(device.identity.serial_number),
            },
            "slaves": slaves_config,
        }
        config["devices"].append(device_config)

    return config


def format_symbol_dump(
    symbols: dict[Any, dict[str, AdsSymbol]],
) -> str:
    """Format symbols for human-readable output.

    Args:
        symbols: Dictionary of device_id -> (dict of symbol_name -> AdsSymbol).

    Returns:
        Formatted string representation of all symbols.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("SYMBOL DUMP")
    lines.append("=" * 70)

    for device_id, device_symbols in symbols.items():
        lines.append(f"\nDevice {device_id} ({len(device_symbols)} symbols):")
        lines.append("-" * 60)

        for sym in device_symbols.values():
            lines.append(f"  {sym.name}")
            lines.append(
                f"    Group=0x{int(sym.group):08X}  Offset=0x{int(sym.offset):08X}  "
                f"Size={sym.size}  Type={sym.dtype}"
            )
            if sym.comment:
                lines.append(f"    Comment: {sym.comment}")

    return "\n".join(lines)


async def diagnose_hardware(
    ip: str,
    target_port: int = 27905,
    output_yaml: str | None = None,
    dump_symbols: bool = False,
    compare_file: str | None = None,
) -> None:
    """Connect to hardware and enumerate all devices and slaves.

    Args:
        ip: IP address of the CATio server.
        target_port: Target AMS port (default 27905).
        output_yaml: Optional path to write YAML configuration file.
        dump_symbols: Whether to dump all introspected symbols.
        compare_file: Optional simulator config YAML to compare against hardware.
    """
    logging.info(f"Connecting to {ip}:{target_port}...")

    # Get the remote AMS Net ID
    logging.info("Getting remote address...")
    target_ams_net_id = get_remote_address(ip)  # This is synchronous, takes string IP
    logging.info(f"Remote AMS Net ID: {target_ams_net_id}")

    # Connect using the class method
    client = await AsyncioADSClient.connected_to(
        target_ip=ip,
        target_ams_net_id=str(target_ams_net_id),
        target_ams_port=target_port,
    )

    try:
        # Introspect the IO server to discover devices
        await client.introspect_io_server()

        # Load symbols if requested or needed for comparison
        # (must be done after introspection)
        if dump_symbols or compare_file:
            logging.info("Loading symbols from device...")
            await client.get_all_symbols()

        # Print IO Server info
        print("\n" + "=" * 70)
        print("IO SERVER INFORMATION")
        print("=" * 70)
        print(f"  Name: {client.ioserver.name}")
        print(f"  Version: {client.ioserver.version}")
        print(f"  Build: {client.ioserver.build}")
        print(f"  Num Devices: {client.ioserver.num_devices}")

        # Print device information
        print("\n" + "=" * 70)
        print("ETHERCAT DEVICES")
        print("=" * 70)

        total_slaves = 0
        for device_id, device in client._ecdevices.items():
            print(f"\nDevice {device_id}: {device.name}")
            print(f"  Type: {device.type}")
            print(f"  NetID: {device.netid}")
            print(f"  Number of Slaves: {len(device.slaves)}")
            total_slaves += len(device.slaves)

            # Print slaves
            print(f"\n  Slaves ({len(device.slaves)}):")
            for i, slave in enumerate(device.slaves):
                print(
                    f"    [{i:3d}] Addr={slave.address:4d}  Type={slave.type:15s}  "
                    f"Name={slave.name}"
                )

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Total Devices: {client.ioserver.num_devices}")
        print(f"  Total Slaves: {total_slaves}")
        hardware_symbol_count = sum(len(s) for s in client._ecsymbols.values())
        print(f"  Total Symbols: {hardware_symbol_count}")

        # Print FastCS IO map entries
        print(f"\n  FastCS IO Map Entries: {len(client.fastcs_io_map)}")

        # Compare with simulator if requested
        if compare_file:
            if not SIMULATOR_AVAILABLE:
                logging.error("Simulator not available - cannot compare")
            else:
                compare_path = Path(compare_file)
                if not compare_path.exists():
                    logging.error(f"Compare file not found: {compare_path}")
                else:
                    print("\n" + "=" * 70)
                    print("SIMULATOR COMPARISON")
                    print("=" * 70)
                    print(f"  Config File: {compare_path}")

                    try:
                        # Load simulator config
                        assert EtherCATChain is not None
                        chain = EtherCATChain()
                        chain.load_config(compare_path)

                        # Compare counts
                        print(f"\n  Hardware Symbols: {hardware_symbol_count}")
                        print(f"  Simulator Total:  {chain.total_symbol_count}")

                        # Break down simulator symbols
                        device_symbols = 0
                        for dev_id, device in chain.devices.items():
                            for slave in device.slaves:
                                symbols = slave.get_symbols(
                                    dev_id, chain.runtime_symbols
                                )
                                device_symbols += len(symbols)

                        runtime_count = chain.total_symbol_count - device_symbols
                        print(f"    - Device Symbols:  {device_symbols}")
                        print(f"    - Runtime Symbols: {runtime_count}")

                        diff = hardware_symbol_count - chain.total_symbol_count
                        print(f"\n  Difference: {diff:+d}")

                        if diff == 0:
                            print("  ✓ Hardware matches simulator")
                        elif abs(diff) <= 5:
                            print(f"  ⚠ Minor difference ({abs(diff)} symbols)")
                        else:
                            print(f"  ✗ Significant difference ({abs(diff)} symbols)")

                        # Show symbol diff if there's a difference
                        if diff != 0:
                            # Collect hardware symbol names
                            hardware_names = set()
                            for device_symbols in client._ecsymbols.values():
                                for sym in device_symbols.values():
                                    hardware_names.add(sym.name)

                            # Collect simulator symbol names
                            # (all symbols it would generate)
                            simulator_names = set()
                            for _dev_id, device in chain.devices.items():
                                # Get all symbols including device-level runtime symbols
                                all_symbols = device.get_all_symbols(
                                    chain.runtime_symbols
                                )
                                for sym in all_symbols:
                                    simulator_names.add(sym["name"])

                            # Find differences
                            only_in_hardware = hardware_names - simulator_names
                            only_in_simulator = simulator_names - hardware_names

                            if only_in_hardware:
                                print(
                                    "\n  Symbols only in hardware "
                                    f"({len(only_in_hardware)}):"
                                )
                                for name in sorted(only_in_hardware)[:10]:
                                    print(f"    + {name}")
                                if len(only_in_hardware) > 10:
                                    print(
                                        f"    ... and {len(only_in_hardware) - 10} more"
                                    )

                            if only_in_simulator:
                                print(
                                    "\n  Symbols only in simulator "
                                    f"({len(only_in_simulator)}):"
                                )
                                for name in sorted(only_in_simulator)[:10]:
                                    print(f"    - {name}")
                                if len(only_in_simulator) > 10:
                                    more = len(only_in_simulator) - 10
                                    print(f"    ... and {more} more")
                    except Exception as e:
                        logging.error(f"Failed to compare with simulator: {e}")
                        import traceback

                        traceback.print_exc()

        # Dump symbols if requested
        if dump_symbols:
            print("\n" + format_symbol_dump(client._ecsymbols))

        # Write YAML configuration if requested
        if output_yaml:
            config = generate_yaml_config(client.ioserver, client._ecdevices)
            output_path = Path(output_yaml)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w") as f:
                # Add header comment
                f.write("# EtherCAT Chain Configuration for ADS Simulation Server\n")
                f.write("# ========================================================\n")
                f.write("#\n")
                f.write(f"# Auto-generated from hardware at {ip}\n")
                f.write("#\n\n")
                yaml.dump(
                    config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                    width=float("inf"),
                )

            print(f"\n  YAML configuration written to: {output_path}")

    except Exception as e:
        logging.error(f"Failed to connect or enumerate: {e}")
        raise
    finally:
        try:
            await client.close()
        except Exception as e:
            logging.warning(f"Error during disconnect: {e}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Diagnose EtherCAT hardware configuration"
    )
    parser.add_argument(
        "--ip",
        default="172.23.242.42",
        help="IP address of the CATio server (default: 172.23.242.42)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=27905,
        help="Target AMS port (default: 27905)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output YAML file path for hardware configuration",
    )
    parser.add_argument(
        "--dump-symbols",
        action="store_true",
        help="Dump all introspected symbols",
    )
    parser.add_argument(
        "--compare",
        type=str,
        default=None,
        help=(
            "Simulator config YAML to compare against hardware "
            "(e.g., tests/ads_sim/erver_config_CX7000_cs2.yaml)"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(
        diagnose_hardware(
            args.ip,
            args.port,
            output_yaml=args.output,
            dump_symbols=args.dump_symbols,
            compare_file=args.compare,
        )
    )


if __name__ == "__main__":
    main()
