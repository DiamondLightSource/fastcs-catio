import asyncio
import datetime
import inspect
import random

from catio.client import AsyncioADSClient

# Connection to CX2020 device
TARGET_IP = "172.23.240.142"
TARGET_NETID = "5.59.238.150.1.1"
TARGET_ADS_PORT = 27909
TARGET_ETHERCAT_NETID = "5.59.238.150.7.1"


async def do_something(client: AsyncioADSClient) -> None:
    print("...doing something...")

    try:
        device = next(iter(client._ecdevices.values()))
        for _ in range(5):
            await client.check_slave_states(
                device.id, random.choice(device.slaves).address
            )
            await client.check_slave_crc(
                device.id, random.choice(device.slaves).address
            )
            await asyncio.sleep(1)

    except ValueError as err:
        print(f"Value error raised in function '{inspect.stack()[0][3]}'")
        raise ValueError from err
    except AssertionError:
        print(f"Assertion error raised in function '{inspect.stack()[0][3]}'")
        raise

    await asyncio.sleep(2)
    print("...fake task completed...")


async def poll_continuously(client: AsyncioADSClient, duration: float) -> None:
    print("...continuous polling...")
    loop = asyncio.get_running_loop()
    end_time = loop.time() + duration
    sleep = 1.0
    await client.reset_frame_counters()
    while True:
        print(f"{datetime.datetime.now()} ...polling")
        if (loop.time() + sleep) >= end_time:
            break
        try:
            await client.poll_states()
            await client.poll_crc_counters()
            await client.poll_frame_counters()
        except ValueError as err:
            print(f"Value error raised in function '{inspect.stack()[0][3]}'")
            raise ValueError from err
        except AssertionError:
            print(f"Assertion error raised in function '{inspect.stack()[0][3]}'")
            raise
        await asyncio.sleep(sleep)
    print("...polling task completed...")


async def make_client() -> AsyncioADSClient:
    return await AsyncioADSClient.connected_to(
        target_ip=TARGET_IP,
        target_ams_net_id=TARGET_NETID,
        target_ams_port=TARGET_ADS_PORT,
    )


async def main():
    client = await make_client()

    try:
        await client.introspect_IO_server()
        await client.check_ads_states()

        async with asyncio.TaskGroup() as tg:
            task0 = tg.create_task(
                coro=do_something(client), name="Mock_task", context=None
            )
            task1 = tg.create_task(
                coro=poll_continuously(client, 5.0), name="Poll_task", context=None
            )
        print(f"All tasks have completed now: {task0.result()}, {task1.result()}")

    except ValueError as err:
        print(f"ADS client definition error: {err}")
    except TimeoutError as err:
        print(f"Connection error: {err}")
    except ConnectionError as err:
        print(f"Connection error: {err}")
    # except ExceptionGroup:    # requires python>3.11
    #     raise

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
