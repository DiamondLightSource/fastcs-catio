from collections import namedtuple
from dataclasses import dataclass
from typing import Sequence, SupportsInt

import numpy as np
import numpy.typing as npt

from ._constants import (
    AdsDataType,
    DeviceType,
    SymbolFlag,
)
from ._types import AmsNetId
from .messages import DeviceFrames, IOIdentity, SlaveState

ChainLocation = namedtuple("ChainLocation", ["node", "position"])


# ===================================================================
# ===== EtherCAT OBJECTS
# ===================================================================


@dataclass
class AdsSymbol:
    """
    Define an ADS symbol.
    """

    parent_id: SupportsInt
    """Id of the device which the symbol belongs to"""
    name: str
    """Name of the symbol"""
    dtype: npt.DTypeLike
    """Data type of the symbol"""
    size: int
    """Number of elements"""
    group: SupportsInt
    """Index group used by the ADS protocol to address the symbol"""
    offset: SupportsInt
    """Index offset used by the ADS protocol to address the symbol"""
    comment: str
    """Optional comment associated to the symbol"""
    handle: SupportsInt | None = None
    """Unique handle value mapping the symbol to an ADS notification"""

    @property
    def datatype(self) -> npt.DTypeLike:
        """
        Get the numpy data type of the data associated to the symbol value.
        It takes into account the type and size of the symbol, i.e. it may return:
        - a generic type: e.g. uint16 of type <class 'numpy.dtypes.UInt16DType'>
        - an array type: e.g. ('<i2', (100,)) of type <class 'numpy.dtypes.VoidDType'>

        :returns: the extended data type of the ADS symbol value.
        """
        if self.size > 1:
            return np.dtype((self.dtype, self.size))
        return np.dtype(self.dtype)

    @property
    def nbytes(
        self,
    ) -> int:
        """
        Get the total number of bytes of the data associated to the symbol value.

        :returns: the total size in bytes of the ADS symbol value
        """
        return np.dtype(self.dtype).itemsize * self.size


@dataclass
class AdsSymbolNode:
    """
    Define a distinct symbol node as exposed by the uploaded symbol table.
    """

    parent_id: SupportsInt
    """Id of the device which the symbol node belongs to"""
    name: str
    """Name of the symbol node (i.e. root name of the device symbol)"""
    type_name: str
    """Type of the symbol node as characterised by the generic terminal type
    (i.e. not the actual data type of the symbol)."""
    ads_type: AdsDataType
    """Actual data type of the symbol"""
    size: SupportsInt
    """Size of the symbol in bytes (0 corresponds to 'bit')"""
    index_group: SupportsInt
    """Index group used by the ADS protocol to address the symbol node"""
    index_offset: SupportsInt
    """Index offset used by the ADS protocol to address the symbol node"""
    flag: SymbolFlag
    """ADS flag characterising the symbol node"""
    comment: str
    """Optional comment associated to the symbol node"""


@dataclass
class IOSlave:
    """
    Define an EtherCAT slave object configured on an EtherCAT device.
    """

    type: str
    """The CANopen type object of the slave"""
    name: str
    """The CANopen name object of the slave"""
    address: SupportsInt
    """The EtherCAT address of the slave"""
    identity: IOIdentity
    """The CANopen identity object of the slave"""
    states: SlaveState
    """The EtherCAT states of the slave"""
    loc_in_chain: ChainLocation = ChainLocation(0, 0)
    """The position of the slave within the EtherCAT device chain"""


@dataclass
class IODevice:
    """
    Define an EtherCAT device object registered on the I/O server.
    """

    id: SupportsInt
    """The id number associated with the EtherCAT device"""
    type: DeviceType
    """The type of the EtherCAT device"""
    name: str
    """The name of the EtherCAT device"""
    netid: AmsNetId
    """The ams netid address of the EtherCAT device"""
    identity: IOIdentity
    """The CANopen identity object of the EtherCAT device"""
    frame_counters: DeviceFrames
    """The EtherCAT cycle frame counters for the EtherCAT device"""
    slave_count: SupportsInt
    """The number of slave terminals configured on the EtherCAT device"""
    slave_crc_counters: npt.NDArray[np.uint32]
    """The error counter values of the cyclic redundancy check for all of the slaves"""
    slaves: Sequence[IOSlave]
    """The slave terminals configured on the EtherCAT device"""

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
    build: SupportsInt
    """The build number of the server"""
    num_devices: SupportsInt
    """The number of EtherCAT devices registered with the server"""
