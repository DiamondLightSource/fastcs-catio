#!/usr/bin/env python3
"""
Diagnostic script to enumerate EtherCAT devices on real hardware.

This script connects to a CATio server and enumerates all discovered
devices and slaves, allowing comparison with the expected configuration.

Usage:
    python tests/diagnose_hardware.py [--ip IP_ADDRESS]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastcs_catio.client import AsyncioADSClient, get_remote_address


async def diagnose_hardware(ip: str, target_port: int = 27905) -> None:
    """Connect to hardware and enumerate all devices and slaves.

    Args:
        ip: IP address of the CATio server.
        target_port: Target AMS port (default 27905).
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

    except Exception as e:
        logging.error(f"Failed to connect or enumerate: {e}")
        raise
    finally:
        try:
            await client.disconnect()
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

    asyncio.run(diagnose_hardware(args.ip, args.port))


if __name__ == "__main__":
    main()
