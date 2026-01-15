#!/bin/bash

# example of how to test the ADS I/O server simulator

# before running start the server in another terminal:
# python -m tests.ads_sim

THIS=$(dirname "$0")

cd $THIS && python -c "
import asyncio
import sys
import logging
logging.basicConfig(level=logging.INFO)
sys.path.insert(0, 'src')
from fastcs_catio.client import AsyncioADSClient

async def test():
    try:
        client = await asyncio.wait_for(
            AsyncioADSClient.connected_to(
                target_ip='127.0.0.1',
                target_ams_net_id='10.0.0.1.3.1',
                target_ams_port=300
            ),
            timeout=10.0
        )
        print('Connected to server!')

        # Introspect the I/O server
        print('Introspecting I/O server...')
        await asyncio.wait_for(client.introspect_io_server(), timeout=30.0)

        print(f'Found {len(client._ecdevices)} device(s)')

        await client.close()
        print('Test passed!')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
" 2>&1
