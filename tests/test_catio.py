import asyncio

from py_ads_client import INT, ADSSymbol

from catio.client import AsyncioADSClient

symbol1 = ADSSymbol(name="Term 31 (EL3702).Ch1 Sample 0", plc_t=INT)
symbol2 = ADSSymbol(name="Term 30 (EL3702).Ch1 Sample 0", plc_t=INT)
symbol3 = ADSSymbol(name="Term 31 (EL3702).Ch2 Sample 0", plc_t=INT)
symbol4 = ADSSymbol(name="Term 30 (EL3702).Ch2 Sample 0", plc_t=INT)


async def make_client():
    return await AsyncioADSClient.connected_to(
        target_ams_net_id="5.59.238.150.1.1",
        target_ip="172.23.240.142",
        target_ams_port=27909,
        local_ams_net_id="172.23.245.123.1.1",
    )


async def run():
    client1 = await make_client()
    await client1.add_device_notification(symbol1)
    await client1.add_device_notification(symbol2)
    await client1.add_device_notification(symbol3)
    await client1.add_device_notification(symbol4)
    await asyncio.sleep(0.1)
    client1.start()
    for _ in range(10):
        await asyncio.sleep(1)
        await client1.get_notifications()
    # client2 = await make_client()
    #
    # for _ in range(3):
    #     await asyncio.sleep(1)
    #     await client2.get_notifications(1000)


if __name__ == "__main__":
    asyncio.run(run())
