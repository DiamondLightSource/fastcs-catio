import inspect
import logging
import re
import string
import time
from abc import abstractmethod
from collections.abc import Generator, Iterator
from itertools import chain, count
from typing import Any

import numpy as np
import numpy.typing as npt
from fastcs.attributes import Attribute, AttrMode, AttrR
from fastcs.controller import Controller, SubController
from fastcs.datatypes import Int, String, Waveform
from fastcs.wrappers import scan
from numpy.lib import recfunctions as rfn

from catio._constants import DeviceType
from catio.devices import ELM_OVERSAMPLING_FACTOR, OVERSAMPLING_FACTOR
from catio.utils import (
    average,
    filetime_to_dt,
    get_notification_changes,
    process_notifications,
)

from .catio_adapters import (
    CATioHandler,
    Subsystem,
)
from .catio_connection import (
    CATioConnection,
    CATioConnectionSettings,
    CATioFastCSRequest,
)
from .devices import IODevice, IONodeType, IOServer, IOSlave, IOTreeNode

NOTIFICATION_UPDATE_PERIOD: float = 0.2
STANDARD_POLL_UPDATE_PERIOD: float = 1.0


class CATioSubController(SubController):
    """
    Will be replace by CATioController in FASTCS2
    A sub-controller for an ADS-based EtherCAT system.
    Such sub-controller will be used to define distinct components in the \
        EtherCAT system, e.g. devices and slave terminals.
    """

    _subctrl_obj: Iterator[int] = count(start=1, step=1)
    _subsystem: Subsystem

    def __init__(
        self,
        connection: CATioConnection,
        *,
        name: str = "UNKNOWN",
        eCAT_name: str = "",
        description: str | None = None,
        io_function: str = "",
        comments: str = "",
    ):
        super().__init__(description)
        self.identifier: int = next(CATioSubController._subctrl_obj)
        self.name: str = name
        self.connection: CATioConnection = connection
        self.eCAT_name: str = eCAT_name
        self.attr_group_name: str = trimmed(eCAT_name)
        self.ads_name_map: dict[
            str, str
        ] = {}  # key is FastCS attribute name, value is complex ads symbol name
        self.io_function: str = io_function
        self.comments: str = comments

    async def initialise(self) -> None:
        logging.debug(
            f"Initialising sub-controller {self.name} with FastCS attributes."
        )

    def attribute_dict_generator(
        self,
    ) -> Generator[dict[str, Attribute], Any, Any]:
        """
        Recursively extract all attribute references from the subcontroller \
            and its subcontrollers.

        :yields: a dictionary with the subcontroller full attribute name as key \
            and the attribute object as value.
        """
        attr_dict = {}
        for key, attr in self.attributes.items():
            if isinstance(self, CATioSubController):
                ads_name = self.ads_name_map.get(key, None)
                key = ads_name if ads_name is not None else key

            attr_dict[".".join([f"_{self.eCAT_name.replace(' ', '')}", key])] = attr
        yield attr_dict
        if self.get_sub_controllers():
            for subctrl in self.get_sub_controllers().values():
                assert isinstance(subctrl, CATioSubController)
                yield from subctrl.attribute_dict_generator()

    def make_class_attributes(self) -> None:
        """Set all subcontroller parameters as class attributes."""
        for attr_name in self.attributes.keys():
            setattr(self, "_" + attr_name, self.attributes[attr_name])

    @property
    def subsystem(self) -> str:
        return self._subsystem

    @abstractmethod
    def get_attributes(self) -> dict[str, Attribute]:
        """Base method to create subcontroller-specific attributes."""
        ...


    async def print_names(self) -> None:
        for name, subctrl in self.get_sub_controllers().items():
            print(f"SUBCONTROLLER: {name}")
            assert isinstance(subctrl, CATioSubController)
            await subctrl.print_names()


class CATioController(Controller):
    """
    A root controller for an ADS-based EtherCAT system using a Beckhoff TwinCAT server.
    The TwinCAT server is restricted to a single client connection from the same host.
    """

    _tcp_connection: CATioConnection
    _ctrl_obj: Iterator[int] = count(start=0, step=1)

    def __init__(self, description: str):
        super().__init__(description)
        self.identifier: int = next(CATioController._ctrl_obj)
        self.name: str = ""

    async def _establish_tcp_connection(self, settings: CATioConnectionSettings):
        """
        Create a catio connection with the Beckhoff TwinCAT server.
        """
        self._tcp_connection = await CATioConnection.connect(settings)

    @property
    def connection(self) -> CATioConnection:
        return self._tcp_connection

    async def get_subcontrollers_from_node(
        self, node: IOTreeNode
    ) -> None | CATioSubController | Controller:
        """
        Recursively register all subcontrollers available from a system node \
            with their parent controller.
        To do so, the EtherCAT system is traversed from top to bottom, left to right.
        Once registered, each subcontroller is then initialised (attributes are created).

        :param node: the tree node to extract available subcontrollers from.

        :returns: the (sub)controller object created for the current node.
        """
        subcontrollers: list[CATioSubController] = []
        if node.has_children():
            for child in node.children:
                ctrl = await self.get_subcontrollers_from_node(child)
                assert ctrl is not None
                assert isinstance(ctrl, CATioSubController)
                subcontrollers.append(ctrl)

            logging.debug(
                f"{len(subcontrollers)} subcontrollers were found for {node.data.name}."
            )

        return await self._get_subcontroller_object(node, subcontrollers)

    async def initialise(self) -> None:
        """
        Automatically called by fastCS backend '__init__()' method.
        Initialise the CATio controller.
        """
        logging.debug(f"Initialising CATio controller {self.name}...")
        await super().initialise()

    async def attribute_initialise(self) -> None:
        """
        Automatically called by fastCS backend '__init__()' method.
        Initialise the FastCS attributes and their associated handlers for the \
            CATio controller and all subcontrollers in the EtherCAT system.
        """
        logging.info(
            f"Initialising attributes for CATio controller {self.name} and "
            + "all its subcontrollers..."
        )
        await super().attribute_initialise()

    async def connect(self) -> None:
        """
        Automatically called by fastCS backend 'serve()' method.
        Method run asynchronously at the same time as the call to start the IOC.
        Call the connect() method for any Master Device subcontroller.
        """
        logging.debug(
            "CATio connection already established during controller initialisation."
        )
        await super().connect()
        logging.debug(
            "Checking for any Master device subcontroller to setup symbol notification."
        )
        for subctrl in self.get_sub_controllers().values():
            if isinstance(subctrl, EtherCATMasterController):
                await subctrl.connect()
        logging.info("CATio Controller instance is now up and running.")

    async def _get_subcontroller_object(
        self,
        node: IOTreeNode,
        subcontrollers: list[CATioSubController],
    ) -> None | CATioSubController | Controller:
        """
        Create the associated CATio controller/subcontroller object for the given node \
            in the EtherCAT tree.

        :param node: the tree node to extract the (sub)controller object from.
        :param subcontrollers: a list of subcontrollers associated with the node.

        :returns: the subcontroller object created for the current node.
        """
        match node.data.category:
            case IONodeType.Server:
                assert isinstance(node.data, IOServer)
                logging.debug(
                    "Implementing I/O server controller as the root CATioController."
                )
                ctrl = self

            case IONodeType.Device:
                assert isinstance(node.data, IODevice)
                key = (
                    "ETHERCAT"
                    if node.data.type == DeviceType.IODEVICETYPE_ETHERCAT
                    else node.data.name
                )
                logging.debug(
                    f"Implementing I/O device '{key}' as a CATioSubController."
                )
                ctrl = SUPPORTED_CONTROLLERS[key](
                    connection=self.connection,
                    name=node.data.get_type_name(),
                    eCAT_name=node.data.name,
                    description=f"Controller for EtherCAT device #{node.data.id}",
                )
                logging.debug(
                    f"Initialising device controller {ctrl.name} with FastCS attributes."
                )
                await ctrl.initialise()

            case IONodeType.Coupler | IONodeType.Slave:
                assert isinstance(node.data, IOSlave)
                logging.debug(
                    f"Implementing I/O terminal '{node.data.name}' as a CATioSubController."
                )
                ctrl = SUPPORTED_CONTROLLERS[node.data.type](
                    connection=self.connection,
                    name=node.data.get_type_name(),
                    eCAT_name=node.data.name,
                    description=f"Controller for {node.data.category.value} terminal "
                    + f"'{node.data.name}'",
                )
                logging.debug(
                    f"Initialising terminal controller {ctrl.name} with FastCS attributes."
                )
                await ctrl.initialise()

        if subcontrollers:
            for subctrl in subcontrollers:
                logging.debug(
                    f"Registering sub-controller {subctrl.name} with controller "
                    + f"{ctrl.name}."
                )
                ctrl.register_sub_controller(subctrl.name, subctrl)

        return ctrl


class CATioDeviceController(CATioSubController):
    """A sub-controller for an EtherCAT I/O device."""

    _subsystem = "device"

    def __init__(self, connection, name, eCAT_name="", description=None):
        super().__init__(
            connection, name=name, eCAT_name=eCAT_name, description=description
        )
        self.notification_ready: bool = False

    async def initialise(self) -> None:
        """Initialise the device controller by creating its attributes."""
        await super().initialise()
        await self.get_device_attributes()
        self.attributes.update(self.get_attributes())
        self.make_class_attributes()

    async def connect(self) -> None:
        """
        Setup the symbol notifications for the device and mark it as ready.
        """
        await self.setup_symbol_notifications()
        self.notification_ready = True

    async def get_device_attributes(self) -> None:
        """Get and create all generic device attributes."""
        _group = "IODevice"

        # Update the CATio client fast_cs_io_map
        io: IODevice = await self.connection.send_query(
            CATioFastCSRequest("IO_FROM_MAP", self.identifier, _group, self.eCAT_name)
        )

        # super().get_attributes()

        self.attributes["Id"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="id"),
            initial_value=int(io.id),
            description="I/O device identity number",
        )

        self.attributes["Type"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="type"),
            initial_value=int(io.type),
            description="I/O device type",
        )

        self.attributes["Name"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="name"),
            initial_value=io.name,
            description="I/O device name",
        )

        self.attributes["Netid"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="netid"),
            initial_value=str(io.netid),
            description="I/O device ams netid",
        )

        self.attributes["Identity"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="identity"),
            initial_value=str(io.identity),
            description="I/O device identity",
        )

        self.attributes["SystemTime"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.frame_counters.time),
            description="I/O device, EtherCAT frame timestamp",
        )

        self.attributes["SentCyclicFrames"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.frame_counters.cyclic_sent),
            description="I/O device, sent cyclic frames counter",
        )

        self.attributes["LostCyclicFrames"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.frame_counters.cyclic_lost),
            description="I/O device, lost cyclic frames counter",
        )

        self.attributes["SentAcyclicFrames"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.frame_counters.acyclic_sent),
            description="I/O device, sent acyclic frames counter",
        )

        self.attributes["LostAcyclicFrames"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.frame_counters.acyclic_lost),
            description="I/O device, lost acyclic frames counter",
        )

        self.attributes["SlaveCount"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.PeriodicPoll.value.create(
                attribute_name="slave_count", update_period=STANDARD_POLL_UPDATE_PERIOD
            ),
            initial_value=int(io.slave_count),
            description="I/O device registered slave count",
        )

        self.attributes["SlavesStates"] = AttrR(
            datatype=Waveform(array_dtype=np.uint8, shape=(2 * int(io.slave_count),)),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.PeriodicPoll.value.create(
                attribute_name="slaves_states",
                update_period=STANDARD_POLL_UPDATE_PERIOD,
            ),
            initial_value=np.array(io.slaves_states, dtype=np.uint8).flatten(),
            description="I/O device, states of slave terminals",
        )

        self.attributes["SlavesCrcCounters"] = AttrR(
            datatype=Waveform(array_dtype=np.uint32, shape=(int(io.slave_count),)),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.PeriodicPoll.value.create(
                attribute_name="slaves_crc_counters",
                update_period=STANDARD_POLL_UPDATE_PERIOD,
            ),
            initial_value=np.array(io.slaves_crc_counters, dtype=np.uint32),
            description="I/O device, slave crc error sum counters",
        )

        self.attributes["NodeCount"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="node_count"),
            initial_value=int(io.node_count),
            description="I/O device registered node count",
        )

        self.attributes["timestamp"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            description="I/O device last notification timestamp",
        )

        logging.debug(
            f"{len(self.attributes)} fastCS attributes have been registered "
            + f"with the device controller {self.eCAT_name}."
        )

    def get_device_eCAT_id(self) -> int:
        """
        Extract the id value from the EtherCAT device name (e.g. from ETH5 or EBUS12).
        """
        matches = re.search(r"(\d+)$", self.name)
        if matches:
            return int(matches.group(0))
        raise NameError(
            f"CATioDeviceController id couldn't be extracted from its name {self.name}."
        )

    async def setup_symbol_notifications(self) -> None:
        """
        Setup subscriptions to all ads symbol variables available to the controller.
        Although running in the background, notifications of change won't be active \
            until monitoring is enabled.
        """
        logging.info(
            f"EtherCAT Device {self.name}: subscribing to symbol notifications."
        )
        await self.connection.add_notifications(self.get_device_eCAT_id())

    @scan(STANDARD_POLL_UPDATE_PERIOD)
    async def frame_counters(self) -> None:
        """Periodically poll the EtherCAT frame counters from the device."""
        attr_names = [
            "SystemTime",
            "SentCyclicFrames",
            "LostCyclicFrames",
            "SentAcyclicFrames",
            "LostAcyclicFrames",
        ]
        attr_dict = {k: self.attributes[k] for k in attr_names if k in self.attributes}
        results: list[np.uint32] = []
        for attr in list(attr_dict.values()):
            assert isinstance(attr, AttrR)
            results.append(attr.get())
        old_value = np.array(results)

        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        function_name = frame.f_code.co_name.replace("_", "")

        response = await self.connection.send_query(
            CATioFastCSRequest(
                f"{self._subsystem.upper()}_{function_name.upper()}_ATTR",
                attr_group=self.identifier,
            )
        )

        if response is not None:
            assert isinstance(response, np.ndarray), (
                f"{function_name.upper()}: Response was {type(response)}, {response}"
            )
            assert response.dtype == np.uint32
            assert response.shape == (5,)

            if not np.array_equal(response, old_value):
                for name, value in zip(attr_names, np.nditer(response), strict=True):
                    attr = self.attributes[name]
                    assert isinstance(attr, AttrR)
                    await attr.set(value)

                logging.debug(
                    f"Frame counters attributes for device {self.name} have been updated."
                )


class CATioTerminalController(CATioSubController):
    """A sub-controller for an EtherCAT I/O terminal."""

    _subsystem = "terminal"

    async def initialise(self) -> None:
        """Initialise the terminal controller by creating its attributes."""
        await super().initialise()
        await self.get_terminal_attributes()
        self.attributes.update(self.get_attributes())
        self.make_class_attributes()

    async def get_terminal_attributes(self) -> None:
        """Get and create all generic terminal attributes."""
        _group = "IOTerminal"

        # Update the CATio client fast_cs_io_map
        io: IOSlave = await self.connection.send_query(
            CATioFastCSRequest("IO_FROM_MAP", self.identifier, _group, self.eCAT_name)
        )

        # super().get_attributes()

        self.attributes["Function"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="io_function"),
            initial_value=self.io_function,
            description="I/O terminal function",
        )

        self.attributes["ParentDevId"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(
                attribute_name="parent_device"
            ),
            initial_value=str(io.parent_device),
            description="I/O terminal master device id",
        )

        self.attributes["Type"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="type"),
            initial_value=io.type,
            description="I/O terminal type",
        )

        self.attributes["Name"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="name"),
            initial_value=io.name,
            description="I/O terminal name",
        )

        self.attributes["Address"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="address"),
            initial_value=int(io.address),
            description="I/O terminal EtherCAT address",
        )

        self.attributes["Identity"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="identity"),
            initial_value=str(io.identity),
            description="I/O terminal identity",
        )

        self.attributes["StateMachine"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.states.eCAT_state),
            description="I/O terminal state machine",
        )

        self.attributes["LinkStatus"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.states.link_status),
            description="I/O terminal communication state",
        )

        self.attributes["CrcErrorPortA"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.crcs.portA_crc),
            description="I/O terminal crc error counter on port A",
        )

        self.attributes["CrcErrorPortB"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.crcs.portB_crc),
            description="I/O terminal crc error counter on port B",
        )

        self.attributes["CrcErrorPortC"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.crcs.portC_crc),
            description="I/O terminal crc error counter on port C",
        )

        self.attributes["CrcErrorPortD"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=int(io.crcs.portD_crc),
            description="I/O terminal crc error counter on port D",
        )

        self.attributes["CrcErrorSum"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.PeriodicPoll.value.create(
                attribute_name="crc_error_sum",
                update_period=STANDARD_POLL_UPDATE_PERIOD,
            ),
            initial_value=int(io.crcs.portD_crc),
            description="I/O terminal crc error sum counter",
        )

        self.attributes["Node"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="node"),
            initial_value=int(io.loc_in_chain.node),
            description="I/O terminal associated node",
        )

        self.attributes["Position"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="position"),
            initial_value=int(io.loc_in_chain.position),
            description="I/O terminal associated position",
        )

        logging.debug(
            f"{len(self.attributes)} fastCS attributes have been registered "
            + f"with the terminal controller {self.eCAT_name}."
        )

    @scan(STANDARD_POLL_UPDATE_PERIOD)
    async def states(self) -> None:
        """Periodically poll the EtherCAT terminal states from the io."""
        attr_names = [
            "StateMachine",
            "LinkStatus",
        ]
        attr_dict = {k: self.attributes[k] for k in attr_names if k in self.attributes}
        results: list[np.uint8] = []
        for attr in list(attr_dict.values()):
            assert isinstance(attr, AttrR)
            results.append(attr.get())
        old_value = np.array(results)

        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        function_name = frame.f_code.co_name.replace("_", "")

        response = await self.connection.send_query(
            CATioFastCSRequest(
                f"{self._subsystem.upper()}_{function_name.upper()}_ATTR",
                attr_group=self.identifier,
            )
        )

        if response is not None:
            assert isinstance(response, np.ndarray)
            assert response.dtype == np.uint8
            assert response.shape == (2,)

            if not np.array_equal(response, old_value):
                for name, value in zip(attr_names, np.nditer(response), strict=True):
                    attr = self.attributes[name]
                    assert isinstance(attr, AttrR)
                    await attr.set(value)

                logging.debug(
                    f"States attributes for terminal {self.name} have been updated."
                )

    @scan(STANDARD_POLL_UPDATE_PERIOD)
    async def crc_error_counters(self) -> None:
        """
        Periodically poll the EtherCAT terminal CRC error counters from the io.
        """
        attr_names = [
            "CrcErrorPortA",
            "CrcErrorPortB",
            "CrcErrorPortC",
            "CrcErrorPortD",
        ]
        attr_dict = {k: self.attributes[k] for k in attr_names if k in self.attributes}
        results: list[np.uint32] = []
        for attr in list(attr_dict.values()):
            assert isinstance(attr, AttrR)
            results.append(attr.get())
        old_value = np.array(results)

        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        function_name = frame.f_code.co_name.replace("_", "")

        response = await self.connection.send_query(
            CATioFastCSRequest(
                f"{self._subsystem.upper()}_{function_name.upper()}_ATTR",
                attr_group=self.identifier,
            )
        )

        if response is not None:
            assert isinstance(response, np.ndarray)
            assert response.dtype == np.uint32
            assert response.shape == (4,)

            if not np.array_equal(response, old_value):
                for name, value in zip(attr_names, np.nditer(response), strict=True):
                    attr = self.attributes[name]
                    assert isinstance(attr, AttrR)
                    await attr.set(value)

                logging.debug(
                    f"CRC counters attributes for terminal {self.name} have been updated."
                )


def print_registered_ctrl(ctrl: CATioController | CATioSubController) -> None:
    """Print the registered subcontrollers for a given controller."""
    subcontrollers = ctrl.get_sub_controllers()
    if subcontrollers:
        print(f"Subcontrollers registered with {ctrl.name}: {subcontrollers.keys()}")
        for subctrl in subcontrollers.values():
            assert isinstance(subctrl, CATioSubController)
            print_registered_ctrl(subctrl)


def trimmed(name: str) -> str:
    """Shorten and remove spaces from the original EtherCAT name."""
    matches = re.search(r"^(\w+\s+)\d+", name)
    return matches.group(0).replace(" ", "") if matches else name


class EtherCATMasterController(CATioDeviceController):
    """A sub-controller for an EtherCAT Master I/O device."""

    io_function: str = "EtherCAT Master Device"
    num_ads_streams: int = 1

    # Depending on number of notification streams, we'll have more attr!!!
    # e.g. 3 streams -> Frm0State, Frm1State, Frm2State
    # For now, just implement Frm0*

    # Also from TwinCAT, it should be:
    # attr_dict["Inputs.Frm0State"] = AttrR(...)
    # but '.' is not allowed in fastCS attribute name -> error
    # name string should match pattern '^([A-Z][a-z0-9]*)*$'

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific master device attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["InputsSlaveCount"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Number of slaves reached in last cycle",
        )
        attr_dict["InputsDevState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="EtherCAT device input cycle frame status",
        )
        attr_dict["OutputsDevCtrl"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="EtherCAT device output control value",
        )
        for i in range(1, self.num_ads_streams + 1):
            attr_dict[f"InFrm{i}State"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description="Cyclic Ethernet frame status",
            )
            attr_dict[f"InFrm{i}WcState"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description="Inputs accumulated working counter",
            )
            attr_dict[f"InFrm{i}InpToggle"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description="EtherCAT cyclic frame update indicator",
            )
            attr_dict[f"OutFrm{i}Ctrl"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description="EtherCAT output frame control value",
            )
            attr_dict[f"OutFrm{i}WcCtrl"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description="Outputs accumulated working counter",
            )

            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"InFrm{i}State"] = f"Inputs.Frm{i}State"
            self.ads_name_map[f"InFrm{i}WcState"] = f"Inputs.Frm{i}WcState"
            self.ads_name_map[f"InFrm{i}InpToggle"] = f"Inputs.Frm{i}InputToggle"
            self.ads_name_map[f"OutFrm{i}Ctrl"] = f"Outputs.Frm{i}Ctrl"
            self.ads_name_map[f"OutFrm{i}WcCtrl"] = f"Outputs.Frm{i}WcCtrl"

        return attr_dict


class EK1100Controller(CATioTerminalController):
    """A sub-controller for an EK1100 EtherCAT Coupler terminal."""

    io_function: str = "EtherCAT coupler at the head of a segment"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific coupler terminal attributes."""
        attr_dict: dict[str, Attribute] = {}
        return attr_dict


class EK1101Controller(CATioTerminalController):
    """A sub-controller for an EK1101 EtherCAT Coupler terminal."""

    io_function: str = "EtherCAT coupler with three ID switches for variable topologies"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific coupler terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["ID"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=1,
            description="Unique ID for the group of components",
        )

        return attr_dict


class EK1110Controller(CATioTerminalController):
    """A sub-controller for an EK1110 EtherCAT Extension terminal."""

    io_function: str = "EtherCAT extension coupler for line topology"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific coupler terminal attributes."""
        attr_dict: dict[str, Attribute] = {}
        return attr_dict


class EL1004Controller(CATioTerminalController):
    """A sub-controller for an EL1004 EtherCAT digital input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 3ms filter"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL1004 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated digital value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital input value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL1014Controller(CATioTerminalController):
    """A sub-controller for an EL1014 EtherCAT wcounter input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 10us filter"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL1014 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated digital value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital input value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL1124Controller(CATioTerminalController):
    """A sub-controller for an EL1124 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital input, 5V DC, 0.05us filter"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL1124 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated digital value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital input value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL1084Controller(CATioTerminalController):
    """A sub-controller for an EL1084 EtherCAT digital input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 3ms filter, GND switching"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL1084 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated digital value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital input value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL1502Controller(CATioTerminalController):
    """A sub-controller for an EL1502 EtherCAT digital input terminal."""

    io_function: str = "2-channel digital input, counter, 24V DC, 100kHz"
    num_channels = 2

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL1502 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated digital value",
        )
        attr_dict["CNTInputStatus"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Input channel counter status",
        )
        attr_dict["CNTInputValue"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Input channel counter value",
        )
        attr_dict["CNTOutputStatus"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Output channel counter status",
        )
        attr_dict["CNTOutputValue"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Output channel counter set value",
        )
        # Map the FastCS attribute names to the symbol names used by ADS
        self.ads_name_map["CNTInputStatus"] = "CNTInputs.Countervalue"
        self.ads_name_map["CNTInputValue"] = "CNTOutputs.Setcountervalue"
        self.ads_name_map["CNTOutputStatus"] = "CNTInputs.Countervalue"
        self.ads_name_map["CNTOutputValue"] = "CNTOutputs.Setcountervalue"

        return attr_dict


class EL2024Controller(CATioTerminalController):
    """A sub-controller for an EL2024 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 24V DC, 2A"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL2024 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DOCh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital output value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL2024_0010Controller(CATioTerminalController):
    """A sub-controller for an EL2024-0010 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 12V DC, 2A"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL2024-0010 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DOCh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital output value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL2124Controller(CATioTerminalController):
    """A sub-controller for an EL2124 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 5V DC, 20mA"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL2124 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"DOCh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} digital output value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

        return attr_dict


class EL3104Controller(CATioTerminalController):
    """A sub-controller for an EL3104 EtherCAT analog input terminal."""

    io_function: str = "4-channel analog input, +/-10V, 16-bit, differential"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL3104 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated analog value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"AICh{i}Status"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} voltage status",
            )
            attr_dict[f"AICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} analog input value",
            )
            # Map the FastCS attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AIStandardChannel{i}.Status"
            self.ads_name_map[f"AICh{i}Value"] = f"AIStandardChannel{i}.Value"

        return attr_dict


class EL3602Controller(CATioTerminalController):
    """A sub-controller for an EL3602 EtherCAT analog input terminal."""

    io_function: str = "2-channel analog input, up to +/-10V, 24-bit, high-precision"
    num_channels: int = 2

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL3602 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Availability of an updated analog value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"AICh{i}Status"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} voltage status",
            )
            attr_dict[f"AICh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} analog input value",
            )
            # Map the FastCS attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AIInputsChannel{i}"
            self.ads_name_map[f"AICh{i}Value"] = f"AIInputsChannel{i}.Value"

        return attr_dict


class EL3702Controller(CATioTerminalController):
    """A sub-controller for an EL3702 EtherCAT analog input terminal."""

    io_function: str = "2-channel analog input, +/-10V, 16-bit, oversampling"

    # TO DO: Can we get those values from ads read or catio config file ???
    operating_channels: int = 2
    oversampling_factor: int = OVERSAMPLING_FACTOR

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL3702 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        for i in range(1, self.operating_channels + 1):
            attr_dict[f"AICh{i}CycleCount"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Record transfer counter for channel#{i}",
            )
            if self.oversampling_factor == 1:
                attr_dict[f"AICh{i}ValueOvsmpl"] = AttrR(
                    datatype=Int(),
                    access_mode=AttrMode.READ,
                    group=self.attr_group_name,
                    handler=None,
                    initial_value=0,
                    description=f"Analog sample value(s) for channel#{i}",
                )
            else:
                attr_dict[f"AICh{i}ValueOvsmpl"] = AttrR(
                    datatype=Waveform(
                        array_dtype=np.int16, shape=(self.oversampling_factor,)
                    ),
                    access_mode=AttrMode.READ,
                    group=self.attr_group_name,
                    handler=None,
                    initial_value=np.zeros((self.oversampling_factor,), dtype=np.int16),
                    description=f"Analog sample value(s) for channel#{i}",
                )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}CycleCount"] = f"Ch{i}CycleCount"
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = f"Ch{i}Sample0"

        return attr_dict


class EL4134Controller(CATioTerminalController):
    """A sub-controller for an EL4134 EtherCAT analog output terminal."""

    io_function: str = "4-channel analog output, +/-10V, 16-bit"
    num_channels: int = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL4134 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        for i in range(1, self.num_channels + 1):
            attr_dict[f"AOCh{i}Value"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} analog output value",
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AOCh{i}Value"] = f"AOOutputChannel{i}.Analogoutput"

        return attr_dict


class EL9410Controller(CATioTerminalController):
    """A sub-controller for an EL9410 EtherCAT power supply terminal."""

    io_function: str = "2A power supply for E-bus"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL9410 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Counter for valid telegram received",
        )
        attr_dict["StatusUp"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Power contacts voltage diagnostic status",
        )
        attr_dict["StatusUs"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="E-bus supply voltage diagnostic status",
        )

        return attr_dict


class EL9505Controller(CATioTerminalController):
    """A sub-controller for an EL9505 EtherCAT power supply terminal."""

    io_function: str = "5V DC output power supply"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL9505 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Counter for valid telegram received",
        )
        attr_dict["StatusUo"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Output voltage status",
        )

        return attr_dict


class EL9512Controller(CATioTerminalController):
    """A sub-controller for an EL9512 EtherCAT power supply terminal."""

    io_function: str = "12V DC output power supply"

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific EL9512 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )
        attr_dict["InputToggle"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Counter for valid telegram received",
        )
        attr_dict["StatusUo"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Output voltage status",
        )

        return attr_dict


class ELM3704_0000Controller(CATioTerminalController):
    """A sub-controller for an ELM3704-0000 EtherCAT analog input terminal."""

    io_function: str = "4-channel analog input, multi-function, 24-bit, 10 ksps"
    oversampling_factor: int = ELM_OVERSAMPLING_FACTOR  # complex setup, see TwinCAT
    num_channels = 4

    def get_attributes(self) -> dict[str, Attribute]:
        """Get and create all specific ELM3704-0000 terminal attributes."""
        attr_dict: dict[str, Attribute] = {}

        attr_dict["WcState"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=self.attr_group_name,
            handler=None,
            initial_value=0,
            description="Slave working counter state value",
        )

        for i in range(1, self.num_channels + 1):
            attr_dict[f"AICh{i}Status"] = AttrR(
                datatype=Int(),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=0,
                description=f"Channel#{i} Process Analog Input status",
            )
            attr_dict[f"AICh{i}LatchTime"] = AttrR(
                datatype=Waveform(array_dtype=np.uint32, shape=(2,)),
                access_mode=AttrMode.READ,
                group=self.attr_group_name,
                handler=None,
                initial_value=np.zeros((2,), dtype=np.uint32),
                description=f"Latch time for next channel#{i} samples",
            )
            if self.oversampling_factor == 1:
                attr_dict[f"AICh{i}ValueOvsmpl"] = AttrR(
                    datatype=Int(),
                    access_mode=AttrMode.READ,
                    group=self.attr_group_name,
                    handler=None,
                    initial_value=0,
                    description=f"ELM3704 terminal channel#{i} value",
                )
            else:
                attr_dict[f"AICh{i}ValueOvsmpl"] = AttrR(
                    datatype=Waveform(
                        array_dtype=np.int32, shape=(self.oversampling_factor,)
                    ),
                    access_mode=AttrMode.READ,
                    group=self.attr_group_name,
                    handler=None,
                    initial_value=np.zeros((self.oversampling_factor,), dtype=np.int32),
                    description=f"ELM3704 terminal channel#{i} value",
                )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"PAIStatusChannel{i}.Status"
            self.ads_name_map[f"AICh{i}LatchTime"] = (
                f"PAITimestampChannel{i}.StartTimeNextLatch"
            )
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = (
                f"PAISamples{self.oversampling_factor}Channel{i}.Samples"
            )

        return attr_dict


# Map of supported controllers available to the FastCS CATio system
SUPPORTED_CONTROLLERS: dict[
    str, type[CATioDeviceController | CATioTerminalController]
] = {
    "EK1100": EK1100Controller,
    "EK1101": EK1101Controller,
    "EK1110": EK1110Controller,
    "EL1004": EL1004Controller,
    "EL1014": EL1014Controller,
    "EL1084": EL1084Controller,
    "EL1124": EL1124Controller,
    "EL1502": EL1502Controller,
    "EL2024": EL2024Controller,
    "EL2024-0010": EL2024_0010Controller,
    "EL2124": EL2124Controller,
    "EL3104": EL3104Controller,
    "EL3602": EL3602Controller,
    "EL3702": EL3702Controller,
    "EL4134": EL4134Controller,
    "EL9410": EL9410Controller,
    "EL9505": EL9505Controller,
    "EL9512": EL9512Controller,
    "ELM3704-0000": ELM3704_0000Controller,
    "ETHERCAT": EtherCATMasterController,
}


class CATioServerController(CATioController):
    """A root controller for an ADS-based EtherCAT I/O server."""

    _subsystem = "server"

    def __init__(
        self,
        ip: str,
        target_netid: str,
        target_port: int,
        poll_period: float,
        notification_period: float,
    ) -> None:
        global STANDARD_POLL_UPDATE_PERIOD, NOTIFICATION_UPDATE_PERIOD
        STANDARD_POLL_UPDATE_PERIOD = poll_period
        NOTIFICATION_UPDATE_PERIOD = notification_period
        logging.info(
            f"CATio standard polling period set to {STANDARD_POLL_UPDATE_PERIOD} "
            + "seconds and CATio notification update period set to "
            + f"{NOTIFICATION_UPDATE_PERIOD} seconds."
        )

        super().__init__(
            description="Root controller for an ADS-based EtherCAT I/O server"
        )
        self.name = "ROOT"
        self._cnx_settings = CATioConnectionSettings(ip, target_netid, target_port)
        self.attribute_map: dict[
            str, Attribute
        ] = {}  # key is attribute name, value is attribute object
        self.notification_enabled = False
        self.notification_stream: npt.NDArray | None = None
        logging.info("CATio Controller instantiated but not connected yet.")

    async def close(self):
        """Stop the device notifications and close the ADS connection."""
        logging.info(">------------ Stopping and deleting notifications.")
        self.connection.enable_notification_monitoring(False)
        self.notification_enabled = False
        self.notification_stream = None
        await self.connection.close()

    async def get_server_attributes(self) -> None:
        """
        Get and create all generic attributes associated with an EtherCAT I/O server.
        """
        _group = "IOServer"

        # Update the CATio client fast_cs_io_map
        io: IOServer = await self.connection.send_query(
            CATioFastCSRequest("IO_FROM_MAP", self.identifier, _group)
        )

        # NOT SURE WHY ATTRIBUTE NAME IN HANDLER CREATION IS REQUIRED!!!! CHECK!
        self.attributes["Name"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=_group,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="name"),
            initial_value=io.name,
            description="I/O server name",
        )

        self.attributes["Version"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=_group,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="version"),
            initial_value=io.version,
            description="I/O server version number",
        )

        self.attributes["Build"] = AttrR(
            datatype=String(),
            access_mode=AttrMode.READ,
            group=_group,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="build"),
            initial_value=str(io.build),
            description="I/O server build number",
        )

        self.attributes["DevCount"] = AttrR(
            datatype=Int(),
            access_mode=AttrMode.READ,
            group=_group,
            handler=CATioHandler.OnceAtStart.value.create(attribute_name="num_devices"),
            initial_value=int(io.num_devices),
            description="I/O server registered device count",
        )

        # Set all controller parameters as class attributes
        for attr_name in self.attributes.keys():
            setattr(self, "_" + attr_name, self.attributes[attr_name])

        logging.debug(
            f"{len(self.attributes)} fastCS attributes have been registered "
            + "with the I/O server controller."
        )

    async def register_system_subcontrollers(self) -> None:
        """Register all subcontrollers found in the EtherCAT system tree."""
        root_node: IOTreeNode = await self.connection.send_query(
            CATioFastCSRequest("SYSTEM_TREE")
        )
        assert isinstance(root_node.data, IOServer), (
            "The root of the EtherCAT system tree must be an I/O server."
        )
        await self.get_subcontrollers_from_node(root_node)

    async def get_complete_attribute_map(self) -> None:
        """Get a complete map of all attributes available to the CATio controller."""
        atrribute_refs = {
            ".".join(["_IOServer", key]): value
            for key, value in self.attributes.items()
        }
        for subctrl in self.get_sub_controllers().values():
            assert isinstance(subctrl, CATioSubController)
            gen_obj = subctrl.attribute_dict_generator()
            for value in gen_obj:
                atrribute_refs.update(value)
        self.attribute_map = atrribute_refs
        logging.debug(
            "Full map of available attributes to the CATio controller: "
            + f"{self.attribute_map.keys()}"
        )

    async def print_names(self) -> None:
        for name, subctrl in self.get_sub_controllers().items():
            print(f"CONTROLLER: {name}")
            assert isinstance(subctrl, CATioSubController)
            await subctrl.print_names()

    async def initialise(self) -> None:
        """
        Initiate a catio connection with the Beckhoff TwinCAT server.
        Introspect the current EtherCAT chain and initialise the system controllers.
        Create the FastCS attributes associated with each component found in the system.
        """
        await super().initialise()
        logging.debug("Initialising EtherCAT connection and CATio controllers...")

        await self._establish_tcp_connection(self._cnx_settings)
        logging.info("Client connection to TwinCAT server was successful.")

        await self.connection.initialise()
        logging.info("Client introspection of the I/O server was successful.")

        await self.get_server_attributes()
        logging.debug("Update of FastCS attributes for the I/O server was successful.")

        await self.register_system_subcontrollers()
        logging.info(
            "FastCS controllers have been created for the I/O server, EThercAT devices "
            + "and slave terminals."
        )
        # await self.print_names()
        await self.get_complete_attribute_map()
        logging.info(
            f"A map of all attributes linked to controller {self.name} was created."
        )

    def get_device_controller(self) -> EtherCATMasterController:
        """
        Get the EtherCAT master device controller from the registered subcontrollers.

        Note: it currently assumes a single device: the EtherCAT master !!!!!
        As is the logic for the client 'get_all_symbols()' anyway.
        """
        devices = []
        for subctrl in self.get_sub_controllers().values():
            if isinstance(subctrl, EtherCATMasterController):
                devices.append(subctrl)
        assert len(devices) == 1
        return devices[0]

    async def update_notification_timestamp(self, notifications: npt.NDArray) -> None:
        """Update the timestamp attribute associated with the notification message."""
        assert notifications.dtype.names

        # Extract the timestamps from the notification changes
        pattern = re.compile(r"^_(\w+(\(\w*\))*)+\.timestamp\d*")
        matches = [s for s in notifications.dtype.names if pattern.search(s)]
        timestamps = list(
            chain.from_iterable([notifications[name].tolist() for name in matches])
        )
        # Confirm that, if many notif streams, all timestamps have the same value
        assert all(x == timestamps[0] for x in timestamps), (
            "Notification timestamps are not identical for the multiple streams."
        )

        # Update the timestamp attribute for the device associated with the notification
        timestamp_attr_name = matches[0].rstrip(string.digits)
        timestamp_attr = self.attribute_map[timestamp_attr_name]
        timestamp_value = timestamp_attr.datatype.validate(
            filetime_to_dt(timestamps[0])
        )
        assert isinstance(timestamp_attr, AttrR)
        await timestamp_attr.set(timestamp_value)
        logging.info(
            f"Updated notification attribute {timestamp_attr_name} "
            + f"to value {timestamp_value}"
        )

    @scan(NOTIFICATION_UPDATE_PERIOD)
    async def notifications(self):
        """
        Get and process the EtherCAT device notification stream.

        This method periodically checks for new notification messages from the
        CATio client and updates the relevant FastCS attributes if any changes are
        detected."""

        if self.notification_stream is None:
            # Wait for the notifications to be setup by the timestamp attribute handler.
            dev_ctrl = self.get_device_controller()
            assert dev_ctrl is not None
            if not dev_ctrl.notification_ready:
                return
            # Request the CATio client to start publishing notifications
            self.connection.enable_notification_monitoring(
                True, NOTIFICATION_UPDATE_PERIOD
            )
            self.notification_enabled = True

        if self.notification_enabled:
            # Get the stream of notifications accumulated over the last period
            notifs = await self.connection.get_notification_streams(timeout=5)

            # Average the accumulated notification stream values for each element.
            mean = process_notifications(average, notifs)
            # logging.debug(f"Mean of accumulated notifications: {mean.dtype}, {mean}")

            # Use the first notification stream as the reference for future updates.
            if self.notification_stream is None:
                self.notification_stream = mean
                return

            # Get the changes between the current and previous notification streams
            diff = get_notification_changes(mean, self.notification_stream)
            assert diff.dtype.names

            # Update the previous notification stream value to the latest one received
            self.notification_stream = mean

            # Extract and set the timestamp attribute from the notification changes
            await self.update_notification_timestamp(diff)

            # Filter out any non-value fields from the notification changes
            non_value_names = [name for name in diff.dtype.names if "value" not in name]
            if len(non_value_names) == len(diff.dtype.names):
                return

            # Remove the notification fields that have changed which aren't relevant
            filtered_diff = rfn.drop_fields(
                diff, drop_names=non_value_names, usemask=False, asrecarray=True
            )

            assert filtered_diff.dtype.names
            for name in filtered_diff.dtype.names:
                # Remove the '.value' from the notification name
                attr_name = name.rsplit(".", 1)[0]
                if attr_name in self.attribute_map.keys():
                    notif_attribute = self.attribute_map[attr_name]
                    # Extract the new value from the notification field
                    if isinstance(filtered_diff[name], np.ndarray):
                        # Handle the oversampling arrays
                        if filtered_diff[name].ndim > 1:
                            assert filtered_diff[name].shape[0] == 1, (
                                "Bad array format received from the notification stream"
                            )
                            val = filtered_diff[name].flatten()

                        # Single discrete value
                        else:
                            if filtered_diff[name].shape[0] > 1:
                                # 1D array with multiple values
                                val = filtered_diff[name]
                            else:
                                # Discrete value expressed as 1D array
                                val = filtered_diff[name][0]
                        new_value = notif_attribute.datatype.validate(val)

                    else:
                        new_value = notif_attribute.datatype.validate(
                            filtered_diff[name]
                        )

                    assert isinstance(notif_attribute, AttrR)
                    await notif_attribute.set(new_value)
                    logging.info(
                        f"Updated notification attribute {attr_name} to value {new_value}."
                    )
