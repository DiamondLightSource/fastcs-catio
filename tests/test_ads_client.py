from __future__ import annotations

import asyncio
import logging
import time
from asyncio.streams import StreamReader, StreamWriter
from collections.abc import AsyncGenerator, Iterable
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from py_ads_client import INT, ADSClient, ADSSymbol

client = ADSClient(local_ams_net_id="172.23.245.123.1.1")
client.open(
    target_ams_net_id="5.59.238.150.1.1",
    target_ip="172.23.240.142",
    target_ams_port=27909,
)

symbol1 = ADSSymbol(name="Term 31 (EL3702).Ch1 Sample 0", plc_t=INT)
# symbol2 = ADSSymbol(name="Term 30 (EL3702).Ch1 Sample 0", plc_t=INT)
# arr_value = client.read_symbol(arr_symbol)
client.add_device_notification(symbol1, 1, 1)
# client.add_device_notification(symbol2)
for i in range(10):
    time.sleep(1)
    x = 0
    while not client.device_notification_queue.empty():
        client.device_notification_queue.get()
        x += 1
    print(x)
client.close()
