import asyncio

from ads_async.asyncio.client import AsyncioClientCircuit, AsyncioClientConnection


async def main():
    client = AsyncioClientConnection(("172.23.241.41", 48898), "172.23.245.123.1.1")
    async with client:
        circuit = AsyncioClientCircuit(client, "5.108.227.22.1.1", 27905)
        symbol = circuit.get_symbol_by_name("Term 31 (EL3702).Ch1 Sample 0")
        notification = await symbol.add_notification()
        notification.add_callback(print)


if __name__ == "__main__":
    asyncio.run(main())
