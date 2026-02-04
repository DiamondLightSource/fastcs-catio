from dataclasses import KW_ONLY, dataclass
from typing import Any, TypeVar

import numpy as np
from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrRW, AttrW
from fastcs.datatypes import DType_T, Waveform
from fastcs.logging import bind_logger
from fastcs.tracer import Tracer
from fastcs.util import ONCE

from fastcs_catio._types import AmsAddress
from fastcs_catio.catio_connection import CATioConnection, CATioFastCSRequest

tracer = Tracer(name=__name__)
logger = bind_logger(logger_name=__name__)


AnyT = TypeVar("AnyT", str, int, float)


async def compare_and_update_attribute_value(
    attr: AttrR[AnyT, AttributeIORef], value: Any, response: Any
) -> None:
    """
    Compare the current attribute value with the polled response; update if needed.

    :param attr: The attribute to be updated.
    :param value: The current value of the attribute.
    :param response: The polled response from the controller.
    """
    # Handle numpy arrays (waveforms) separately
    if isinstance(response, np.ndarray):
        assert isinstance(attr.datatype, Waveform)
        assert isinstance(value, np.ndarray)
        if not np.array_equal(response, value):
            value = response
            await attr.update(value)
            logger.debug(f"Waveform attribute '{attr.name}' was updated to {response}.")
        else:
            logger.debug(
                f"Current value of attribute '{attr.name}' is unchanged: {value}"
            )
    # Handle simple data types
    else:
        new_value = attr.dtype(response)
        if new_value != value:
            value = new_value
            await attr.update(value)
            logger.debug(f"Attribute '{attr.name}' was updated to value {new_value}")
        else:
            logger.debug(
                f"Current value of CoE attribute '{attr.name}' is unchanged: {value}"
            )


@dataclass
class CATioControllerAttributeIORef(AttributeIORef):
    """Reference to a CATio controller attribute IO."""

    name: str
    """Name of the attribute in the CATio API"""
    _: KW_ONLY  # Additional keyword-only arguments
    update_period: float | None = 0.2
    """Update period for the FastCS attribute"""


class CATioControllerAttributeIO(AttributeIO[AnyT, CATioControllerAttributeIORef]):
    """Attribute IO for CATio controller attributes."""

    def __init__(
        self,
        connection: CATioConnection,
        subsystem: str,
        controller_id: int,
    ):
        super().__init__()
        self._connection: CATioConnection = connection
        """Client connection to the CATio controller."""
        self.subsystem: str = subsystem
        """Subsystem name for the CATio controller."""
        self.controller_id: int = controller_id
        """Identifier for the CATio controller."""
        self._value: dict[str, Any] = {}
        """Cached value of the controller attributes."""

    # async def send(
    #     self,
    #     attr: AttrW[DType_T, CATioControllerAttributeIORef]
    #     | AttrRW[DType_T, CATioControllerAttributeIORef],
    #     value: DType_T,
    # ) -> None:
    #     """"""
    # logger.debug("Poll parameters are not expected to be writeable.")
    # pass

    async def update(self, attr: AttrR[AnyT, CATioControllerAttributeIORef]) -> None:
        """Poll the attribute value and update it if it has changed."""

        logger.debug(f"Poll handler has been called for {attr.group} -> {attr.name}.")

        # Process initial startup poll (inc. unique update for invariant attributes)
        if (attr.io_ref.update_period is ONCE) or (self._value.get(attr.name) is None):
            query = "INITIAL_STARTUP_POLL"
            self._value[attr.name] = attr.get()
            assert self._value[attr.name] is not None
            if isinstance(attr.datatype, Waveform):
                await attr.update(self._value[attr.name])
            else:
                await attr.update(attr.dtype(self._value[attr.name]))

        # Process regular polling attribute updates
        else:
            # Send a request to the controller to read the latest attribute value.
            attr_name = attr.io_ref.name.replace("_", "").upper()
            query = f"{self.subsystem.upper()}_{attr_name}_ATTR"
            response = await self._connection.send_query(
                CATioFastCSRequest(command=query, controller_id=self.controller_id)
            )

            # Update the attribute value if it has changed.
            if response is not None:
                await compare_and_update_attribute_value(
                    attr, self._value[attr.name], response
                )
            else:
                logger.debug(
                    f"No corresponding API method was found for command '{query}'"
                )

        self.log_event(
            "Get query for attribute",
            topic=attr,
            query=query,
            response=self._value,
        )


@dataclass
class CATioControllerSymbolAttributeIORef(AttributeIORef):
    """Reference to a CATio controller attribute IO."""

    name: str
    """Name of the attribute in the CATio API"""
    _: KW_ONLY  # Additional keyword-only arguments
    update_period: float | None = None
    """Update period for the FastCS attribute"""


class CATioControllerSymbolAttributeIO(
    AttributeIO[AnyT, CATioControllerSymbolAttributeIORef]
):
    """Attribute IO for CATio controller symbol attributes."""

    query = "SYMBOL_PARAM"

    def __init__(
        self,
        connection: CATioConnection,
        subsystem: str,
        controller_id: int,
        symbol_map: dict[str, str],
    ):
        super().__init__()
        self._connection: CATioConnection = connection
        """Client connection to the CATio controller."""
        self.subsystem: str = subsystem
        """Subsystem name for the CATio controller."""
        self.controller_id: int = controller_id
        """Identifier for the CATio controller."""
        self.symbol_map: dict[str, str] = symbol_map
        """Dictionary mapping CATio controller attribute names to ADS symbol names."""
        self._value: dict[str, Any] = {}
        """Cached value of the controller attributes."""

    async def send(
        self,
        attr: AttrW[DType_T, CATioControllerSymbolAttributeIORef]
        | AttrRW[DType_T, CATioControllerSymbolAttributeIORef],
        value: DType_T,
    ) -> None:
        """
        Send a value to the controller.

        :param attr: The attribute to send the value to.
        :param value: The value to send.
        """
        logger.debug(
            f"{self.subsystem}:: Symbol Write handler has been called for "
            f"{attr.group} -> {attr.name}."
        )
        symbol_name = self.symbol_map.get(attr.name, None)
        if symbol_name is not None:
            await self._connection.send_command(
                CATioFastCSRequest(
                    command=self.query,
                    controller_id=self.controller_id,
                    symbol_name=symbol_name,
                    dtype=attr.dtype,
                    value=value,
                )
            )
            self.log_event(
                "Set command for ADS Symbol attribute",
                topic=attr,
                query=self.query,
                new_value=value,
            )
            return

        logger.error(
            f"Attribute {attr.name} has no ADS symbol correspondance; "
            f"write operation failed."
        )

    async def update(
        self, attr: AttrR[AnyT, CATioControllerSymbolAttributeIORef]
    ) -> None:
        """
        Process initial startup poll of a single ADS Symbol attribute \
            and update its value.

        :param attr: The attribute to be updated.
        """
        pass


@dataclass
class CATioControllerCoEAttributeIORef(AttributeIORef):
    """Reference to a CATio controller CoE attribute IO."""

    name: str
    """Name of the attribute in the CATio API"""
    _: KW_ONLY  # Additional keyword-only arguments
    address: AmsAddress
    """Ams address of the controller for CoE communication"""
    index: str
    """Index of the CoE parameter associated with the attribute"""
    subindex: str
    """Subindex of the CoE parameter associated with the attribute"""
    dtype: np.dtype
    """Data type of the CoE parameter associated with the attribute"""
    update_period: float | None = ONCE
    """Update period for the FastCS attribute"""


class CATioControllerCoEAttributeIO(
    AttributeIO[AnyT, CATioControllerCoEAttributeIORef]
):
    """Attribute IO for CATio controller CANopen-over-EtherCAT (CoE) attributes."""

    query = "COE_PARAM"

    def __init__(
        self,
        connection: CATioConnection,
        subsystem: str,
    ):
        super().__init__()
        self._connection: CATioConnection = connection
        """Client connection to the CATio controller."""
        self.subsystem: str = subsystem
        """Subsystem name for the CATio controller."""
        self._value: dict[str, Any] = {}
        """Cached value of the controller attributes."""

    async def send(
        self,
        attr: AttrW[DType_T, CATioControllerCoEAttributeIORef]
        | AttrRW[DType_T, CATioControllerCoEAttributeIORef],
        value: DType_T,
    ) -> None:
        """
        Send a new value to the CoE attribute.

        :param attr: The attribute to send the value to.
        :param value: The value to send.
        """
        logger.debug(
            f"{self.subsystem}:: CoE Write handler has been called for "
            f"{attr.group} -> {attr.name}."
        )

        await self._connection.send_command(
            CATioFastCSRequest(
                command=self.query,
                address=attr.io_ref.address,
                index=attr.io_ref.index,
                subindex=attr.io_ref.subindex,
                dtype=attr.io_ref.dtype,
                value=value,
            )
        )

        if isinstance(attr, AttrRW):
            await attr.update(value)

        self.log_event(
            "Set command for CoE attribute",
            topic=attr,
            query=self.query,
            new_value=value,
        )

    async def initialise_attribute_value(
        self, attr: AttrR[AnyT, CATioControllerCoEAttributeIORef], response: Any
    ) -> None:
        """
        Initialise the attribute value at the start of the IOC.

        :param attr: The attribute to be initialised.
        :param response: The polled response from the controller.
        """
        try:
            if isinstance(response, np.ndarray):
                assert isinstance(attr.datatype, Waveform)
                self._value[attr.name] = response
            else:
                self._value[attr.name] = attr.dtype(response)
        except Exception as e:
            logger.warning(
                f"Error converting response for attribute '{attr.name}': {e}"
            )
            self._value[attr.name] = response
        await attr.update(self._value[attr.name])
        logger.debug(
            f"CoE attribute '{attr.name}' of type {attr.datatype} was initialised "
            f"to value {response}."
        )

    async def update(self, attr: AttrR[AnyT, CATioControllerCoEAttributeIORef]) -> None:
        """
        Poll the CoE attribute value and update it if it has changed.

        :param attr: The attribute to be updated.
        """
        logger.debug(
            f"{self.subsystem}:: CoE Read handler has been called for "
            f"{attr.group} -> {attr.name}."
        )

        # Get the current value of the CoE attribute
        response = await self._connection.send_query(
            CATioFastCSRequest(
                command=self.query,
                address=attr.io_ref.address,
                index=attr.io_ref.index,
                subindex=attr.io_ref.subindex,
                dtype=attr.io_ref.dtype,
            )
        )
        # Convert byte responses to string if required
        if attr.io_ref.dtype.kind == "S" and isinstance(response, bytes):
            response = response.decode("utf-8")

        logger.debug(f"Initial value of CoE parameter {attr.io_ref.name}: {response}")

        if response is not None:
            if self._value.get(attr.name) is None:
                # Initialise the attribute value at the start of the IOC.
                logger.debug(
                    f"CoE Attribute '{attr.name}' hasn't been initialised yet."
                )
                await self.initialise_attribute_value(attr, response)

            else:
                # Update the attribute value if it has changed.
                logger.debug(
                    f"Checking if value of CoE Attribute '{attr.name}' needs updating."
                )
                await compare_and_update_attribute_value(
                    attr, self._value[attr.name], response
                )

        self.log_event(
            "Get query for CoE attribute",
            topic=attr,
            query=self.query,
            response=self._value,
        )
