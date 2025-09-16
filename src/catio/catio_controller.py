import asyncio
import logging
import re
from collections.abc import Generator, Sequence
from itertools import chain
from typing import Any

import numpy as np
import numpy.typing as npt
from fastcs.attributes import Attribute, AttrR, AttrRW, AttrW
from fastcs.controller import Controller, SubController
from fastcs.wrappers import scan
from numpy.lib import recfunctions as rfn

from catio.utils import (
    average,
    filetime_to_dt,
    get_notification_changes,
    process_notifications,
)

from .catio_adapters import (
    CATioParameter,
    CommandParamHandler,
    ReadWriteParamHandler,
    Subsystem,
)
from .catio_connection import (
    CATioConnection,
    CATioConnectionSettings,
    CATioFastCSRequest,
)
from .devices import IODevice, IONodeType, IOServer, IOSlave, IOTreeNode

NOTIFICATION_UPDATE_PERIOD: float = 0.2


class CATioSubsystemController(SubController):
    """
    A root sub-controller for an ADS-based EtherCAT system.
    Such sub-controller will be used to define distinct components in the \
        EtherCAT system, e.g. the server, devices and slave terminals.
    """

    _subsystem: Subsystem

    def __init__(
        self,
        # queue_subsystem_update: Callable[[list[Coroutine]], Coroutine],
        connection: CATioConnection,
        eCAT_name: str,
        name: str = "",
        description: str = "",
        subcontrollers: list["CATioSubsystemController"] = [],
    ):
        super().__init__(description)
        # self._queue_subsystem_update = queue_subsystem_update
        self.connection = connection
        self.eCAT_name = eCAT_name
        self.name = name
        self.subcontrollers = subcontrollers

    @property
    def subsystem(self) -> str:
        return self._subsystem

    async def _introspect_parameters(self) -> Sequence[CATioParameter]:
        """
        Introspect the EtherCAT system to extract all available parameters.

        :returns: a list of CATio parameters
        """
        parameters: Sequence[CATioParameter] = []

        # Get the keyword arguments specific to the subcontroller
        kwargs = {}
        base_attributes = CATioSubsystemController(
            CATioConnection(), ""
        ).__dict__.keys()
        extra_attributes = list(set(self.__dict__.keys()) - set(base_attributes))
        if extra_attributes:
            for attr in extra_attributes:
                kwargs[attr] = getattr(self, attr)

        # Remove spaces from the EtherCAT name
        matches = re.search(r"^(\w+\s+)\d+", self.eCAT_name)
        trimmed_name = matches.group(0).replace(" ", "") if matches else self.eCAT_name

        # Get all CATio parameters associated with the subcontroller
        params = await self.connection.send_query(
            CATioFastCSRequest(
                f"{self._subsystem.upper()}_PARAMS", trimmed_name, **kwargs
            )
        )
        for param in params:
            parameters.extend(
                [CATioParameter(param, subsystem=self._subsystem, group=trimmed_name)]
            )

        return parameters

    def _create_attributes(self, parameters: Sequence[CATioParameter]) -> None:
        """
        Update the sub-controller object attributes from the available CATio parameters.

        :param parameters: a list of CATio parameters available for the EtherCAT system.
        """
        for param in parameters:
            match param.access:
                case "r":
                    self.attributes[param.name] = AttrR(
                        datatype=param.type,
                        group=param.group,
                        handler=param.handler.value.create(
                            attribute_name=param.name, kwargs=param.kwargs
                        )
                        if param.handler is not None
                        else None,
                        initial_value=param.value,
                        description=param.description,
                    )
                case "w":
                    self.attributes[param.name] = AttrW(
                        datatype=param.type,
                        group=param.group,
                        handler=CommandParamHandler(),
                        description=param.description,
                    )
                case "rw":
                    self.attributes[param.name] = AttrRW(
                        datatype=param.type,
                        group=param.group,
                        handler=ReadWriteParamHandler(),
                        initial_value=param.value,
                        description=param.description,
                    )
            # Set all subsystem parameters as class attributes
            setattr(self, "_" + param.name, self.attributes[param.name])

        # Check for requested callback functions.
        # This is used to update multiple attributes following a singlewaveform read.
        for param in parameters:
            if param.kwargs:
                callbacks = param.kwargs.get("callbacks", None)
                if callbacks is not None:
                    assert isinstance(callbacks, list)
                    attr = self.attributes[param.name]
                    assert isinstance(attr, AttrR)

                    async def on_update(value: npt.NDArray, callbacks=callbacks):
                        assert callbacks is not None
                        assert value.size == len(callbacks)
                        for idx, name in enumerate(callbacks):
                            subattr = self.attributes[name]
                            assert isinstance(subattr, AttrR)
                            await subattr.set(value[idx])
                            # logging.debug(
                            #     f"Sub-attribute updated to new value: {subattr.get()}"
                            # )

                    attr.add_update_callback(on_update)

    def attribute_dict_generator(
        self,
    ) -> Generator[dict[str, dict[str, Attribute]], Any, Any]:
        """
        Recursively extract all attribute references from the subcontroller \
            and its subcontrollers.

        :yields: a dictionary with the subcontroller eCAT name as key \
            and its attributes dictionary as value.
        """
        yield {f"_{self.eCAT_name.replace(' ', '')}": dict(self.attributes.items())}
        if self.subcontrollers:
            for subctrl in self.subcontrollers:
                yield from subctrl.attribute_dict_generator()

    async def initialise(self) -> None:
        """Initialise a CATio sub-controller."""
        parameters = await self._introspect_parameters()
        self._create_attributes(parameters)

        for name, attribute in self.attributes.items():
            if isinstance(attribute, AttrR):
                pass
                # logging.debug(
                #     f"Attribute keys available to subcontroller {self.eCAT_name} are \
                #         {self.attributes.keys()}"
                # )
                # logging.debug(f"Current AttrR values -> {name} = {attribute.get()}")


class CATioController(Controller):
    """
    A root controller for an ADS-based EtherCAT system using a Beckhoff TwinCAT server.
    A TwinCAT server is restricted to a single client connection from the same host.
    """

    def __init__(
        self,
        ip: str,
        target_netid: str,
        target_port: int,
        poll_period: float,
    ) -> None:
        super().__init__(description="Controller for an ADS-based EtherCAT I/O system")
        self._catio_cnx_settings = CATioConnectionSettings(
            ip, target_netid, target_port
        )
        self.connection = CATioConnection()
        self.queue = asyncio.Queue()
        self.counter = 0
        self.attribute_map: dict[
            str, dict[str, Attribute]
        ] = {}  # key is subcontroller, value is dict(attr.name: Attribute)
        self.notification_enabled = False
        self.notification_stream: npt.NDArray | None = None
        self.notification_timestamp: np.datetime64 | None = None
        logging.info("CATio Controller instantiated but not connected yet.")

    async def close(self):
        logging.info(">------------ Stopping and deleting notifications.")
        self.connection.enable_notification_monitoring(False)
        self.notification_enabled = False
        self.notification_stream = None
        await self.connection.close()

    async def _get_root_attributes(self) -> None:
        """
        Read the fixed attributes associated with the root controller \
            (the unique I/O server in the EtherCAT system).

        :returns: a dictionary of fast_cs attributes (key is name, value is attribute)
        """
        group = "IOServer"

        # Get the CATio parameters specific to the root controller, i.e. the I/O Server
        params = await self.connection.send_query(
            CATioFastCSRequest("SERVER_PARAMS", group)
        )
        parameters: Sequence[CATioParameter] = []
        for param in params:
            parameters.extend([CATioParameter(param, subsystem="server", group=group)])

        # Populate the controller's fast-cs attribute dictionary
        for parameter in parameters:
            assert parameter.access == "r", "I/O server parameter must be read-only."
            self.attributes[parameter.name] = AttrR(
                datatype=parameter.type,
                group=parameter.group,
                handler=parameter.handler.value.create(attribute_name=parameter.name)
                if parameter.handler
                else None,
                initial_value=parameter.value,
                description=parameter.description,
            )
            # Set all controller parameters as class attributes
            setattr(self, "_" + parameter.name, self.attributes[parameter.name])

        logging.debug(
            f"{len(self.attributes)} fastCS attributes have been registered "
            + "with the I/O server controller."
        )

    async def _get_subcontrollers(
        self,
        node: IOTreeNode,
    ) -> None | CATioSubsystemController:
        """
        Recursively register all sub-controllers available from a system node \
            with their parent controller.
        Once registered, each subcontroller is then initialised (attributes are created).

        :param node: the tree node to extract available subcontrollers from.
        """
        # Traverse the EtherCAT system from top to bottom, left to right
        subcontrollers: list[CATioSubsystemController] = []
        if node.has_children():
            for child in node.children:
                ctrl = await self._get_subcontrollers(child)
                assert ctrl is not None
                subcontrollers.append(ctrl)
            logging.debug(
                f"{len(subcontrollers)} subcontrollers were found for {node.data.name}."
            )

        # If it is a leaf node, define the type of subcontroller
        match node.data.category:
            case IONodeType.Server:
                assert subcontrollers, (
                    "No EtherCAT subcontroller attached to the I/O server."
                )
                assert isinstance(node.data, IOServer)
                logging.debug(
                    "I/O server controller implemented as the root CATioController."
                )
                self.subcontrollers = subcontrollers
                self.name = "ROOT"
                ctrl = self

            case IONodeType.Device:
                assert subcontrollers, (
                    "No EtherCAT subcontroller attached to the EtherCAT Device."
                )
                assert isinstance(node.data, IODevice)
                ctrl = CATioDeviceController(
                    connection=self.connection,
                    eCAT_name=node.data.name,
                    name=node.data.get_type_name(),
                    description=f"Controller for EtherCAT device #{node.data.id}",
                    subcontrollers=subcontrollers,
                )

            case IONodeType.Coupler | IONodeType.Slave:
                assert isinstance(node.data, IOSlave)
                ctrl = CATioTerminalController(
                    connection=self.connection,
                    eCAT_name=node.data.name,
                    name=node.data.get_type_name(),
                    description=f"Controller for {node.data.category.value} terminal "
                    + f"'{node.data.name}'",
                    subcontrollers=subcontrollers,
                    parent_id=node.data.parent_device,
                )

        # Initialise and register each subcontroller
        for subctrl in ctrl.subcontrollers:
            logging.debug(
                f"Initialising sub-controller {subctrl.name} with FastCS attributes."
            )
            await subctrl.initialise()
            logging.debug(
                f"Registering sub-controller {subctrl.name} to controller {ctrl.name}"
            )
            ctrl.register_sub_controller(subctrl.name.capitalize(), subctrl)

        return ctrl if isinstance(ctrl, CATioSubsystemController) else None

    async def _register_subcontrollers(self, system_tree: IOTreeNode) -> None:
        """
        Traverse the EtherCAT system tree once, from top to bottom and left to right.
        CATio subcontrollers are registered and initialised for each node in the tree.
        """
        # Register the low level subcontrollers (terminals/coupler with devices).
        for node in system_tree.node_generator():
            await self._get_subcontrollers(node)
            break

    def _get_all_attribute_references(self) -> None:
        """
        Recursively extract all attribute references from the controller \
            and its subcontrollers.
        """
        atrribute_refs = {"IOServer": dict(self.attributes.items())}
        for subctrl in self.subcontrollers:
            gen_obj = subctrl.attribute_dict_generator()
            for value in gen_obj:
                atrribute_refs.update(value)
        self.attribute_map = atrribute_refs

    async def initialise(self) -> None:
        """
        Initiate a catio connection with the Beckhoff TwinCAT server.
        Introspect the current EtherCAT chain and initialise the system controllers.
        Create the FastCS attributes associated with each component found in the system.
        """
        logging.debug("Initialising EtherCAT connection and CATio controllers...")

        await self.connection.connect(self._catio_cnx_settings)
        logging.info("Client connection to TwinCAT server was successful.")

        await self.connection.initialise()
        logging.info("Client introspection of the I/O server was successful.")

        await self._get_root_attributes()
        logging.debug("Update of FastCS attributes for the I/O server was successful.")

        sys_tree = await self.connection.send_query(CATioFastCSRequest("SYSTEM_TREE"))
        await self._register_subcontrollers(sys_tree)
        logging.info(
            "FastCS controllers have been created for the I/O server, EThercAT devices "
            + "and slave terminals."
        )

        self._get_all_attribute_references()
        logging.info(
            f"A map of all attributes linked to controller {self.name} was created."
        )

    async def attribute_initialise(self):
        """Initialise the FastCS attributes and their associated handlers for the \
            CATio controller and all subcontrollers in the EtherCAT system."""
        logging.debug("Initialising CATio controller and subcontrollers' attributes...")

        return await super().attribute_initialise()

    async def connect(self):
        """
        Create  a catio connection with the Beckhoff TwinCAT server.
        Introspect the current EtherCAT chain and initialise the system controllers.
        """
        logging.debug(
            "CATio connection already established during controller initialisation."
        )
        logging.info("CATio Controller instance is now up and running.")
        await super().connect()

        # Request the CATio client to start publishing notifications
        self.connection.enable_notification_monitoring(True, NOTIFICATION_UPDATE_PERIOD)
        self.notification_enabled = True

    async def send_query(self, message: str) -> Any:
        """
        Send a request to the I/O server from the CATio controller.

        :param message: a CATio request message which will be routed via the client.

        :returns: the response to the query as received by the CATio client
        """
        response = await self.connection.send_query(CATioFastCSRequest(message))
        logging.info(f"Response to '{message}' query: {response}")
        return response

    @scan(NOTIFICATION_UPDATE_PERIOD)
    async def notifications(self):
        if self.notification_enabled:
            # Get the stream of notifications accumulated over the last period
            notifs = await self.connection.get_notification_streams(timeout=5)

            # Average the accumulated notification stream values for each element.
            mean = process_notifications(average, notifs)
            # print(f" Mean: {mean.dtype}, {mean}")

            # Use the first notification stream as the reference for future updates.
            if self.notification_stream is None:
                self.notification_stream = mean
                return

            # Get the changes between the current and previous notification streams
            diff = get_notification_changes(mean, self.notification_stream)
            print(f" Diff: {diff.dtype}, {diff}")

            # Extract the timestamps from the notification changes
            pattern = re.compile(r"^_(\w+(\(\w*\))*)+\.timestamp\d*")
            assert diff.dtype.names
            assert len({name.split(".", 1)[0] for name in diff.dtype.names}) == 1, (
                "Notification timestamps do not belong to the same device."
            )
            matches = [s for s in diff.dtype.names if pattern.search(s)]
            timestamps = list(
                chain.from_iterable([diff[name].tolist() for name in matches])
            )
            assert all(x == timestamps[0] for x in timestamps), (
                "Notification timestamps are not identical for the multiple streams."
            )
            self.notification_timestamp = filetime_to_dt(timestamps[0])
            logging.debug(f"Notification timestamp: {self.notification_timestamp}")

            # Update the timestamp attribute for the device associated with the notifications
            device_name = diff.dtype.names[0].split(".")[0]
            attr = self.attribute_map[device_name]["timestamp"]
            assert isinstance(attr, AttrR)
            await attr.set(self.notification_timestamp)
            logging.debug(f"Attribute 'timestamp' updated to new value: {attr.get()}")

            # Remove the timestamp fields from the notification changes and create a numpy record array
            diff = rfn.drop_fields(diff, matches, usemask=False, asrecarray=True)

            # Filter out any non-value fields from the notification changes
            if diff.dtype.names:
                filtered_diff = diff[np.char.find(diff.dtype.names, "value") >= 0]
                if filtered_diff.size == 0:
                    return
                if filtered_diff.dtype.names:
                    # print(f"Map: {self.attribute_map.keys()}")
                    for name in filtered_diff.dtype.names:
                        components = name.split(".")
                        assert components[0] in self.attribute_map, (
                            f"Attribute map doesn't contain subcontroller '{components[0]}'."
                        )
                        print(
                            f">> ========= HOORAY, got one subcontroller change: {name}"
                        )
                        # TO DO: NEED TO FIND A WAY TO MAP THE NOTIFICATION NAME TO THE ATTRIBUTE NAME
                        # e.g. notif = _Term10(EL4134).AOOutputChannel4.Analogoutput.value
                        # attr_map = _Term10(EL4134).ao_channel4    (small name required by PV name creator)

            print(f" Filtered Diff: {diff.dtype}, {diff}")


class CATioServerController(CATioSubsystemController):
    """"""

    _subsystem = "server"

    # Server parameters to use in internal logic
    # n/a


class CATioDeviceController(CATioSubsystemController):
    """"""

    _subsystem = "device"

    def __init__(
        self,
        connection: CATioConnection,
        eCAT_name: str,
        name: str = "",
        description: str = "",
        subcontrollers: list[CATioSubsystemController] = [],
    ):
        super().__init__(connection, eCAT_name, name, description, subcontrollers)
        self.id = self.get_device_id()

    # Device parameters to use in internal logic
    # n/a

    async def initialise(self) -> None:
        # Get available symbols and setup notifications
        await super().initialise()
        await self.setup_symbol_notifications()

    def get_device_id(self) -> int:
        """Extract the id value from the device name (e.g. from ETH5 or EBUS12)."""
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
        await self.connection.add_notifications(self.id)


class CATioTerminalController(CATioSubsystemController):
    """"""

    _subsystem = "terminal"

    def __init__(
        self,
        connection: CATioConnection,
        eCAT_name: str,
        name: str = "",
        description: str = "",
        subcontrollers: list[CATioSubsystemController] = [],
        parent_id: int | None = None,
    ):
        super().__init__(connection, eCAT_name, name, description, subcontrollers)
        self.parent_id = parent_id

    # Terminal parameters to use in internal logic
    # n/a


def print_registered_ctrl(ctrl: CATioController | CATioSubsystemController) -> None:
    """Print the registered subcontrollers for a given controller."""
    if ctrl.subcontrollers:
        print(
            f"Subcontrollers registered with {ctrl.name}: {ctrl.get_sub_controllers()}"
        )
        for subctrl in ctrl.subcontrollers:
            print_registered_ctrl(subctrl)
