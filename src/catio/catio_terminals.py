from abc import ABC, abstractmethod

from fastcs.datatypes import Int

from .catio_adapters import CATioHandler, SubsystemParameter
from .devices import NOTIF_UPDATE_POLL_PERIOD


class SupportedIO(ABC):
    @abstractmethod
    def get_params(self, name: str) -> list[SubsystemParameter]: ...

    # @abstractmethod
    def get_PV_name(self) -> str:
        ...
        # Update the initial ADCx name to something more accurate, e.g. AI1, DO4


class Device(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return [
            SubsystemParameter(
                name,
                "Inputs.Frm0State",
                Int(),
                0,
                "r",
                "I/O device input frame state value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "Outputs.Frm0Ctrl",
                Int(),
                0,
                "r",
                "I/O device output frame control value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
        ]


class EK1100(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EK1101(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EK1110(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL1004(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL1014(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return [
            SubsystemParameter(
                name,
                # "wc_state",
                "WcState",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 wcounter state value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                # "input_toggle",
                "InputToggle",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 input toggle value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "Channel1",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 channel#1 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "Channel2",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 channel#2 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "Channel3",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 channel#3 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "Channel4",
                Int(),
                0,
                "r",
                "I/O terminal EL1014 channel#4 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
        ]


class EL1124(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL1084(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL1502(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL2024(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL2024_0010(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL2124(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL3104(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL3602(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL3702(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL4134(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return [
            SubsystemParameter(
                name,
                "wc_state",
                Int(),
                0,
                "r",
                "I/O terminal EL4134 wcounter state value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                # "AOOutputChannel1.Analogoutput",
                "ao_channel1",
                Int(),
                0,
                "r",
                "I/O terminal EL4134 channel#1 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "ao_channel2",
                Int(),
                0,
                "r",
                "I/O terminal EL4134 channel#2 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "ao_channel3",
                Int(),
                0,
                "r",
                "I/O terminal EL4134 channel#3 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
            SubsystemParameter(
                name,
                "ao_channel4",
                Int(),
                0,
                "r",
                "I/O terminal EL4134 channel#4 value",
                handler=CATioHandler.FromNotification,
                update_period=NOTIF_UPDATE_POLL_PERIOD,
            ),
        ]


class EL9410(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL9505(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class EL9512(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


class ELM3704_0000(SupportedIO):
    def get_params(self, name: str) -> list[SubsystemParameter]:
        return []


SUPPORTED_TERMINALS: dict[str, SupportedIO] = {
    "EK1100": EK1100(),
    "EK1101": EK1101(),
    "EK1110": EK1110(),
    "EL1004": EL1004(),
    "EL1014": EL1014(),
    "EL1084": EL1084(),
    "EL1124": EL1124(),
    "EL1502": EL1502(),
    "EL2024": EL2024(),
    "EL2024_0010": EL2024_0010(),
    "EL2124": EL2124(),
    "EL3104": EL3104(),
    "EL3602": EL3602(),
    "EL3702": EL3702(),
    "EL4134": EL4134(),
    "EL9410": EL9410(),
    "EL9505": EL9505(),
    "EL9512": EL9512(),
    "ELM3704_0000": ELM3704_0000(),
}
