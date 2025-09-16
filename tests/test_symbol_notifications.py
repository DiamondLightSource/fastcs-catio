import asyncio
import random

from catio.client import AsyncioADSClient
from catio.utils import average, process_notifications

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
    notif_symbols = []

    try:
        await client.introspect_IO_server()
        symbols = await client.get_all_symbols()

        master_dev = next(iter(symbols))
        notif_symbols = symbols[master_dev]
        # notif_symbols = random.sample(symbols[master_dev], 800)
        print("...registering notifications...")
        await client.add_notifications(
            notif_symbols,  # max_delay_ms=1000, cycle_time_ms=1000
        )
        await asyncio.sleep(0.3)

        print("...start notifications...")
        client.start_notification_monitor(0.5)

        cnt = 50
        while cnt:
            notifs = await client.get_notifications(timeout=5)
            process_notifications(average, notifs)
            cnt -= 1
            print("COUNT: ", cnt)

        print("...stop notifications...")
        client.stop_notification_monitor()

    finally:
        print("...deleting notifications...")
        await client.delete_notifications(notif_symbols)
        await asyncio.sleep(1)

        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
