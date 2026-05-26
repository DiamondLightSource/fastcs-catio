import inspect
import re
import string
import time
from abc import abstractmethod
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from itertools import chain, count
from types import FrameType
from typing import Any

import numpy as np
import numpy.typing as npt
from fastcs.attributes import Attribute, AttrR
from fastcs.controllers import Controller, GroupLayout
from fastcs.datatypes import Int, String, Waveform
from fastcs.methods import scan
from fastcs.tracer import Tracer
from fastcs.util import ONCE
from numpy.lib import recfunctions as rfn

from fastcs_catio._constants import DeviceType
from fastcs_catio.catio_attribute_io import (
    CATioControllerAttributeIO,
    CATioControllerAttributeIORef,
    CATioControllerCoEAttributeIO,
    CATioControllerSymbolAttributeIO,
)
from fastcs_catio.client import REMOTE_UDP_PORT, RemoteRoute, get_remote_address
from fastcs_catio.devices import IODevice, IONodeType, IOServer, IOSlave, IOTreeNode
from fastcs_catio.logging import get_logger
from fastcs_catio.utils import (
    average,
    check_ndarray,
    filetime_to_dt,
    get_notification_changes,
    process_notifications,
    trim_ecat_name,
)

from .catio_connection import (
    CATioConnection,
    CATioFastCSRequest,
    CATioServerConnectionSettings,
)

NOTIFICATION_UPDATE_PERIOD: float = 0.2
STANDARD_POLL_UPDATE_PERIOD: float = 1.0


tracer = Tracer()
logger = get_logger(__name__)


class CATioController(Controller, Tracer):
    """
    A controller for an ADS-based EtherCAT system.
    Such base controller is used to define distinct components in the EtherCAT system, \
        e.g. server, devices and slave terminals.
    """

    _ctrl_obj: Iterator[int] = count(start=0, step=1)
    """Class counter associating each controller to a unique identifier"""
    _tcp_connection: CATioConnection = CATioConnection()
    """TCP connection to the CATio server, only one per client"""

    def __init__(
        self,
        name: str = "UNKNOWN",
        ecat_name: str = "",
        description: str | None = None,
        group: str = "",
        # comments: str = ""    # TO DO: can comments attribute be written to hardware?
        *,
        path: list[str] | None = None,
        group_layout: GroupLayout | None = None,
    ):
        # tracer.log_event("CATio controller creation", topic=self, name=name)

        self._identifier: int = next(CATioController._ctrl_obj)
        """Unique identifier for the controller instance."""
        self._io: IOServer | IODevice | IOSlave | None = None
        """The I/O object referenced by the CATio controller."""
        self.name: str = name
        """Name of the I/O controller."""
        self.ecat_name = ecat_name
        """Name of the I/O controller in the EtherCAT system."""
        self.group = group
        """Group name associated with the controller."""
        self.attr_group_name = trim_ecat_name(ecat_name)
        """Controller attributes' group name derived from the ecat name."""
        if getattr(self, "io_function", None) is None:
            self.io_function = ""
            """Function description of the I/O controller."""
        # self.comments: str = comments
        self.ads_name_map: dict[
            str, str
        ] = {}  # key is FastCS attribute name, value is complex ads symbol name
        """Map of FastCS attribute names to ADS symbol names."""

        logger.verbose(
            f"CATio controller '{self.ecat_name}' instantiated with PV suffix "
            + f"{self.name} and registered with id {self._identifier}"
        )

        super().__init__(
            description=description,
            ios=[
                CATioControllerAttributeIO(
                    self.connection,
                    self.group,
                    self._identifier,
                ),
                CATioControllerSymbolAttributeIO(
                    self.connection,
                    self.group,
                    self._identifier,
                    self.ads_name_map,
                ),
                CATioControllerCoEAttributeIO(
                    self.connection,
                    self.group,
                ),
            ],
            path=path,
            group_layout=group_layout,
        )

    @property
    def connection(self) -> CATioConnection:
        """The TCP connection to the CATio server."""
        return self._tcp_connection

    @property
    def io(self) -> IOServer | IODevice | IOSlave | None:
        """The I/O object referenced by the CATio controller."""
        return self._io

    async def _get_io_from_map(self) -> IOServer | IODevice | IOSlave:
        """
        Get the I/O object associated with the controller from the CATio client \
            fast_cs_io_map.

        :returns: the I/O object associated with the controller.
        """
        return await self.connection.send_query(
            CATioFastCSRequest(
                "IO_FROM_MAP", self._identifier, self.group, self.ecat_name
            )
        )

    async def create_tcp_connection(
        self, tcp_settings: CATioServerConnectionSettings
    ) -> None:
        """Create the TCP connection to the CATio server if not already defined. \
            Otherwise, reuse the existing connection.
        Then connect to the Beckhoff TwinCAT server and initialise the CATio client.
        Hardware present in the EtherCAT I/O system will be identified and introspected.
        Subscribable parameters will be gathered for possible notification monitoring.

        :param tcp_settings: the TCP connection settings to use.
        """
        if not self.connection.is_defined():
            await self.connection.connect(tcp_settings)
            logger.info("Client connection to TwinCAT server was successful.")

            await self.connection.initialise()
            logger.info("Client introspection of the I/O server was successful.")

    async def initialise(self) -> None:
        """
        Initialise the CATio controller by creating its FastCS attributes.
        Each attribute is registered as a class instance attribute for easy access.
        """
        # await super().initialise()

        # Get the I/O object associated with the controller
        self._io = await self._get_io_from_map()
        assert self._io is not None, (
            "The I/O object associated with the controller must be defined."
        )
        # Get the current configuration of the controller
        await self.read_configuration()

        # Create the controller attributes
        await self.get_io_attributes()
        logger.info(
            f"Initialisation of FastCS attributes for CATio controller {self.name} "
            + "was successful."
        )

    async def read_configuration(self) -> None:
        """
        Get the current configuration of the controller from the CATio client.
        This includes updating any relevant internal state variables.
        """
        # Currently no specific configuration is needed at the base controller level
        # e.g. the server won't have any specific configuration
        pass

    async def get_generic_attributes(self) -> None:
        """
        Base method to create generic controller attributes applicable to all.
        """
        self.add_attribute(
            "Function",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("io_function", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io_function,
                description="I/O controller function",
            ),
        )
        logger.verbose(f"Generic attributes for controller {self.name} created.")

    @abstractmethod
    async def get_io_attributes(self) -> None:
        """Base method to create subcontroller-specific attributes."""
        ...

    async def get_root_node(self) -> IOTreeNode:
        """
        Get the root node of the EtherCAT system tree.
        It should be an I/O server and the parent of all other nodes.
        Each node can be a device or a terminal and can have children nodes.

        :returns: the root node of the EtherCAT system tree.
        """
        root_node: IOTreeNode = await self.connection.send_query(
            CATioFastCSRequest("SYSTEM_TREE")
        )
        assert isinstance(root_node.data, IOServer), (
            "The root of the EtherCAT system tree must be an I/O server."
        )
        return root_node

    async def add_subcontrollers(self, subcontrollers: list["CATioController"]) -> None:
        """
        Register the given subcontrollers with this controller.

        :param subcontrollers: a list of subcontrollers to register.
        """
        if subcontrollers:
            for subctrl in subcontrollers:
                logger.verbose(
                    f"Registering sub-controller {subctrl.name} with controller "
                    + f"{self.name}."
                )
                self.add_sub_controller(trim_ecat_name(subctrl.name), subctrl)

    def attribute_dict_generator(
        self,
    ) -> Generator[dict[str, Attribute], Any, Any]:
        """
        Recursively extract all attribute references from the controller \
            and its subcontrollers.

        :yields: a dictionary with the (sub)controller's full attribute name as key \
            and the attribute object as value.
        """
        attr_dict = {}
        # Extract the current controller's attributes and prefix them with the ecat name
        for key, attr in self.attributes.items():
            if isinstance(self, CATioController):
                ads_name = self.ads_name_map.get(key, None)
                key = ads_name if ads_name is not None else key
            attr_dict[".".join([f"_{self.ecat_name}", key])] = attr
        logger.verbose(
            f"Extracted {len(attr_dict)} attributes for controller {self.name}."
        )
        yield attr_dict

        # Recursively extract the current controller's subcontrollers' attributes
        if self.sub_controllers:
            for subctrl in self.sub_controllers.values():
                assert isinstance(subctrl, CATioController)
                yield from subctrl.attribute_dict_generator()

    async def connect(self) -> None:
        """Establish the FastCS connection to the controller and its subcontrollers."""
        await super().connect()
        if self.sub_controllers:
            for name, subctlr in self.sub_controllers.items():
                assert isinstance(subctlr, CATioController)
                await subctlr.connect()
                logger.verbose(f"Connection to subcontroller {name} completed.")

    async def query_api(self, function_name: str) -> Any:
        """
        Interrogate the CATio client API for an attribute-related query.

        :param function_name: the root name of the CATio API function to query.

        :returns: the response received from the CATio client.
        """
        query = f"{self.group.upper()}_{function_name.upper()}_ATTR"
        try:
            response = await self.connection.send_query(
                CATioFastCSRequest(command=query, controller_id=self._identifier)
            )
            if response is None:
                logger.verbose(
                    f"No corresponding API method was found for command '{query}'"
                )
            return response
        except (KeyError, ValueError) as err:
            logger.error(
                f"Error querying CATio client API with command '{query}': {err}"
            )
            return None

    async def update_nparray_subattributes(
        self, attr_names: list[str], caller: FrameType, dtype: npt.DTypeLike
    ) -> None:
        """
        Update the sub-attributes of a numpy array attribute by querying \
            the associated CATio client API function.

        :param attr_names: a list of attribute names to update.
        :param caller: the frame of the calling function.
        :param dtype: the expected numpy data type of the attribute values.
        """
        # Get the associated attributes
        attr_dict = {k: self.attributes[k] for k in attr_names if k in self.attributes}

        # Get the current attribute value
        results = []
        for attr in list(attr_dict.values()):
            assert isinstance(attr, AttrR)
            results.append(attr.get())
        value = np.array(results, dtype=dtype)

        # Get the name of the associated CATio API function and call it
        fn_name = caller.f_code.co_name
        response = await self.query_api(fn_name.replace("_", ""))

        if response is not None:
            # Check that the received response has the expected type and format
            assert check_ndarray(response, dtype, value.shape), (
                f"{fn_name.upper()}: unexpected response type {type(response)}"
            )

            # Determine if the attribute value has changed, and update accordingly
            if not np.array_equal(response, value):
                for name, new_value in zip(
                    attr_names, np.nditer(response), strict=True
                ):
                    attr = self.attributes[name]
                    assert isinstance(attr, AttrR)
                    await attr.update(new_value)

                logger.verbose(
                    f"{fn_name} attributes for device {self.name} have been updated."
                )


@dataclass
class CATioTCPSettings:
    target_ip: str
    target_port: int = 27905
    tcp_port: int = 48898


@dataclass
class CATioRouteSettings:
    route_name: str = ""
    user_name: str = "Administrator"
    password: str = "1"
    udp_port: int = REMOTE_UDP_PORT


@dataclass
class CATioScanTimings:
    poll_period: float = 1.0
    notification_period: float = 0.2


# Keys that are valid inside each template field.
# {} / {n} / {n:02d}  → numeric index (id, chain node, or chain position)
# {id}               → the IOC root prefix (from the YAML `id:` field)
# {device_prefix}    → rendered name of the parent device
#                      (node_prefix and module_prefix only)
# {node_prefix}      → rendered name of the parent coupler/box
#                      (module_prefix only)
_VALID_TEMPLATE_KEYS: dict[str, frozenset[str]] = {
    "device_prefix": frozenset({"id", "n"}),
    "node_prefix": frozenset({"id", "n", "device_prefix"}),
    "module_prefix": frozenset({"id", "n", "node_prefix", "device_prefix"}),
}


@dataclass
class CATioNameMappings:
    """User-configurable name templates for EtherCAT subcontrollers.

    Every template is rendered with Python's :meth:`str.format` using:

    * ``{}`` / ``{n}`` / ``{n:02d}``  — numeric index for the node
      (device id, chain-node index, or chain-position index).
    * ``{id}``          — the IOC root prefix from the YAML ``id:`` field
      (e.g. ``BL04I-EA-CATIO-01``).  When this key is present the rendered
      result is treated as an *absolute* PV path and split on ``:`` into
      path segments.
    * ``{device_prefix}`` — the rendered name of the parent EtherCAT device.
      Valid inside ``node_prefix`` and ``module_prefix``.
    * ``{node_prefix}``  — the full path to the parent node (coupler/box, or device
      when no coupler is present) joined with ``:``.  Only valid inside
      ``module_prefix``.  Using this key always yields an absolute path after
      splitting, regardless of whether the parent is a multi-segment device path
      or a standalone coupler root.

    The rendered result is split on ``:`` to produce the controller's path
    segments.  The last segment becomes ``controller.name``.  For example,
    ``"{id}:ETH{n:02d}"`` rendered with id ``BL04I-EA-CATIO-01`` and n=1
    gives path ``["BL04I-EA-CATIO-01", "ETH01"]`` and name ``"ETH01"``.

    Unknown placeholder keys raise :exc:`ValueError` immediately on
    construction — before any hardware connection is attempted.
    """

    device_prefix: str = "ETH{}"
    node_prefix: str = "E1RIO{}"
    module_prefix: str = "MOD{}"

    def __post_init__(self) -> None:
        for field_name, valid_keys in _VALID_TEMPLATE_KEYS.items():
            template = getattr(self, field_name)
            for _, key, _, _ in string.Formatter().parse(template):
                # key is None for literal text; '' for positional {}; digit-only
                # strings for explicit positional indices like {0:02d} — all fine.
                if key and not key.isdigit() and key not in valid_keys:
                    raise ValueError(
                        f"name_mappings.{field_name!r}: unknown placeholder "
                        f"'{{{key}}}' in template {template!r}. "
                        f"Valid keys: {sorted(valid_keys)}"
                    )


@dataclass
class CATioServerControllerOptions:
    tcp_settings: CATioTCPSettings
    route: CATioRouteSettings = field(default_factory=CATioRouteSettings)
    scan_timings: CATioScanTimings = field(default_factory=CATioScanTimings)
    name_mappings: CATioNameMappings = field(default_factory=CATioNameMappings)


class CATioServerController(CATioController):
    """A root controller for an ADS-based EtherCAT I/O server."""

    def __init__(
        self,
        options: CATioServerControllerOptions,
        *,
        path=None,
    ) -> None:
        target_ip = options.tcp_settings.target_ip

        route = RemoteRoute(
            target_ip,
            route_name=options.route.route_name,
            user_name=options.route.user_name,
            password=options.route.password,
            udp_port=options.route.udp_port,
        )

        # Get remote target netid via udp connection.
        # The route already knows the remote's UDP discovery port; reuse it
        # so all UDP traffic for this remote goes to the same place.
        target_netid = get_remote_address(target_ip, route.udp_port)
        logger.info(f"{target_ip} remote has Ams netid: {target_netid}.")

        # Add a communication route to the remote via udp connection
        if not route.add():
            raise ConnectionRefusedError("Remote route addition failed.")
        self._route = route
        """Route object managing the communication route to the remote."""
        logger.info(f"Route to remote {target_ip} added successfully.")

        # Define the other instance variables
        self._tcp_settings = CATioServerConnectionSettings(
            target_ip,
            target_netid.to_string(),
            options.tcp_settings.target_port,
            options.tcp_settings.tcp_port,
        )
        """TCP connection settings for the CATio server."""
        self.io_function = "Beckhoff Embedded PC for I/O systems connection and control"
        """Function description of the I/O server controller."""
        self.attribute_map: dict[
            str, Attribute
        ] = {}  # key is attribute name, value is attribute object
        """Map of all attributes available to the CATio server controller."""
        self.notification_enabled = False
        """Flag indicating if notification monitoring is enabled."""
        self.notification_stream: npt.NDArray | None = None
        """Cached notification stream from the CATio client."""
        self._name_mappings = options.name_mappings
        """Naming templates for device/node/module subcontrollers."""

        # Update the global period variables
        global STANDARD_POLL_UPDATE_PERIOD, NOTIFICATION_UPDATE_PERIOD
        STANDARD_POLL_UPDATE_PERIOD = options.scan_timings.poll_period
        NOTIFICATION_UPDATE_PERIOD = options.scan_timings.notification_period
        logger.info(
            f"CATio standard polling period set to {STANDARD_POLL_UPDATE_PERIOD} "
            + "seconds and CATio notification update period set to "
            + f"{NOTIFICATION_UPDATE_PERIOD} seconds."
        )

        # The launcher framework injects 'path=[entry.id]' from fastcs.yaml
        # and the direct ioc command line injection uses 'path=[pv_prefix]'
        name = path[0] if path else "ROOT"

        # Initialise the base controller
        super().__init__(
            name=name,
            ecat_name="IOServer",
            description="Root controller for an ADS-based EtherCAT I/O server",
            group="server",
            path=path,
        )

    async def initialise(self) -> None:
        """
        Initialise the CATio server controller.
        This includes creating an ADS client for TCP communication \
            and registering all subcontrollers configured in the EtherCAT I/O system.

        This method is automatically called by the fastCS backend 'serve()' method.
        """
        logger.info(">-------- Initialising EtherCAT connection and CATio controllers.")

        await self.create_tcp_connection(self._tcp_settings)
        logger.info(
            "An ADS client for TCP communication with the remote "
            + f"at {self._tcp_settings.ip} has been established."
        )

        await self.register_subcontrollers()
        logger.info(
            "FastCS controllers have been created for the I/O server, EThercAT devices "
            + "and slave terminals."
        )

        await self.get_complete_attribute_map()
        logger.info(
            f"A map of all attributes linked to controller {self.name} was created."
        )

        # Gate bus subscriptions on attribute_map membership so the IOC
        # only subscribes to symbols a PV consumes. Closes the seam
        # behind issue #53 (e.g. _SyncUnits.*) without an ad-hoc
        # carve-out in the notification handler.
        self.connection.set_wanted_attribute_keys(self.attribute_map.keys())

    async def connect(self) -> None:
        """
        Establish the FastCS connection to the CATio server controller.
        This includes connecting all subcontrollers as well.

        This method is automatically called by the fastCS backend 'serve()' method.
        """
        await super().connect()
        logger.info(">-------- CATio Controller instances are now up and running.")

    async def disconnect(self) -> None:
        """
        Stop the device notification monitoring and unsubscribe from all notifications.
        Also close the ADS connection and remove the communication route to the remote.
        """
        logger.info(">-------- Stopping and deleting notifications.")
        self.connection.enable_notification_monitoring(False)
        self.notification_enabled = False
        self.notification_stream = None
        logger.info(">-------- Closing the ADS client communication.")
        await self.connection.close()
        # logger.info(">-------- Removing the existing route to the remote.")
        # self._route.delete()

    async def get_io_attributes(self) -> None:
        """Create and get all server controller attributes."""
        logger.verbose(
            "No specific attributes are defined for a CATio server controller"
        )
        await self.get_server_generic_attributes()

    async def get_server_generic_attributes(self) -> None:
        """
        Create and get all generic server attributes.
        """
        assert isinstance(self.io, IOServer), (
            f"Wrong I/O type associated with controller {self.name}"
        )

        # Get the generic attributes related to a CATioServerController
        await super().get_generic_attributes()

        self.add_attribute(
            "Name",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("name", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io.name,
                description="I/O server name",
            ),
        )

        self.add_attribute(
            "Version",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("version", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io.version,
                description="I/O server version number",
            ),
        )
        self.add_attribute(
            "Build",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("build", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=str(self.io.build),
                description="I/O server build number",
            ),
        )
        self.add_attribute(
            "DevCount",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("num_devices", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.num_devices),
                description="I/O server registered device count",
            ),
        )
        logger.verbose(f"Generic attributes for the controller {self.name} created.")

    async def register_subcontrollers(self) -> None:
        """Register all subcontrollers available in the EtherCAT system tree."""
        server_node: IOTreeNode = await self.get_root_node()
        await self.get_subcontrollers_from_node(server_node, self.path)

    @staticmethod
    def _render(template: str, index: int, context: dict[str, str]) -> str:
        """Render a name template in a single :meth:`str.format` pass.

        Passes *index* both as the first positional argument (so ``{}``
        and ``{:02d}`` work) and as the keyword argument ``n`` (so
        ``{n}`` and ``{n:02d}`` also work).  All *context* key/value
        pairs are forwarded as additional keyword arguments.
        """
        try:
            return template.format(index, n=index, **context)
        except KeyError as err:
            raise ValueError(
                f"Unknown placeholder {err} in name mapping template {template!r}. "
                f"Available keys: {sorted(context)}"
            ) from err
        except (IndexError, ValueError) as err:
            raise ValueError(
                f"Invalid name mapping template {template!r}: {err}"
            ) from err

    def _resolve_controller_name_and_path(
        self,
        node: IOTreeNode,
        parent_path: list[str],
    ) -> tuple[str, list[str]]:
        """Return ``(controller_name, path)`` for a non-server tree node.

        *controller_name* is the last path segment and is used as the FastCS
        controller name.  *path* is the full list of path segments that forms
        the PV prefix for the controller's attributes.
        """
        root_prefix = self.path[0] if self.path else ""

        if isinstance(node.data, IODevice):
            template = self._name_mappings.device_prefix
            index = int(node.data.id)
            context: dict[str, str] = {"id": root_prefix}
        elif isinstance(node.data, IOSlave):
            if node.data.category in (IONodeType.Coupler, IONodeType.Box):
                template = self._name_mappings.node_prefix
                index = int(node.data.loc_in_chain.node)
                context = {
                    "id": root_prefix,
                    # full path to the parent device joined as a colon-separated string
                    # so {device_prefix}:E1RIO{n} renders to a splittable absolute name
                    "device_prefix": ":".join(parent_path) if parent_path else "",
                }
            else:
                template = self._name_mappings.module_prefix
                index = int(node.data.loc_in_chain.position)
                context = {
                    "id": root_prefix,
                    # full parent path colon-joined, so {node_prefix}:MOD{n} produces
                    # an absolute path regardless of whether the parent is a standalone
                    # coupler root or a multi-segment device path
                    "node_prefix": ":".join(parent_path) if parent_path else "",
                    # device path: everything except the immediate parent segment;
                    # empty string when the coupler resolved to a standalone root
                    "device_prefix": (
                        ":".join(parent_path[:-1]) if len(parent_path) >= 2 else ""
                    ),
                }
        else:
            raise TypeError(f"Unsupported node data type: {type(node.data)!r}")

        rendered = self._render(template, index, context)
        path = [s for s in rendered.split(":") if s]
        return path[-1], path

    async def get_subcontrollers_from_node(
        self, node: IOTreeNode, parent_path: list[str]
    ) -> None | CATioController:
        """
        Recursively register all subcontrollers available from a system node \
            with their parent controller.
        To do so, the EtherCAT system is traversed from top to bottom, left to right.
        Once registered, each subcontroller is then initialised
        (attributes are created).

        Couplers/boxes whose resolved path is a single segment (i.e. they have a
        beamline-level PV prefix such as ``BL04I-EA-E1RIO-01``) are *hoisted*:
        they are registered as direct sub-controllers of the server rather than
        of the device, so that PVI can render them inline on the top-level screen
        instead of nesting a Grid inside a SubScreen (which PVI forbids).

        :param node: the tree node to extract available subcontrollers from.

        :returns: the (sub)controller object created for the current node.
        """
        current_path = parent_path
        controller_name = self.name
        if not isinstance(node.data, IOServer):
            controller_name, current_path = self._resolve_controller_name_and_path(
                node, parent_path
            )

        subcontrollers: list[CATioController] = []
        hoisted: list[CATioController] = []
        if node.has_children():
            for child in node.children:
                ctlr = await self.get_subcontrollers_from_node(child, current_path)
                assert (ctlr is not None) and (isinstance(ctlr, CATioController))
                # Hoist couplers/boxes with a root-level (1-segment) path to the
                # server so PVI can render them as inline Grid groups on the top-level
                # screen.  Multi-segment paths stay as SubScreen children of the device.
                if (
                    isinstance(node.data, IODevice)
                    and isinstance(child.data, IOSlave)
                    and child.data.category in (IONodeType.Coupler, IONodeType.Box)
                    and len(ctlr.path) == 1
                ):
                    ctlr.group_layout = GroupLayout.INLINE
                    hoisted.append(ctlr)
                else:
                    subcontrollers.append(ctlr)

            logger.verbose(
                f"{len(subcontrollers)} subcontrollers were found for "
                f"{node.data.name} ({len(hoisted)} hoisted to server)."
            )

        result = await self._get_subcontroller_object(
            node,
            subcontrollers,
            controller_name,
            current_path,
        )

        # Register hoisted couplers directly with the server after the device
        # controller has been created (so path/name are already resolved).
        for h in hoisted:
            self.add_sub_controller(trim_ecat_name(h.name), h)

        return result

    async def _get_subcontroller_object(
        self,
        node: IOTreeNode,
        subcontrollers: list[CATioController],
        controller_name: str,
        controller_path: list[str],
    ) -> None | CATioController:
        """
        Create the associated CATio controller/subcontroller object for the given node \
            in the EtherCAT tree.

        :param node: the tree node to extract the (sub)controller object from.
        :param subcontrollers: a list of subcontrollers associated with the node.

        :returns: the subcontroller object created for the current node.
        """
        # Lazy import to prevent circular import reference
        from fastcs_catio.catio_dynamic_controller import get_terminal_controller_class
        from fastcs_catio.catio_hardware import SUPPORTED_DEVICE_CONTROLLERS

        match node.data.category:
            case IONodeType.Server:
                assert isinstance(node.data, IOServer)
                ctlr = self
                await super().initialise()

            case IONodeType.Device:
                assert isinstance(node.data, IODevice)
                key = (
                    "ETHERCAT"
                    if node.data.type == DeviceType.IODEVICETYPE_ETHERCAT
                    else node.data.name
                )
                logger.verbose(
                    f"Implementing I/O device '{key}' as CATioSubController."
                )
                ctlr = SUPPORTED_DEVICE_CONTROLLERS[key](
                    name=controller_name,
                    ecat_name=node.data.name,
                    description=f"Controller for EtherCAT device #{node.data.id}",
                    path=controller_path,
                )
                await ctlr.initialise()

            case IONodeType.Coupler | IONodeType.Box | IONodeType.Slave:
                assert isinstance(node.data, IOSlave)
                logger.verbose(
                    f"Implementing I/O terminal '{node.data.name}' as "
                    f"CATioSubController."
                )
                ctlr_class = get_terminal_controller_class(node.data.type)

                ctlr = ctlr_class(
                    name=controller_name,
                    ecat_name=node.data.name,
                    description=f"Controller for {node.data.category.value} terminal "
                    + f"'{node.data.name}'",
                    path=controller_path,
                )
                await ctlr.initialise()

        # Register any subcontrollers with the current controller
        await ctlr.add_subcontrollers(subcontrollers)

        return ctlr

    async def get_complete_attribute_map(self) -> None:
        """
        Get a complete map of all attributes available to the CATio Server controller.
        The map keys are the full attribute names as per the ADS symbol names.
        """
        attribute_refs = {
            ".".join(["_IOServer", key]): value
            for key, value in self.attributes.items()
        }
        for subctrl in self.sub_controllers.values():
            assert isinstance(subctrl, CATioController)
            gen_obj = subctrl.attribute_dict_generator()
            for value in gen_obj:
                attribute_refs.update(value)
        self.attribute_map = attribute_refs
        logger.verbose(
            "Full map of attributes available to the CATio server controller: "
            + f"{self.attribute_map.keys()}"
        )

    def get_device_controller(self) -> CATioController:
        """
        Get the EtherCAT master device controller from the registered subcontrollers.

        Note: it currently assumes a single device: the EtherCAT master !!!!!
        As is the logic for the client 'get_all_symbols()' anyway.
        TO DO: extend to multiple devices if needed; other functions will be impacted!

        :returns: the EtherCAT master device controller.
        """
        devices = []
        for subctrl in self.sub_controllers.values():
            if isinstance(subctrl, CATioDeviceController):
                devices.append(subctrl)
        assert len(devices) == 1
        return devices[0]

    async def update_notification_timestamp(self, notifications: npt.NDArray) -> None:
        """
        Update the timestamp attribute associated with the notification message.

        :param notifications: the notification changes received from the CATio client.
        """
        assert notifications.dtype.names

        # Extract the timestamps from the notification changes
        pattern = re.compile(r"^_([\w ]+(\([\w ]*\))*)+\.timestamp\d*")
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
        await timestamp_attr.update(timestamp_value)
        # logger.verbose(
        #     f"Updated notification attribute {timestamp_attr_name} "
        #     + f"to value {timestamp_value}"
        # )

    @scan(NOTIFICATION_UPDATE_PERIOD)
    async def notifications(self):
        """
        Get and process the EtherCAT device notification stream.

        This method periodically checks for new notification messages from \
            the CATio client and updates the relevant FastCS attributes \
                if any changes are detected.
        """
        try:
            if self.notification_stream is None:
                # Get a reference to the EtherCAT Master Device which provides notifs
                dev_ctrl = self.get_device_controller()
                assert isinstance(dev_ctrl, CATioDeviceController)
                # Wait until the device controller is ready to provide notifications
                if not dev_ctrl.notification_ready:
                    logger.verbose("Notification setup not ready yet, monitoring off.")
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

                # Track whether this is the first notification processing
                is_first_notification = self.notification_stream is None
                if is_first_notification and mean.dtype.names is not None:
                    logger.debug(
                        f"FIRST NOTIFICATION: notification_stream is None, "
                        f"mean has {len(mean.dtype.names)} fields: {mean.dtype.names}"
                    )

                # Get the changes between the current and previous notif streams
                diff = get_notification_changes(mean, self.notification_stream)
                assert diff.dtype.names, (
                    "Expected a numpy structured array with fields."
                )

                if is_first_notification:
                    logger.debug(
                        f"FIRST NOTIFICATION: diff returned {len(diff.dtype.names)} "
                        f"fields: {diff.dtype.names}"
                    )
                else:
                    logger.debug(
                        f"Notification fields which show changes: "
                        f"{diff.dtype.names}, {diff}"
                    )

                # Update the previous notif stream value to the latest one received
                self.notification_stream = mean

                # Extract and set the timestamp attribute from the notif changes
                await self.update_notification_timestamp(diff)

                # Filter out any non-value fields from the notification changes
                non_value_names = [
                    name for name in diff.dtype.names if "value" not in name
                ]
                if is_first_notification:
                    logger.info(
                        f"FIRST NOTIFICATION: {len(non_value_names)} non-value fields, "
                        f"{len(diff.dtype.names) - len(non_value_names)} value fields"
                    )
                if len(non_value_names) == len(diff.dtype.names):
                    if is_first_notification:
                        logger.error(
                            "FIRST NOTIFICATION: Early return - no value fields found!"
                        )
                    return

                # Remove the notif fields that have changed which aren't relevant
                filtered_diff = rfn.drop_fields(
                    diff, drop_names=non_value_names, usemask=False, asrecarray=True
                )
                if is_first_notification:
                    assert filtered_diff.dtype.names
                    logger.debug(
                        f"FIRST NOTIFICATION: filtered_diff has "
                        f"{len(filtered_diff.dtype.names)} fields: "
                        f"{filtered_diff.dtype.names}"
                    )
                else:
                    logger.verbose(
                        f"Value field notifications which have changed: "
                        f"{filtered_diff} {filtered_diff.size}, {filtered_diff.shape}"
                    )

                assert filtered_diff.dtype.names
                updates_count = 0
                for name in filtered_diff.dtype.names:
                    # Remove the '.value' from the notification name
                    attr_name = name.rsplit(".", 1)[0]

                    if attr_name not in self.attribute_map.keys():
                        logger.warning(
                            f"No reference to {attr_name} in the CATio attribute map"
                        )
                        continue

                    notif_attribute = self.attribute_map[attr_name]

                    # Extract the new value from the notification field
                    if isinstance(filtered_diff[name], np.ndarray):
                        # Handle the oversampling arrays (must be 1D numpy arrays)
                        # e.g. shape of 'sample' with n values is: (1, n)
                        if filtered_diff[name].ndim > 1:
                            assert filtered_diff[name].shape[0] == 1, (
                                "Bad array format received from notification stream"
                            )
                            val = filtered_diff[name].flatten()
                        else:
                            # Handle 1D arrays with multiple values
                            # e.g. shape of X with n elements is: (n,)
                            if filtered_diff[name].shape[0] > 1:
                                val = filtered_diff[name]
                            else:
                                # Handle single discrete value expressed as 1D array
                                # e.g. shape of 'cyclecount' with single value is: (1,)
                                val = filtered_diff[name][0]
                        new_value = notif_attribute.datatype.validate(val)

                    else:
                        # Handle single discrete value
                        new_value = notif_attribute.datatype.validate(
                            filtered_diff[name]
                        )

                    assert isinstance(notif_attribute, AttrR)
                    await notif_attribute.update(new_value)
                    updates_count += 1
                    logger.verbose(
                        f"Updated notification attribute {attr_name} "
                        f"to value {new_value}."
                    )

                if is_first_notification:
                    logger.debug(
                        f"FIRST NOTIFICATION: Successfully updated {updates_count} "
                        f"attributes out of {len(filtered_diff.dtype.names)} "
                        f"value fields"
                    )
        except TimeoutError:
            # Timeout waiting for notifications (e.g., debugger pause) - just retry
            logger.warning(
                "Timeout waiting for notifications, will retry on next scan cycle"
            )
        except Exception:
            logger.exception("Error processing notification stream")


class CATioDeviceController(CATioController):
    """A controller for an EtherCAT I/O device."""

    def __init__(
        self,
        name: str,
        ecat_name: str = "",
        description: str | None = None,
        path: list[str] | None = None,
        group_layout: GroupLayout | None = None,
    ) -> None:
        super().__init__(
            name=name,
            ecat_name=ecat_name,
            description=description,
            group="device",
            path=path,
            group_layout=group_layout,
        )
        self.notification_ready: bool = False
        """Flag indicating if the device is ready to provide notifications."""

    async def get_io_attributes(self) -> None:
        """Create and get all device controller attributes."""
        await self.get_device_generic_attributes()

    async def get_device_generic_attributes(self) -> None:
        """
        Create and get all generic device attributes.
        """
        assert isinstance(self.io, IODevice), (
            f"Wrong I/O type associated with controller {self.name}"
        )

        # Get the generic attributes related to a CATioDeviceController
        initial_attr_count = len(self.attributes)
        await super().get_generic_attributes()

        self.add_attribute(
            "Id",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("id", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.id),
                description="I/O device identity number",
            ),
        )
        self.add_attribute(
            "Type",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("type", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.type),
                description="I/O device type",
            ),
        )
        self.add_attribute(
            "Name",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("name", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io.name,
                description="I/O device name",
            ),
        )
        self.add_attribute(
            "Netid",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("netid", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=str(self.io.netid),
                description="I/O device ams netid",
            ),
        )
        self.add_attribute(
            "Identity",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("identity", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=str(self.io.identity),
                description="I/O device identity",
            ),
        )
        self.add_attribute(
            "SystemTime",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.frame_counters.time),
                description="I/O device, EtherCAT frame timestamp",
            ),
        )
        self.add_attribute(
            "SentCyclicFrames",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.frame_counters.cyclic_sent),
                description="I/O device, sent cyclic frames counter",
            ),
        )
        self.add_attribute(
            "LostCyclicFrames",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.frame_counters.cyclic_lost),
                description="I/O device, lost cyclic frames counter",
            ),
        )
        self.add_attribute(
            "SentAcyclicFrames",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.frame_counters.acyclic_sent),
                description="I/O device, sent acyclic frames counter",
            ),
        )
        self.add_attribute(
            "LostAcyclicFrames",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.frame_counters.acyclic_lost),
                description="I/O device, lost acyclic frames counter",
            ),
        )
        self.add_attribute(
            "SlaveCount",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef(
                    "slave_count", update_period=STANDARD_POLL_UPDATE_PERIOD
                ),
                group=self.attr_group_name,
                initial_value=int(self.io.slave_count),
                description="I/O device registered slave count",
            ),
        )
        self.add_attribute(
            "SlavesStates",
            AttrR(
                datatype=Waveform(
                    array_dtype=np.uint8, shape=(2 * int(self.io.slave_count),)
                ),
                io_ref=CATioControllerAttributeIORef(
                    "slaves_states", update_period=STANDARD_POLL_UPDATE_PERIOD
                ),
                group=self.attr_group_name,
                initial_value=np.array(self.io.slaves_states, dtype=np.uint8).flatten(),
                description="I/O device, states of slave terminals",
            ),
        )
        self.add_attribute(
            "SlavesCrcCounters",
            AttrR(
                datatype=Waveform(
                    array_dtype=np.uint32, shape=(int(self.io.slave_count),)
                ),
                io_ref=CATioControllerAttributeIORef(
                    "slaves_crc_counters", update_period=STANDARD_POLL_UPDATE_PERIOD
                ),
                group=self.attr_group_name,
                initial_value=np.array(
                    self.io.slaves_crc_counters, dtype=np.uint32
                ).flatten(),
                description="I/O device, slave crc error sum counters",
            ),
        )
        self.add_attribute(
            "NodeCount",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("node_count", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.node_count),
                description="I/O device registered node count",
            ),
        )
        self.add_attribute(
            "timestamp",
            AttrR(
                datatype=String(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                description="I/O device last notification timestamp",
            ),
        )
        attr_count = len(self.attributes) - initial_attr_count
        logger.verbose(
            f"Created {attr_count} generic attributes "
            + f"for the controller {self.name}."
        )

    async def connect(self) -> None:
        """Establish the FastCS connection to the device controller."""
        await super().connect()

    def get_device_ecat_id(self) -> int:
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
        logger.info(
            f"EtherCAT Device {self.name}: subscribing to symbol notifications."
        )
        await self.connection.add_notifications(self.get_device_ecat_id())

    @scan(ONCE)
    async def subscribe(self) -> None:
        """Subscribe to all ads symbol notifications available to the controller.
        This is done once after post FastCS connection; \
            if done earlier, the notification setup process will somehow fail."""
        await self.setup_symbol_notifications()
        self.notification_ready = True
        logger.verbose("Setup of notification subscriptions completed.")

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
        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        await self.update_nparray_subattributes(attr_names, frame, np.uint32)


class CATioTerminalController(CATioController):
    """A controller for an EtherCAT I/O terminal."""

    def __init__(
        self,
        name: str,
        ecat_name: str = "",
        description: str | None = None,
        path: list[str] | None = None,
        group_layout: GroupLayout | None = None,
    ) -> None:
        super().__init__(
            name=name,
            ecat_name=ecat_name,
            description=description,
            group="terminal",
            path=path,
            group_layout=group_layout,
        )

    async def get_io_attributes(self) -> None:
        """Create and get all terminal controller attributes."""
        await self.get_terminal_generic_attributes()

    async def get_terminal_generic_attributes(self) -> None:
        """Create and get all generic terminal attributes."""
        assert isinstance(self.io, IOSlave), (
            f"Wrong I/O type associated with controller {self.name}"
        )

        # Get the generic attributes related to a CATioDeviceController
        initial_attr_count = len(self.attributes)
        await super().get_generic_attributes()

        self.add_attribute(
            "ParentDevId",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef(
                    "parent_device", update_period=ONCE
                ),
                group=self.attr_group_name,
                initial_value=str(self.io.parent_device),
                description="I/O terminal master device id",
            ),
        )
        self.add_attribute(
            "Type",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("type", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io.type,
                description="I/O terminal type",
            ),
        )
        self.add_attribute(
            "Name",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("name", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=self.io.name,
                description="I/O terminal name",
            ),
        )
        self.add_attribute(
            "Address",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("address", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.address),
                description="I/O terminal EtherCAT address",
            ),
        )
        self.add_attribute(
            "Identity",
            AttrR(
                datatype=String(),
                io_ref=CATioControllerAttributeIORef("identity", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=str(self.io.identity),
                description="I/O terminal identity",
            ),
        )
        self.add_attribute(
            "StateMachine",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.states.ecat_state),
                description="I/O terminal state machine",
            ),
        )
        self.add_attribute(
            "LinkStatus",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.states.link_status),
                description="I/O terminal communication state",
            ),
        )
        self.add_attribute(
            "CrcErrorPortA",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.crcs.port_a_crc),
                description="I/O terminal crc error counter on port A",
            ),
        )
        self.add_attribute(
            "CrcErrorPortB",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.crcs.port_b_crc),
                description="I/O terminal crc error counter on port B",
            ),
        )
        self.add_attribute(
            "CrcErrorPortC",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.crcs.port_c_crc),
                description="I/O terminal crc error counter on port C",
            ),
        )
        self.add_attribute(
            "CrcErrorPortD",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=int(self.io.crcs.port_d_crc),
                description="I/O terminal crc error counter on port D",
            ),
        )
        self.add_attribute(
            "CrcErrorSum",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef(
                    "crc_error_sum", update_period=STANDARD_POLL_UPDATE_PERIOD
                ),
                group=self.attr_group_name,
                initial_value=int(self.io.crc_error_sum),
                description="I/O terminal crc error sum counter",
            ),
        )
        self.add_attribute(
            "Node",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("node", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.loc_in_chain.node),
                description="I/O terminal associated node",
            ),
        )
        self.add_attribute(
            "Position",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerAttributeIORef("position", update_period=ONCE),
                group=self.attr_group_name,
                initial_value=int(self.io.loc_in_chain.position),
                description="I/O terminal associated position",
            ),
        )
        attr_count = len(self.attributes) - initial_attr_count
        logger.verbose(
            f"Created {attr_count} generic attributes "
            + f"for the controller {self.name}."
        )

    async def connect(self) -> None:
        """Establish the FastCS connection to the terminal controller."""
        await super().connect()

    @scan(STANDARD_POLL_UPDATE_PERIOD)
    async def states(self) -> None:
        """
        Periodically poll the EtherCAT terminal states from the io.
        """
        attr_names = [
            "StateMachine",
            "LinkStatus",
        ]
        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        await self.update_nparray_subattributes(attr_names, frame, np.uint8)

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
        frame = inspect.currentframe()
        assert frame is not None, "Function name couldn't be retrieved."
        await self.update_nparray_subattributes(attr_names, frame, np.uint32)
