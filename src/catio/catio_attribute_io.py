from dataclasses import KW_ONLY, dataclass
from typing import Any, TypeVar

import numpy as np
from fastcs.attribute_io import AttributeIO
from fastcs.attribute_io_ref import AttributeIORef
from fastcs.attributes import ONCE, AttrR
from fastcs.datatypes import Waveform
from fastcs.logging import bind_logger
from fastcs.tracer import Tracer

from catio.catio_connection import CATioConnection, CATioFastCSRequest

tracer = Tracer(name=__name__)
logger = bind_logger(logger_name=__name__)


AnyT = TypeVar("AnyT", str, int, float)


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

    #     async def send(
    #         self, attr: AttrW[NumberT, CATioControllerPollAttributeIORef],
    #         value: NumberT
    #     ) -> None:
    #         command = f"{attr.io_ref.name}{self.suffix}={attr.dtype(value)}"
    #         await self._connection.send_command(CATioFastCSRequest(f"{command}\r\n"))
    #         self.log_event("Send command for attribute", topic=attr, command=command)

    async def update(self, attr: AttrR[AnyT, CATioControllerAttributeIORef]) -> None:
        """Poll the attribute value and update it if it has changed."""

        logger.debug(f"Poll handler has been called for {attr.group} -> {attr.name}.")

        # Process initial startup poll (inc. unique update for invariant attributes)
        if (attr.io_ref.update_period is ONCE) or (self._value.get(attr.name) is None):
            self._value[attr.name] = attr.get()
            assert self._value[attr.name] is not None
            query = "INITIAL_STARTUP_POLL"
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
                # Handle numpy arrays (waveforms) separately
                if isinstance(response, np.ndarray):
                    assert isinstance(self._value[attr.name], np.ndarray)
                    if not np.array_equal(response, self._value[attr.name]):
                        self._value[attr.name] = attr.dtype(response)
                        await attr.update(self._value[attr.name])
                        logger.debug(f"Waveform attribute '{attr.name}' was updated.")
                    else:
                        logger.debug(
                            f"Current value of attribute '{attr.name}' is unchanged: "
                            + f"{self._value}"
                        )

                # Handle simple data types
                else:
                    new_value = attr.dtype(response)
                    if new_value != self._value:
                        self._value[attr.name] = new_value
                        await attr.update(self._value[attr.name])
                        logger.debug(
                            f"Attribute '{attr.name}' was updated to value {new_value}"
                        )
                    else:
                        logger.debug(
                            f"Current value of attribute '{attr.name}' is unchanged: "
                            + f"{self._value}"
                        )

            else:
                logger.debug(
                    f"No corresponding API method was found for command '{query}'"
                )

        self.log_event(
            "Query for attribute",
            topic=attr,
            query=query,
            response=self._value,
        )
