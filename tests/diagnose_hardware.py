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

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastcs_catio.client import AsyncioADSClient, get_remote_address
from fastcs_catio.devices import AdsSymbol, IODevice, IOServer


def generate_yaml_config(
    ioserver: IOServer,
    devices: dict[Any, IODevice],
) -> dict[str, Any]:
    """Generate a YAML-serializable configuration dict from discovered hardware.

    Args:
        ioserver: The IO Server information.
        devices: Dictionary of discovered EtherCAT devices.

    Returns:
        Dictionary suitable for YAML serialization matching server_config.yaml format.
    """
    config: dict[str, Any] = {
        "server": {
            "name": ioserver.name,
            "version": ioserver.version,
            "build": int(ioserver.build),
        },
        "devices": [],
    }

    for device_id, device in devices.items():
        # Build slave list with node/position tracking
        slaves_config = []
        current_node = -1

        for slave in device.slaves:
            node = slave.loc_in_chain.node
            position = slave.loc_in_chain.position

            slave_entry: dict[str, Any] = {
                "type": slave.type,
                "name": slave.name,
                "node": node,
                "position": position,
            }
            slaves_config.append(slave_entry)

            # Track node changes for comments
            if node != current_node:
                current_node = node

        device_type = (
            device.type.value if hasattr(device.type, "value") else int(device.type)
        )
        device_config: dict[str, Any] = {
            "id": int(device_id),
            "name": device.name,
            "type": device_type,
            "netid": str(device.netid),
            "identity": {
                "vendor_id": int(device.identity.vendor_id),
                "product_code": hex(int(device.identity.product_code)),
                "revision_number": int(device.identity.revision_number),
                "serial_number": int(device.identity.serial_number),
            },
            "slaves": slaves_config,
        }
        config["devices"].append(device_config)

    return config


def format_symbol_dump(
    symbols: dict[Any, list[AdsSymbol]],
) -> str:
    """Format symbols for human-readable output.

    Args:
        symbols: Dictionary of device_id -> list of AdsSymbol.

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

        for sym in device_symbols:
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
) -> None:
    """Connect to hardware and enumerate all devices and slaves.

    Args:
        ip: IP address of the CATio server.
        target_port: Target AMS port (default 27905).
        output_yaml: Optional path to write YAML configuration file.
        dump_symbols: Whether to dump all introspected symbols.
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

        # Load symbols if requested (must be done after introspection)
        if dump_symbols:
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
        print(f"  Total Symbols: {sum(len(s) for s in client._ecsymbols.values())}")

        # Print FastCS IO map entries
        print(f"\n  FastCS IO Map Entries: {len(client.fastcs_io_map)}")

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
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

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
        )
    )


if __name__ == "__main__":
    main()
