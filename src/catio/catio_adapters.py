import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Self

import numpy as np
from fastcs.attributes import (
    ONCE,
    AttrHandlerR,
    AttrHandlerRW,
    AttrHandlerW,
    AttrR,
    _BaseAttrHandler,
)
from fastcs.controller import BaseController
from fastcs.datatypes import DataType


class CATioFastCSRequest:
    """Request object sent to the catio client (string subclass)."""

    def __init__(self, command: str, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
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
    attribute_name: str = ""
    """The name of the attribute which the handler is linked to"""
    kwargs: dict[str, Any] = field(default_factory=dict)
    """Additional parameters which may be useful to the handler"""

    @classmethod
    def create(cls, *args, **kwargs) -> Self:
        logging.debug(f"CATioParamHandler: args={args}, kwargs={kwargs}")
        return cls(*args, **kwargs)


@dataclass(kw_only=True)
class ReadOnceParamHandler(AttrHandlerR, CATioParamHandler):
    """Handler for FastCS attributes that are polled only once on startup."""

    update_period: float | None = ONCE

    async def update(self, attr: AttrR[Any]):
        # logging.debug(
        #     f"Read once handler has been called for {attr.group}, {attr.description}"
        # )
        value = attr.get()
        await attr.set(value)


@dataclass(kw_only=True)
class PollParamHandler(AttrHandlerR, CATioParamHandler):
    """Handler for FastCS attributes that are polled regularly."""

    update_period: float | None = 0.2
    first_poll: bool = True
    _controller: BaseController | None = None

    def __post_init__(self):
        if (update_period := self.kwargs.get("update_period", None)) is not None:
            self.update_period = update_period

    async def initialise(self, controller: BaseController):
        # logging.debug("PollParamHandler has been initialised.")
        self._controller = controller

    @property
    def controller(self) -> BaseController:
        if self._controller is None:
            raise RuntimeError(f"Handler {__name__} was not initialised.")
        return self._controller

    async def update(self, attr: AttrR) -> None:
        # Lazy import to avoid circular references
        from .catio_controller import CATioSubsystemController

        assert isinstance(self.controller, CATioSubsystemController)
        # logging.debug(
        #     f"Poll handler has been called for {attr.group} -> {self.attribute_name}."
        # )

        # Read the current attribute value.
        old_value = attr.get()
        # Update pv if first call after ioc start
        if self.first_poll:
            await attr.set(old_value)
            self.first_poll = False

        response = await self.controller.connection.send_query(
            CATioFastCSRequest(
                f"{self.controller.subsystem.upper()}_{self.attribute_name.upper()}_ATTR",
                attr_group=attr.group,
                **self.kwargs,
            )
        )

        if response is not None:
            if isinstance(response, np.ndarray):
                assert isinstance(old_value, np.ndarray)
                if not np.array_equal(response, old_value):
                    await attr.set(response)
                    logging.debug(
                        f"Waveform attribute '{self.attribute_name}' was updated."
                    )
            else:
                new_value = attr.dtype(response)
                if new_value != old_value:
                    await attr.set(new_value)
                    logging.debug(
                        f"Attribute '{self.attribute_name}' was updated to value {attr.get()}"
                    )

        else:
            # pass
            logging.debug(
                f"Attribute '{self.attribute_name}' current value {attr.get()}"
            )


@dataclass(kw_only=True)
class NotificationParamHandler(AttrHandlerR, CATioParamHandler):
    """"""

    update_period: float | None = 0.2

    async def update(self, attr: AttrR[Any]):
        pass


@dataclass
class CommandParamHandler(AttrHandlerW):
    """"""

    ...


@dataclass
class ReadWriteParamHandler(AttrHandlerRW):
    """"""

    ...


class CATioHandler(Enum):
    """Represent the available handler methods to process CATio FastCS attributes."""

    OnceAtStart = ReadOnceParamHandler
    PeriodicPoll = PollParamHandler
    FromNotification = NotificationParamHandler


class SubsystemParameter:
    """"""

    def __init__(
        self,
        subsystem_id: str,
        name: str,
        type: DataType,
        value: Any,
        access: Literal["r", "w", "rw"],
        description: str = "",
        handler: CATioHandler | None = None,
        **kwargs,  # used to define any variable which may be required by the handler definition or the attribute API
    ):
        self.subsystem_id = subsystem_id
        self.name = name
        self.type = type
        self.value = value
        self.access = access
        self.description = description
        self.handler = handler
        self.kwargs = kwargs


Subsystem = Literal["server", "device", "terminal"]


class CATioParameter(SubsystemParameter):
    """"""

    def __init__(self, *args, **kwargs):
        assert type(args[0]) is SubsystemParameter, (
            "CATioParameter instance must be defined from an existing SubsystemParameter object."
        )
        self.__dict__ = args[0].__dict__.copy()

        self.subsystem: Subsystem = kwargs["subsystem"]
        """Subsystem type within the CATio API."""
        self.group: str = kwargs["group"]
        """Subsystem group name within the CATio API"""
