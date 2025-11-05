import logging
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import numpy as np

from ._constants import AdsDataType
from .devices import (
    ELM_OVERSAMPLING_FACTOR,
    OVERSAMPLING_FACTOR,
    AdsSymbol,
    AdsSymbolNode,
)
from .utils import add_comment


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


def symbol_lookup(node: AdsSymbolNode):
    """
    Get the symbol(s) associated with the AdsSymbolNode object.
    Lookup is implemented as a function of the symbol node type which will differ
    depending on the related I/O terminal.

    ! This LUT may need updating for functionality to expand to new I/O terminals.

    :return: a list of AdsSymbol objects associated to this node
    """
    symbols: Sequence[AdsSymbol] = []
    match node.ads_type:
        case AdsDataType.ADS_TYPE_BIT:
            # This will include most parameters for standard terminals:
            # e.g. EL1502, EL1004, EL9410, EL2024, EL1014, EL1084, EL3602, EL9512,
            # EL9505, EL1124, EL2124...
            symbols.append(
                AdsSymbol(
                    parent_id=node.parent_id,
                    name=node.name,
                    dtype=np.uint8,
                    size=1,
                    group=node.index_group,
                    offset=node.index_offset,
                    comment=add_comment(
                        "Value symbol for a 1 byte memory block which includes "
                        + "distinct data on given bits.",
                        node.comment,
                    ),
                )
            )
        case AdsDataType.ADS_TYPE_BIGTYPE:
            # This will be a structured data type which may comprise multiple symbols.
            # This will apply to few parameters for more complex terminals:
            # e.g. EK1101.ID, EL1502.CNT, EL9512.Status, EL9505.Status, EL3104.AI,
            # EL3602.AI, EL3702.Ch, ELM3704.PAI...

            match RegexIn(node.type_name):
                case AdsSymbolTypePattern.BIT:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint8,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Value symbol for a 1 byte memory block which includes "
                                + "distinct data on given bits.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.ID:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint16,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "ID symbol for an extension coupler terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.PWR12_STATUS:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint8,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Power Status symbol for a 12Vdc power supply unit "
                                + "terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.PWR24_STATUS:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint8,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Power Status symbol for a 24Vdc power supply unit "
                                + "terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.DEV_INPUTS:
                    # !!! This will vary depending on the nb of used communication ports
                    # TO DO: REVIEW
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Frm0State"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Input Frame status symbol for the EtherCAT "
                                    + "Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Frm0WcState"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Input Frame working counter status symbol for the "
                                    + "EtherCAT Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Frm0InputToggle"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 4,
                                comment=add_comment(
                                    "Input Frame input toggle symbol for the EtherCAT "
                                    + "Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "SlaveCount"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 10,
                                comment=add_comment(
                                    "SlaveCount symbol for the EtherCAT Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "DevState"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 14,
                                comment=add_comment(
                                    "Device Input Status symbol for the EtherCAT "
                                    + "Master device.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.DEV_OUTPUTS:
                    # !!! This will vary depending on the nb of used communication ports
                    # TO DO: REVIEW
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Frm0Ctrl"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Output Frame control symbol for the EtherCAT "
                                    + "Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Frm0WcCtrl"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Output Frame working counter control symbol for "
                                    + "the EtherCAT Master device.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "DevCtrl"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 4,
                                comment=add_comment(
                                    "Device Output status symbol for the EtherCAT "
                                    + "Master device.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.DI_COUNTER:
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=node.name,
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Status symbol for a digital input counter "
                                    + "terminal.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Counter value"]),
                                dtype=np.uint32,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Value symbol for a digital input counter "
                                    + "terminal.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.DO_COUNTER:
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=node.name,
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Status symbol for a digital output counter "
                                    + "terminal.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Set counter value"]),
                                dtype=np.uint32,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Value symbol for a digital output counter "
                                    + "terminal.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.DI_CHANNEL:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint8,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Value symbol for a digital input channel terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI16_CHANNEL:
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Status"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Status symbol for a 16-bit analog input terminal.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Value"]),
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Value symbol for a 16-bit analog input terminal "
                                    + "channel.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.AO16_CHANNEL:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=".".join([node.name, "Analog output"]),
                            dtype=np.int16,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Value symbol for a 16-bit analog output terminal "
                                + "channel.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI24_CHANNEL:
                    symbols.extend(
                        [
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=node.name,
                                dtype=np.uint16,
                                size=1,
                                group=node.index_group,
                                offset=node.index_offset,
                                comment=add_comment(
                                    "Status symbol for a 24-bit analog input terminal.",
                                    node.comment,
                                ),
                            ),
                            AdsSymbol(
                                parent_id=node.parent_id,
                                name=".".join([node.name, "Value"]),
                                dtype=np.int32,
                                size=1,
                                group=node.index_group,
                                offset=int(node.index_offset) + 2,
                                comment=add_comment(
                                    "Value symbol for a 24-bit analog input terminal "
                                    + "channel.",
                                    node.comment,
                                ),
                            ),
                        ]
                    )
                case AdsSymbolTypePattern.AI16_OVSMPL_CYCLE:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.uint16,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "CycleCount symbol for a 16-bit analog input "
                                + "oversampling terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI16_OVSMPL_CHANNEL:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=node.name,
                            dtype=np.int16,
                            size=OVERSAMPLING_FACTOR,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Sample symbol for a 16-bit analog input oversampling "
                                + "terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI24_MF_STATUS:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=".".join([node.name, "Status"]),
                            dtype=np.int32,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Status symbol for a 24-bit multi-function analog "
                                + "input terminal.",
                                node.comment,
                            ),
                        )
                    )

                case AdsSymbolTypePattern.AI24_MF_TIMESTAMP:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=".".join([node.name, "StartTimeNextLatch"]),
                            dtype=np.uint32,
                            size=2,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Timing symbol for a 24-bit multi-function analog "
                                + "input terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI24_MF_SAMPLE:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=".".join([node.name, "Samples"]),
                            dtype=np.int32,
                            size=ELM_OVERSAMPLING_FACTOR,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Sample symbol for a 24-bit multi-function analog "
                                + "input terminal.",
                                node.comment,
                            ),
                        )
                    )
                case AdsSymbolTypePattern.AI24_MF_SYNCHRON:
                    symbols.append(
                        AdsSymbol(
                            parent_id=node.parent_id,
                            name=".".join([node.name, "SM-Synchron"]),
                            dtype=np.uint16,
                            size=1,
                            group=node.index_group,
                            offset=node.index_offset,
                            comment=add_comment(
                                "Synchronisation symbol for a 24-bit multi-function "
                                + "analog input terminal.",
                                node.comment,
                            ),
                        )
                    )
                case _:
                    logging.warning(
                        "Definition for the structured symbol node type "
                        + f"'{node.type_name}' in terminal {node.name} is missing. "
                        + "Symbol node will be ignored."
                    )
        case _:
            logging.warning(
                f"Definition for the symbol node type '{node.ads_type}' in terminal "
                + f"{node.name} is missing. Symbol node will be ignored."
            )

    return symbols
