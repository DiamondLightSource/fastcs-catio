from collections import namedtuple
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import numpy.typing as npt

from ._constants import DeviceType, SlaveLinkState, SlaveStateMachine
from ._types import UDINT, UINT, USINT
from .messages import Message

ChainLocation = namedtuple("ChainLocation", ["node", "position"])


# ===================================================================
# ===== ETHERCAT PROPERTIES
# ===================================================================


class IOIdentity(Message):
    """
    Define the identity parameters of an EtherCAT device or slave.
    """

    vendor_id: UDINT
    """The vendor id number"""
    product_code: UDINT
    """The product code"""
    revision_number: UDINT
    """The revision number"""
    serial_number: UDINT
    """The serial number"""


class DeviceFrames(Message):
    """
    Define the frame counters of an EtherCAT device.
    """

    time: UDINT
    """System time"""
    cyclic_sent: UDINT
    """Number of cyclic frames sent by the master device"""
    cyclic_lost: UDINT
    """Number of lost cyclic frames"""
    acyclic_sent: UDINT
    """Number of acyclic frames sent by the master device"""
    acyclic_lost: UDINT
    """Number of lost acyclic frames"""


class SlaveCRC(Message):
    """
    Define the cyclic redundancy check error counters of an EtherCAT slave.
    Ports B, C and D may not be used, thus potentially absent from an ADS response.
    """

    portA_crc: UDINT
    """CRC error counter of communication port A"""
    portB_crc: UDINT
    """CRC error counter of communication port B"""
    portC_crc: UDINT
    """CRC error counter of communication port C"""
    portD_crc: UDINT
    """CRC error counter of communication port D"""


class SlaveState(Message):
    """
    Define the EtherCAT state and link status of an EtherCAT slave.
    """

    eCAT_state: USINT
    """The EtherCAT state"""
    link_status: USINT
    """The link status for communication"""


# ===================================================================
# ===== EtherCAT OBJECTS
# ===================================================================


@dataclass
class IOSlave:
    """
    Define an EtherCAT slave object configured on an EtherCAT device.
    """

    type: str
    """The CANopen type object of the slave"""
    name: str
    """The CANopen name object of the slave"""
    address: UINT
    """The EtherCAT address of the slave"""
    identity: IOIdentity
    """The CANopen identity object of the slave"""
    loc_in_chain: ChainLocation = ChainLocation(0, 0)
    """The position of the slave within the EtherCAT device chain"""
    states: SlaveState = SlaveState(
        eCAT_state=SlaveStateMachine.SLAVE_STATE_OP,
        link_status=SlaveLinkState.SLAVE_LINK_STATE_OK,
    )
    """The EtherCAT states of the slave"""


@dataclass
class IODevice:
    """
    Define an EtherCAT device object registered on the I/O server.
    """

    id: int
    """The id number associated with the EtherCAT device"""
    type: DeviceType
    """The type of the EtherCAT device"""
    name: str
    """The name of the EtherCAT device"""
    netid: str
    """The ams netid address of the EtherCAT device"""
    identity: IOIdentity
    """The CANopen identity object of the EtherCAT device"""
    slave_count: int
    """The number of slave terminals configured on the EtherCAT device"""
    slave_crc_counters: npt.NDArray[np.uint32]
    """The error counter values of the cyclic redundancy check for all of the slaves"""
    slaves: Sequence[IOSlave]
    """The slave terminals configured on the EtherCAT device"""
    frame_counters: DeviceFrames = DeviceFrames(
        time=0, cyclic_sent=0, cyclic_lost=0, acyclic_sent=0, acyclic_lost=0
    )
    """The EtherCAT cycle frame counters for the EtherCAT device"""

    def __repr__(self):
        return (
            f"IODevice(id={self.id}, type={self.type}, name={self.name}, "
            + f"netid={self.netid}, slaveCount={self.slave_count}, "
            + f"slaveAdresses=[{self.slaves[0].address}...{self.slaves[-1].address}])"
        )


@dataclass
class IOServer:
    """Define an I/O server object."""

    name: str
    """The name of the server"""
    version: str
    """The version number of the server"""
    build: UINT
    """The build number of the server"""
    num_devices: int
    """The number of EtherCAT devices registered with the server"""
