import numpy as np
from py_ads_client.ams.ads_add_device_notification import (
    ADSAddDeviceNotificationRequest,
)
from py_ads_client.ams.ads_add_device_notification import IndexGroup as OldIndexGroup
from py_ads_client.ams.ads_add_device_notification import (
    TransmissionMode as OldTransmissionMode,
)

from catio.messages import ADSAddDeviceNotificationRequest, IndexGroup, TransmissionMode


def test_ads_add_device_notification():
    old = ADSAddDeviceNotificationRequest(
        index_group=OldIndexGroup.GET_SYMHANDLE_BYNAME,
        index_offset=6,
        length=15,
        max_delay_ms=34,
        cycle_time_ms=2,
        transmission_mode=OldTransmissionMode.ADSTRANS_SERVERCYCLE,
    )
    new = ADSAddDeviceNotificationRequest(
        index_group=IndexGroup.GET_SYMHANDLE_BYNAME,
        index_offset=6,
        length=15,
        max_delay_ms=34,
        cycle_time_ms=2,
        transmission_mode=TransmissionMode.ADSTRANS_SERVERCYCLE,
    )
    assert old.index_offset == new.index_offset == 6
    assert old.length == new.length == 15
    assert old.max_delay_ms == new.max_delay_ms == 34
    assert old.cycle_time_ms == new.cycle_time_ms == 2
    assert len(old.to_bytes()) == len(new.to_bytes())
    assert old.to_bytes().hex(" ") == new.to_bytes().hex(" ")
    serialized = new.to_bytes()
    assert (
        ADSAddDeviceNotificationRequest.from_bytes(serialized).to_bytes() == serialized
    )
