import re
import time
from collections import namedtuple
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self, SupportsInt

import numpy as np
import numpy.typing as npt
from fastcs.datatypes import Int, String, Waveform

from catio.catio_adapters import SubsystemParameter

from ._constants import (
    AdsDataType,
    DeviceType,
    SymbolFlag,
)
from ._types import AmsNetId
from .catio_adapters import CATioHandler
from .messages import DeviceFrames, IOIdentity, SlaveCRC, SlaveState

ChainLocation = namedtuple("ChainLocation", ["node", "position"])

STD_UPDATE_POLL_PERIOD: float = 2.0
FAST_UPDATE_POLL_PERIOD: float = 0.2
NOTIF_UPDATE_POLL_PERIOD: float = 1.0


# ===================================================================
# ===== EtherCAT OBJECTS
# ===================================================================


class IONodeType(str, Enum):
    """
    Provide a broad classification of the type of hardware found in the EtherCAT system.
    """

    Server = "server"
    Device = "device"
    Coupler = "coupler"
    Slave = "slave"


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

    parent_device: int
    """The id of the EtherCAT device the slave belongs to"""
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
    crcs: SlaveCRC
    """The error counters for the slave CRC on the distinct communication ports"""
    crc_error_sum: SupportsInt = 0
    """The error sum counter for the cyclic redundancy check of the slave"""
    loc_in_chain: ChainLocation = ChainLocation(0, 0)
    """The position of the slave within the EtherCAT device chain"""
    category: IONodeType = IONodeType.Slave
    """The component category the object belongs to in the EtherCAT system"""

    def get_type_name(self) -> str:
        """
        Translate the Beckhoff terminal type name into a more suitable PV name.
        """
        if self.category == "coupler":
            return f"RIO{self.loc_in_chain.node}"
        elif self.category == "slave":
            # This name will need updated by the actual Terminal Class (ai,ao,di,do...)
            return f"ADC{self.loc_in_chain.position}"
        else:
            raise NameError(f"I/O terminal category '{self.category}' isn't valid.")

    def get_params(self) -> list[SubsystemParameter]:
        """
        Get the parameters characteristic of an IOSlave object.

        :returns: the IOSlave object attributes as a list of sub-system parameters
        """
        params = []
        for key, value in vars(self).items():
            param_name = re.sub("[^0-9a-zA-Z]+", "", key)

            match key:
                case "parent_device":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O terminal master device",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "type":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O terminal type",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "name":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O terminal name",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "address":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O terminal EtherCAT address",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "identity":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            str(value),
                            "r",
                            "I/O terminal identity",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "states":
                    params.extend(
                        [
                            SubsystemParameter(
                                self.name,
                                param_name,
                                Waveform(array_dtype=np.uint8, shape=(2,)),
                                np.array(value, dtype=np.uint8),
                                "r",
                                "I/O terminal EtherCAT states",
                                handler=CATioHandler.PeriodicPoll,
                                update_period=STD_UPDATE_POLL_PERIOD,
                                callbacks=[
                                    "state_machine",
                                    "link_status",
                                ],
                            ),
                            SubsystemParameter(
                                self.name,
                                "state_machine",
                                Int(),
                                value.eCAT_state,
                                "r",
                                "I/O terminal state machine",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "link_status",
                                Int(),
                                value.link_status,
                                "r",
                                "I/O terminal communication state",
                                handler=CATioHandler.OnceAtStart,
                            ),
                        ]
                    )
                case "crcs":
                    params.extend(
                        [
                            SubsystemParameter(
                                self.name,
                                param_name,
                                Waveform(array_dtype=np.uint32, shape=(4,)),
                                np.array(value, dtype=np.uint32),
                                "r",
                                "I/O terminal crc error counters",
                                handler=CATioHandler.PeriodicPoll,
                                update_period=STD_UPDATE_POLL_PERIOD,
                                callbacks=[
                                    "crc_error_port_a",
                                    "crc_error_port_b",
                                    "crc_error_port_c",
                                    "crc_error_port_d",
                                ],
                            ),
                            SubsystemParameter(
                                self.name,
                                "crc_error_port_a",
                                Int(),
                                value.portA_crc,
                                "r",
                                "I/O terminal crc error counter on port A",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "crc_error_port_b",
                                Int(),
                                value.portB_crc,
                                "r",
                                "I/O terminal crc error counter on port B",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "crc_error_port_c",
                                Int(),
                                value.portC_crc,
                                "r",
                                "I/O terminal crc error counter on port C",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "crc_error_port_d",
                                Int(),
                                value.portD_crc,
                                "r",
                                "I/O terminal crc error counter on port D",
                                handler=CATioHandler.OnceAtStart,
                            ),
                        ]
                    )
                case "crc_error_sum":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O terminal crc error sum counter",
                            handler=CATioHandler.PeriodicPoll,
                            update_period=STD_UPDATE_POLL_PERIOD,
                        )
                    )
                case "loc_in_chain":
                    params.extend(
                        [
                            SubsystemParameter(
                                self.name,
                                "node",
                                Int(),
                                int(value.node),
                                "r",
                                "I/O terminal associated node",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "position",
                                Int(),
                                int(value.position),
                                "r",
                                "I/O terminal associated position",
                                handler=CATioHandler.OnceAtStart,
                            ),
                        ]
                    )
                case "category":
                    continue
                case _:
                    raise ValueError(
                        f"Missing definition for IOSlave parameter '{key}'"
                    )

        return params


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
    slaves_states: Sequence[SlaveState]
    """The states values for all of the slaves"""
    slaves_crc_counters: Sequence[np.uint32]
    """The error sum counter values of the cyclic redundancy check for all slaves"""
    slaves: Sequence[IOSlave]
    """The slave terminals configured on the EtherCAT device"""
    node_count: SupportsInt = 0
    """The number of node terminals (i.e. couplers) among the configured slaves"""
    category: IONodeType = IONodeType.Device
    """The component category the object belongs to in the EtherCAT system"""

    def __repr__(self):
        return (
            f"IODevice(id={self.id}, type={self.type}, name={self.name}, "
            + f"netid={self.netid}, slaveCount={self.slave_count}, "
            + f"slaveAdresses=[{self.slaves[0].address}...{self.slaves[-1].address}])"
        )

    def get_type_name(self) -> str:
        """
        Translate the Beckhoff device type code into a more suitable PV name.
        """
        if self.type == DeviceType.IODEVICETYPE_ETHERCAT:
            return f"ETH{self.id}"
        else:
            return f"EBUS{self.id}"

    def get_params(self) -> list[SubsystemParameter]:
        """
        Get the parameters characteristic of an IODevice object.

        :returns: the IODevice object attributes as a list of sub-system parameters
        """
        params = []
        for key, value in vars(self).items():
            param_name = re.sub("[^0-9a-zA-Z]+", "", key)

            match key:
                case "id":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O device identity number",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "type":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            int(value),
                            "r",
                            "I/O device type",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "name":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O device name",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "netid":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            str(value),
                            "r",
                            "I/O device ams netid",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "identity":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            str(value),
                            "r",
                            "I/O device identity",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "frame_counters":
                    params.extend(
                        [
                            SubsystemParameter(
                                self.name,
                                param_name,
                                Waveform(array_dtype=np.uint32, shape=(5,)),
                                np.array(value, dtype=np.uint32),
                                "r",
                                "I/O device frame counters",
                                handler=CATioHandler.PeriodicPoll,
                                update_period=STD_UPDATE_POLL_PERIOD,
                                # List the attribute dependencies to update,
                                # sub-attr must be marked as r|rw and start-only
                                callbacks=[
                                    "system_time",
                                    "sent_cyclic_frames",
                                    "lost_cyclic_frames",
                                    "sent_acyclic_frames",
                                    "lost_acyclic_frames",
                                ],
                            ),
                            SubsystemParameter(
                                self.name,
                                "system_time",
                                Int(),
                                value.time,
                                "r",
                                "I/O device, EtherCAT frame timestamp",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "sent_cyclic_frames",
                                Int(),
                                value.cyclic_sent,
                                "r",
                                "I/O device, sent cyclic frames counter",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "lost_cyclic_frames",
                                Int(),
                                value.cyclic_lost,
                                "r",
                                "I/O device, lost cyclic frames counter",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "sent_acyclic_frames",
                                Int(),
                                value.acyclic_sent,
                                "r",
                                "I/O device, sent acyclic frames counter",
                                handler=CATioHandler.OnceAtStart,
                            ),
                            SubsystemParameter(
                                self.name,
                                "lost_acyclic_frames",
                                Int(),
                                value.acyclic_lost,
                                "r",
                                "I/O device, lost acyclic frames counter",
                                handler=CATioHandler.OnceAtStart,
                            ),
                        ]
                    )
                case "slave_count":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O device registered slave count",
                            handler=CATioHandler.PeriodicPoll,
                            update_period=STD_UPDATE_POLL_PERIOD,
                        )
                    )
                case "slaves_states":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Waveform(
                                array_dtype=np.uint8, shape=(2 * int(self.slave_count),)
                            ),
                            np.array(value, dtype=np.uint8).flatten(),
                            "r",
                            "I/O device, states of slave terminals",
                            handler=CATioHandler.PeriodicPoll,
                            update_period=STD_UPDATE_POLL_PERIOD,
                        )
                    )
                case "slaves_crc_counters":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Waveform(
                                array_dtype=np.uint32, shape=(int(self.slave_count),)
                            ),
                            np.array(value, dtype=np.uint32),
                            "r",
                            "I/O device, slave crc error sum counters",
                            handler=CATioHandler.PeriodicPoll,
                            update_period=STD_UPDATE_POLL_PERIOD,
                        )
                    )
                case "node_count":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O device registered node count ",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "slaves" | "category":
                    continue
                case _:
                    raise ValueError(
                        f"Missing definition for IODevice parameter '{key}'"
                    )

        # Add potential notification timestamp parameter.
        params.append(
            SubsystemParameter(
                self.name,
                "timestamp",
                String(),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "r",
                "I/O device last notification timestamp",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            )
        )

        return params


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
    category: IONodeType = IONodeType.Server
    """The component category the object belongs to in the EtherCAT system"""

    def get_params(self) -> Sequence[SubsystemParameter]:
        """
        Get the parameters characteristic of an IOServer object.

        :returns: the IOServer object attributes as a list of sub-system parameters
        """
        params = []
        for key, value in vars(self).items():
            param_name = re.sub("[^0-9a-zA-Z]+", "", key)
            match key:
                case "name":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O server name",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "version":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            value,
                            "r",
                            "I/O server version number",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "build":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            String(),
                            str(value),
                            "r",
                            "I/O server build number",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "num_devices":
                    params.append(
                        SubsystemParameter(
                            self.name,
                            param_name,
                            Int(),
                            value,
                            "r",
                            "I/O server registered device count",
                            handler=CATioHandler.OnceAtStart,
                        )
                    )
                case "category":
                    continue
                case _:
                    raise ValueError(
                        f"Missing definition for IOServer parameter '{key}'"
                    )
        return params


class IOTreeNode:
    """
    Define an I/O component as a node in the tree structure representation \
        of the EtherCAT system.
    """

    def __init__(
        self, data: IOServer | IODevice | IOSlave, path: list[str] | None = None
    ):
        if path is None:
            self.path = [data.name]
        else:
            path.append(data.name)
            self.path = path

        self.data = data
        self.children: list[IOTreeNode] = []

    @property
    def child_count(self) -> int:
        return len(self.children)

    @property
    def tree_path(self) -> str:
        assert self.path is not None
        return " <-- ".join(self.path) if len(self.path) > 1 else self.path[0]

    def add_child(self, child: Self) -> None:
        self.children.append(child)

    def has_children(self) -> bool:
        return bool(self.children)

    def tree_height(self) -> int:
        if not self.children:
            return 1
        return 1 + max(child.tree_height() for child in self.children)

    def node_search(self, target: str) -> bool:
        """
        Depth-first search algorithm to check if the node is itself or has a child node\
             whose associated EtherCAT object correspond to a specific name.

        :params target: the name of the EtherCAT object to find in the tree

        :returns: true if this root node comprises the EtherCAT object name
        """
        if self.data.name == target:
            return True
        for child in self.children:
            if child.node_search(target):
                return True
        return False

    def print_tree(self, depth: int = 0) -> None:
        """
        Depth-first pre-order traversal function to print the EtherCAT object name \
            across the depth of the tree starting at this node.
        """
        tabs = "\t" * depth
        print(f"{tabs}node: {self.data.name}")
        for child in self.children:
            child.print_tree(depth + 1)

    def node_generator(self) -> Generator["IOTreeNode", Any, Any]:
        """
        Iterate recursively over all node elements in the tree starting at this node.
        """
        yield self
        for child in self.children:
            yield from child.node_generator()
