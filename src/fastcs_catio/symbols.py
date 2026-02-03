import re
import sys
from dataclasses import dataclass
from enum import Enum
from logging import getLogger

import numpy as np
import numpy.typing as npt

from ._constants import AdsDataType
from .devices import (
    ELM_OVERSAMPLING_FACTOR,
    OVERSAMPLING_FACTOR,
    AdsSymbol,
    AdsSymbolNode,
)
from .utils import add_comment

logger = getLogger(__name__)


@dataclass(kw_only=True)
class SymbolGroupParam:
    """
    Parameters for defining symbols within a structured AdsSymbolNode.
    """

    name: str
    """Name of the symbol within the structured node"""
    description: str
    """Description of the symbol within the structured node"""
    dtype: npt.DTypeLike
    """Data type of the symbol within the structured node"""
    offset_shift: int = 0
    """Offset shift of the symbol within the structured node"""
    size: int = 1
    """Size of the symbol within the structured node"""


class AdsSymbolTypePattern:
    BIT = re.compile(r"^BIT")
    """e.g. WcState and InputToggle, value common to all terminals on the bus"""
    ID = re.compile(r"^ID_TYPE")
    """e.g. EK1110 extension coupler id"""
    PWR12_STATUS = re.compile(r"^Status Uo_TYPE")
    """e.g. EL9512 power supply unit converter"""
    PWR24_STATUS = re.compile(r"^Status Us_TYPE")
    """e.g. EL9410 power supply terminal for E-bus"""
    DEV_INPUTS = re.compile(r"^Inputs_TYPE")
    """e.g. EtherCAT Master device inputs"""
    DEV_OUTPUTS = re.compile(r"^Outputs_TYPE")
    """e.g. EtherCAT Master device outputs"""
    DI_COUNTER = re.compile(r"^CNT Inputs_(\d*_)?TYPE")
    """e.g. EL1502 digital input counter terminal"""
    DO_COUNTER = re.compile(r"^CNT Outputs_(\d*_)?TYPE")
    """e.g. EL1502 digital output counter terminal"""
    DI_CHANNEL = re.compile(r"^Channel 1_(\d*_)?TYPE")
    """e.g. EL1014 digital input channel terminal"""
    AI16_CHANNEL = re.compile(r"^AI Standard Channel 1_(\d*_)?TYPE")
    """e.g. EL3104 16-bit analog input channel terminal"""
    AO16_CHANNEL = re.compile(r"^AO Output Channel 1_(\d*_)?TYPE")
    """e.g. EL4134 16-bit analog output channel terminal"""
    AI24_CHANNEL = re.compile(r"^AI Inputs Channel 1_(\d*_)?TYPE")
    """e.g. EL3602 24-bit analog input channel terminal"""
    AI16_OVSMPL_CYCLE = re.compile(r"^Ch(\d+) CycleCount_(\d*_)?TYPE")
    """e.g. EL3702 16-bit analog input oversampling terminal cycle count"""
    AI16_OVSMPL_CHANNEL = re.compile(r"^Ch(\d+) Sample 0_(\d*_)?TYPE_ARR")
    """e.g. EL3702 16-bit analog input oversampling terminal sample"""
    AI24_MF_STATUS = re.compile(r"^PAI Status Channel 1_(\d*_)?TYPE")
    """e.g. ELM3704-0000 24-bit multi-function analog input terminal status"""
    AI24_MF_TIMESTAMP = re.compile(r"^PAI Timestamp Channel 1_(\d*_)?TYPE")
    """e.g. ELM3704-0000 24-bit multi-function analog input terminal timing"""
    AI24_MF_SAMPLE = re.compile(r"^PAI Samples (\d+) Channel 1_(\d*_)?TYPE")
    """e.g. ELM3704-0000 24-bit multi-function analog input terminal sample"""
    AI24_MF_SYNCHRON = re.compile(
        r"^PAI Synchronous Oversampling Channel 1_(\d*_)?TYPE"
    )
    """e.g. ELM3704-0000 24-bit multi-function analog input terminal synchronisation"""


class ReMatchType(Enum):
    SEARCH = 0
    MATCH = 1
    FULLMATCH = 2


@dataclass
class RegexIn:
    """
    Enable structural pattern matching using regular expressions.
    """

    string: str
    """Input string to validate against a regex pattern"""
    fn_type: ReMatchType = ReMatchType.SEARCH
    """Type of regex function to use (i.e. search, match, fullmatch)"""
    match: re.Match[str] | None = None
    """Match object returned by the regex function call"""
    pos: int = 0
    """Index in the string where the search is to start"""
    endpos: int = sys.maxsize
    """Index in the string where the search is to stop"""

    def _match_pattern(self, pattern: re.Pattern):
        """
        Call the requested regex function to match a pattern in a string.

        :param pattern: the regex pattern to match

        :return: the result of the regex match
        """
        match self.fn_type:
            case ReMatchType.SEARCH:
                re_func = pattern.search
            case ReMatchType.MATCH:
                re_func = pattern.match
            case ReMatchType.FULLMATCH:
                re_func = pattern.fullmatch

        return re_func(self.string, self.pos, self.endpos)

    def __eq__(self, other: object):
        """
        Override the equality operator of the string class for evaluating a match.
        """
        if not (isinstance(other, str) or isinstance(other, re.Pattern)):
            return super().__eq__(other)

        if isinstance(other, str):
            other = re.compile(other)
        assert isinstance(other, re.Pattern)

        self.match = self._match_pattern(other)

        return self.match is not None

    def __hash__(self):
        return super().__hash__()

    def __getitem__(self, group: int):
        return self.match[group] if self.match else None


def symbol_lookup(node: AdsSymbolNode) -> dict[str, AdsSymbol]:
    """
    Get the symbol(s) associated with the AdsSymbolNode object.
    Lookup is implemented as a function of the symbol node type which will differ
    depending on the related I/O terminal.

    ! This LUT may need updating for functionality to expand to new I/O terminals.

    :return: a dictionary of AdsSymbol objects associated to this node
    """
    symbols: dict[str, AdsSymbol] = {}
    params: list[SymbolGroupParam] = []

    match node.ads_type:
        case AdsDataType.ADS_TYPE_BIT:
            # This will include most parameters for standard terminals:
            # e.g. EL1502, EL1004, EL9410, EL2024, EL1014, EL1084, EL3602, EL9512,
            # EL9505, EL1124, EL2124...
            params = [
                SymbolGroupParam(
                    name="",
                    dtype=np.uint8,
                    description="Value symbol for a 1 byte memory block "
                    "which includes distinct data on given bits.",
                ),
            ]

        case AdsDataType.ADS_TYPE_BIGTYPE:
            # This will be a structured data type which may comprise multiple symbols.
            # This will apply to few parameters for more complex terminals:
            # e.g. EK1101.ID, EL1502.CNT, EL9512.Status, EL9505.Status, EL3104.AI,
            # EL3602.AI, EL3702.Ch, ELM3704.PAI...

            match RegexIn(node.type_name):
                case AdsSymbolTypePattern.BIT:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint8,
                            description="Value symbol for a 1 byte memory block "
                            "which includes distinct data on given bits "
                            "as part of a combined type.",
                        ),
                    ]

                case AdsSymbolTypePattern.ID:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint16,
                            description="ID symbol for an extension coupler terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.PWR12_STATUS:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint8,
                            description="Power Status symbol "
                            "for a 12Vdc power supply unit terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.PWR24_STATUS:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint8,
                            description="Power Status symbol "
                            "for a 24Vdc power supply unit terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.DEV_INPUTS:
                    # !!! This will vary depending on the nb of used communication ports
                    # TO DO: REVIEW
                    params = [
                        SymbolGroupParam(
                            name="Frm0State",
                            dtype=np.uint16,
                            description="Input Frame status symbol "
                            "for the EtherCAT Master device.",
                        ),
                        SymbolGroupParam(
                            name="Frm0WcState",
                            dtype=np.uint16,
                            offset_shift=2,
                            description="Input Frame working counter status symbol "
                            "for the EtherCAT Master device.",
                        ),
                        SymbolGroupParam(
                            name="Frm0InputToggle",
                            dtype=np.uint16,
                            offset_shift=4,
                            description="Input Frame input toggle symbol "
                            "for the EtherCAT Master device.",
                        ),
                        SymbolGroupParam(
                            name="SlaveCount",
                            dtype=np.uint16,
                            offset_shift=10,
                            description="SlaveCount symbol for the EtherCAT "
                            "Master device.",
                        ),
                        SymbolGroupParam(
                            name="DevState",
                            dtype=np.uint16,
                            offset_shift=14,
                            description="Device Input Status symbol "
                            "for the EtherCAT Master device.",
                        ),
                    ]

                case AdsSymbolTypePattern.DEV_OUTPUTS:
                    # !!! This will vary depending on the nb of used communication ports
                    # TO DO: REVIEW
                    params = [
                        SymbolGroupParam(
                            name="Frm0Ctrl",
                            dtype=np.uint16,
                            description="Output Frame control symbol "
                            "for the EtherCAT Master device.",
                        ),
                        SymbolGroupParam(
                            name="Frm0WcCtrl",
                            dtype=np.uint16,
                            offset_shift=2,
                            description="Output Frame working counter control symbol "
                            "for the EtherCAT Master device.",
                        ),
                        SymbolGroupParam(
                            name="DevCtrl",
                            dtype=np.uint16,
                            offset_shift=4,
                            description="Device Output status symbol "
                            "for the EtherCAT Master device.",
                        ),
                    ]

                case AdsSymbolTypePattern.DI_COUNTER:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint16,
                            description="Status symbol "
                            "for a digital input counter terminal.",
                        ),
                        SymbolGroupParam(
                            name="Counter value",
                            dtype=np.uint32,
                            offset_shift=2,
                            description="Value symbol "
                            "for a digital input counter terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.DO_COUNTER:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint16,
                            description="Status symbol "
                            "for a digital output counter terminal.",
                        ),
                        SymbolGroupParam(
                            name="Set counter value",
                            dtype=np.uint32,
                            offset_shift=2,
                            description="Value symbol "
                            "for a digital output counter terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.DI_CHANNEL:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint8,
                            description="Value symbol "
                            "for a digital input channel terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI16_CHANNEL:
                    params = [
                        SymbolGroupParam(
                            name="Status",
                            dtype=np.uint16,
                            description="Status symbol "
                            "for a 16-bit analog input terminal.",
                        ),
                        SymbolGroupParam(
                            name="Value",
                            dtype=np.uint16,
                            offset_shift=2,
                            description="Value symbol "
                            "for a 16-bit analog input terminal channel.",
                        ),
                    ]

                case AdsSymbolTypePattern.AO16_CHANNEL:
                    params = [
                        SymbolGroupParam(
                            name="Analog output",
                            dtype=np.int16,
                            description="Value symbol "
                            "for a 16-bit analog output terminal channel.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI24_CHANNEL:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint16,
                            description="Status symbol "
                            "for a 24-bit analog input terminal.",
                        ),
                        SymbolGroupParam(
                            name="Value",
                            dtype=np.int32,
                            offset_shift=2,
                            description="Value symbol "
                            "for a 24-bit analog input terminal channel.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI16_OVSMPL_CYCLE:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.uint16,
                            description="CycleCount symbol "
                            "for a 16-bit analog input oversampling terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI16_OVSMPL_CHANNEL:
                    params = [
                        SymbolGroupParam(
                            name="",
                            dtype=np.int16,
                            size=OVERSAMPLING_FACTOR,
                            description="Sample symbol "
                            "for a 16-bit analog input oversampling terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI24_MF_STATUS:
                    params = [
                        SymbolGroupParam(
                            name="Status",
                            dtype=np.int32,
                            description="Status symbol "
                            "for a 24-bit multi-function analog input terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI24_MF_TIMESTAMP:
                    params = [
                        SymbolGroupParam(
                            name="StartTimeNextLatch",
                            dtype=np.uint32,
                            size=2,
                            description="Timing symbol "
                            "for a 24-bit multi-function analog input terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI24_MF_SAMPLE:
                    params = [
                        SymbolGroupParam(
                            name="Samples",
                            dtype=np.int32,
                            size=ELM_OVERSAMPLING_FACTOR,
                            description="Sample symbol "
                            "for a 24-bit multi-function analog input terminal.",
                        ),
                    ]

                case AdsSymbolTypePattern.AI24_MF_SYNCHRON:
                    params = [
                        SymbolGroupParam(
                            name="SM-Synchron",
                            dtype=np.uint16,
                            description="Synchronisation symbol "
                            "for a 24-bit multi-function analog input terminal.",
                        ),
                    ]

                case _:
                    logger.warning(
                        "Definition for the structured symbol node type "
                        + f"'{node.type_name}' in terminal {node.name} is missing. "
                        + "Symbol node will be ignored."
                    )

        case AdsDataType.ADS_TYPE_UINT8:
            """This will include some parameters for standard terminals:
            e.g. Status_Uo for EL9512, EL9505..."""
            params = [
                SymbolGroupParam(
                    name="",
                    dtype=np.uint8,
                    description="Value symbol for a 1 byte unsigned integer.",
                ),
            ]

        case _:
            logger.warning(
                f"Definition for the symbol node type '{node.ads_type}' in terminal "
                + f"{node.name} is missing. Symbol node will be ignored."
            )

    for var in params:
        node_name = ".".join([node.name, var.name]) if var.name else node.name
        symbols[node_name] = AdsSymbol(
            parent_id=node.parent_id,
            name=node_name,
            dtype=var.dtype,
            size=var.size,
            group=node.index_group,
            offset=int(node.index_offset) + var.offset_shift,
            comment=add_comment(var.description, node.comment),
        )

    return symbols
