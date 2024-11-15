import time

import pyads

# create some constants for connection

CLIENT_NETID = "172.23.245.123.1.1"
CLIENT_IP = "172.23.245.123"
TARGET_IP = "172.23.240.142"
TARGET_USERNAME = "Administrator"
TARGET_PASSWORD = "DIAMOND"
ROUTE_NAME = "route-to-my-plc"

# add a new route to the target plc
if __name__ == "__main__":
    pyads.add_route_to_plc(
        CLIENT_NETID,
        CLIENT_IP,
        TARGET_IP,
        TARGET_USERNAME,
        TARGET_PASSWORD,
        route_name=ROUTE_NAME,
    )

    # connect to plc and open connection

    # route is added automatically to client on Linux, on Windows use the TwinCAT router
    print(pyads.ads.adsGetNetIdForPLC(TARGET_IP))
    plc = pyads.Connection("5.59.238.150.1.1", 27909, TARGET_IP)
    plc.open()
    ch1 = []
    ch2 = []
    plc.add_device_notification(
        "Term 31 (EL3702).Ch1 Sample 0",
        pyads.structs.NotificationAttrib(
            2, pyads.constants.ADSTRANS_SERVERCYCLE, cycle_time=1
        ),
        lambda n, d: ch1.append((n, d)),
    )
    plc.add_device_notification(
        "Term 31 (EL3702).Ch2 Sample 0",
        pyads.structs.NotificationAttrib(
            2, pyads.constants.ADSTRANS_SERVERCYCLE, cycle_time=1
        ),
        lambda n, d: ch2.append((n, d)),
    )
    for i in range(10):
        time.sleep(1)
        print(len(ch1), len(ch2))
    plc.close()
