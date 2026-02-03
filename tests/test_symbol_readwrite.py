import asyncio
import random

from fastcs_catio.client import AsyncioADSClient

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
        symbols = await client.get_all_symbols()
        master_dev = next(iter(symbols))

        # Read symbol values
        for _ in range(10):
            name, value = await client.read_ads_symbol(
                random.choice(list(symbols[master_dev].values()))
            )
            print(f"{name}: {value}")

        read_symbols = random.sample(list(symbols[master_dev].values()), 10)
        for symbol in read_symbols:
            name, value = await client.read_ads_symbol(symbol)
            print(f"Read {name} = {value}")

        print(f"SUM Read -- {await client.sumread_ads_symbols(read_symbols)}")

        # Write value to symbols
        output_symbols = [
            symbol
            for symbol in list(symbols[master_dev].values())
            if all(substr in symbol.name for substr in ["EL2024", "Channel"])
        ]
        if output_symbols:
            write_symbols = random.sample(
                list(symbols[master_dev].values()), min(10, len(output_symbols))
            )

            for symbol in write_symbols:
                print(
                    f"{symbol.name}, "
                    + f"value set to 1: {await client.write_ads_symbol(symbol, 1)}"
                )
            await asyncio.sleep(1)
            for symbol in write_symbols:
                print(
                    f"{symbol.name}, "
                    + f"value set to 0: {await client.write_ads_symbol(symbol, 0)}"
                )

            # # SumWrite will return 'ErrorCode.ADSERR_DEVICE_SRVNOTSUPP' with CX2020.
            # # (single write command works and couldn't find any error in bytes stream)
            # n = len(write_symbols)
            # print(
            #     "SUM Write -- "
            #     + f"{await client.sumwrite_ads_symbols(
            #         list(zip(write_symbols, [1] * n)))}"
            # )
            # await asyncio.sleep(1)
            # print(
            #     "SUM Write -- "
            #     + f"{await client.sumwrite_ads_symbols(
            #         list(zip(write_symbols, [0] * n)))}"
            # )

            # # ReadWrite calls will also return 'ErrorCode.ADSERR_DEVICE_SRVNOTSUPP'.
            # # ReadWrite value to symbols
            # readwrite_symbols = random.sample(
            #     symbols[master_dev], min(5, len(output_symbols))
            # )
            # for symbol in readwrite_symbols:
            #     print(
            #         f"{symbol.name}, value set to 1: "
            #         + f"initially was {await client.readwrite_ads_symbol(symbol, 1)}"
            #     )
            # await asyncio.sleep(1)
            # for symbol in readwrite_symbols:
            #     print(
            #         f"{symbol.name}, value set to 0: "
            #         + f"initially was {await client.readwrite_ads_symbol(symbol, 0)}"
            #     )

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
