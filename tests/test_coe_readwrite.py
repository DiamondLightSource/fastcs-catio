import asyncio

from catio.client import AsyncioADSClient

# Connection to CX2020 device
TARGET_IP = "172.23.240.142"
TARGET_NETID = "5.59.238.150.1.1"
TARGET_ADS_PORT = 27909


async def make_client() -> AsyncioADSClient:
    return await AsyncioADSClient.connected_to(
        target_ip=TARGET_IP,
        target_ams_net_id=TARGET_NETID,
        target_ams_port=TARGET_ADS_PORT,
    )


async def main():
    client = await make_client()

    try:
        await client.introspect_io_server()

        # Get a slave terminal of a given type
        slave_type = "EL3104"
        terminal = client.find_slave_in_master_device(slave_type)

        # Toggle one of its CoE parameter, e.g. the 'filter enable'
        if terminal:
            await client.set_io_coe_parameter(terminal, "8000", "0006", True)
            await asyncio.sleep(2)
            await client.set_io_coe_parameter(terminal, "8000", "0006", False)
        else:
            print(
                f"ERROR: no slave terminal of type {slave_type} is available \
                    on the EtherCAT Master device."
            )

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
