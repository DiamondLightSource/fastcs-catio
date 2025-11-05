import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Self

import numpy as np
from fastcs.attributes import (
    ONCE,
    AttrHandlerR,
    AttrR,
    _BaseAttrHandler,
)
from fastcs.controller import BaseController

Subsystem = Literal["server", "device", "terminal"]
"""Subsystem type within the CATio API."""


class CATioFastCSRequest:
    """Request object sent to the catio client (string subclass).
    Used to encapsulate all the information needed to perform a query.
    """

    def __init__(self, command: str, *args, **kwargs):
        self.command = command
        """The command to be executed by the CATio client."""
        self.args = args
        """Optional positional arguments for the command."""
        self.kwargs = kwargs
        """Optional keyword arguments for the command."""

    def __repr__(self) -> str:
        """Return a string representation of the CATio request."""
        return repr(
            self.command
            + "("
            + ", ".join(self.args)
            + ", "
            + ", ".join([f"{k}={v!r}" for k, v in self.kwargs.items()])
            + ")"
        )


@dataclass(kw_only=True)
class CATioParamHandler(_BaseAttrHandler):
    """Base class for CATio parameter handlers."""

    attribute_name: str = ""
    """The name of the attribute which the handler is linked to"""
    kwargs: dict[str, Any] = field(default_factory=dict)
    """Additional parameters which may be useful to the handler"""

    @classmethod
    def create(cls, *args, **kwargs) -> Self:
        """Factory method to create a new instance of the handler."""
        logging.debug(f"CATioParamHandler: args={args}, kwargs={kwargs}")
        return cls(*args, **kwargs)


@dataclass(kw_only=True)
class ReadOnceParamHandler(AttrHandlerR, CATioParamHandler):
    """
    Handler for FastCS attributes that are polled only once on startup.
    The attribute value is read once and then never updated again.
    """

    update_period: float | None = ONCE
    """Update period for the attribute (default: ONCE)."""

    async def update(self, attr: AttrR[Any]) -> None:
        """Read the attribute value once and set it."""
        value = attr.get()
        await attr.set(value)


@dataclass(kw_only=True)
class PollParamHandler(AttrHandlerR, CATioParamHandler):
    """
    Handler for FastCS attributes that are polled regularly.
    The attribute value is read periodically and updated if it has changed.
    """

    update_period: float | None = 0.2
    """Update period for the attribute (default: 0.2 seconds)."""
    first_poll: bool = True
    """Flag to indicate if this is the first poll after IOC start."""
    _controller: BaseController | None = None
    """Reference to the controller instance."""

    def __post_init__(self) -> None:
        """Post-initialization to set the update period from kwargs if provided."""
        if (update_period := self.kwargs.get("update_period", None)) is not None:
            self.update_period = update_period

    async def initialise(self, controller: BaseController) -> None:
        """Initialise the handler with a reference to the controller."""
        self._controller = controller

    @property
    def controller(self) -> BaseController:
        """
        Get the controller instance.

        raises RuntimeError if the controller has not been set.
        """
        if self._controller is None:
            raise RuntimeError(f"Handler {__name__} was not initialised.")
        return self._controller

    async def update(self, attr: AttrR) -> None:
        """Poll the attribute value and update if it has changed."""
        # Lazy import to avoid circular references
        from .catio_controller import CATioSubController

        assert isinstance(self.controller, CATioSubController)
        # logging.debug(
        #     f"Poll handler has been called for {attr.group} -> {self.attribute_name}."
        # )

        old_value = attr.get()
        assert old_value is not None

        # Update pv if first call after ioc start
        if self.first_poll:
            await attr.set(old_value)
            self.first_poll = False

        # Send a request to the controller to read the latest attribute value.
        response = await self.controller.connection.send_query(
            CATioFastCSRequest(
                f"{self.controller.subsystem.upper()}_{self.attribute_name.upper()}_ATTR",
                attr_group=self.controller.identifier,
                **self.kwargs,
            )
        )

        # Update the attribute value if it has changed.
        if response is not None:
            # Handle numpy arrays (waveforms) separately
            if isinstance(response, np.ndarray):
                assert isinstance(old_value, np.ndarray)
                if not np.array_equal(response, old_value):
                    await attr.set(response)
                    logging.debug(
                        f"Waveform attribute '{self.attribute_name}' was updated."
                    )

            # Handle simple data types
            else:
                new_value = attr.dtype(response)
                if new_value != old_value:
                    await attr.set(new_value)
                    logging.debug(
                        f"Attribute '{self.attribute_name}' was updated "
                        + f"to value {attr.get()}"
                    )

        else:
            logging.debug(
                f"Attribute '{self.attribute_name}' current value unchanged: "
                + f"{attr.get()}"
            )



class CATioHandler(Enum):
    """Represent the available handler methods to process CATio FastCS attributes."""

    OnceAtStart = ReadOnceParamHandler
    PeriodicPoll = PollParamHandler

