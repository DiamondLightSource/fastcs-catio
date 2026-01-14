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
        await client.check_ads_states()

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
