# =============================================================================
# ===== BECKHOFF VARIABLES -- Documentation References ========================
# =============================================================================

# WcState and InputToggle:
# https://infosys.beckhoff.com/english.php?content=../content/1033/b110_ethercat_optioninterface/1984417163.html&id=

# =============================================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from fastcs.attributes import Attribute, AttributeIORef, AttrR, AttrRW
from fastcs.datatypes import DataType, DType, Float, Int, String, Waveform
from fastcs.logging import bind_logger
from fastcs.tracer import Tracer

from fastcs_catio._types import AmsAddress
from fastcs_catio.catio_attribute_io import (
    CATioControllerSymbolAttributeIORef,
)
from fastcs_catio.catio_connection import CATioConnection
from fastcs_catio.catio_controller import (
    CATioDeviceController,
    CATioTerminalController,
)
from fastcs_catio.symbols import ELM_OVERSAMPLING_FACTOR, OVERSAMPLING_FACTOR
from fastcs_catio.utils import get_all_attributes

tracer = Tracer(name=__name__)
logger = bind_logger(logger_name=__name__)


# ============================================================================
# Data types mapping
# ============================================================================


def generic_dtype_to_fastcs_datatype(dtype: np.dtype) -> DataType:
    """
    Convert a generic NumPy dtype to the equivalent FastCS Attribute datatype.
    Maps NumPy dtype representations to FastCS datatype classes \
        (Float, Int, String, Waveform) used for creating FastCS attributes.

    :param dtype: NumPy dtype to convert

    :returns: FastCS datatype instance matching the NumPy dtype
    """
    if issubclass(dtype.type, np.generic):
        # Handle string types (fixed-length byte strings)
        if dtype.kind == "S":  # Byte string type
            return String(dtype.itemsize)

        # Handle boolean types
        if dtype == np.bool_:
            return Int()

        # Handle signed integer types
        signed_int_types = (
            np.int16,
            np.int32,
            np.int64,
            np.dtype("int16"),
            np.dtype("int32"),
            np.dtype("int64"),
        )
        if dtype in signed_int_types:
            return Int()

        # Handle unsigned integer types
        unsigned_int_types = (
            np.uint8,
            np.uint16,
            np.uint32,
            np.uint64,
            np.dtype("uint8"),
            np.dtype("uint16"),
            np.dtype("uint32"),
            np.dtype("uint64"),
        )
        if dtype in unsigned_int_types:
            return Int()

        # Handle floating point types
        float_types = (
            np.float32,
            np.float64,
            np.dtype("float32"),
            np.dtype("float64"),
        )
        if dtype in float_types:
            return Float()

    raise ValueError(
        f"Unsupported CoE parameter type: {dtype}. "
        f"Supported types are: int16, int32, int64, uint8, uint16, uint32, uint64, "
        f"float32, float64, bool, and byte strings (S*)"
    )


def coe_parameter_to_fastcs_datatype(coe_type: np.dtype) -> DataType:
    """
    Convert a CoEParameter type to the equivalent FastCS Attribute datatype.
    Maps NumPy dtype representations used in CoE parameters to FastCS
    datatype classes (Float, Int, String, Waveform) used for creating FastCS attributes.

    e.g.:   coe_type=np.dtype(np.int16) -> fastcstype=Int()
            coe_type=np.dtype((np.uint32, (5,))) -> fastcstype=Waveform(np.uint32, (5,))

    :param coe_type: the numpy dtype of the CoE parameter to convert

    :returns: FastCS datatype instance matching the CoE parameter type
    """
    # Process subdtype (e.g. arrays)
    if coe_type.subdtype is not None:
        dtype, shape = coe_type.subdtype
        return Waveform(dtype, shape)

    return generic_dtype_to_fastcs_datatype(coe_type)


# ============================================================================
# CoE parameter definitions
# ============================================================================


class CoEAccessMode(str, Enum):
    """CoE parameter access mode."""

    READ_ONLY = "read-only"
    """Read-only access mode"""
    READ_WRITE = "read/write"
    """Read and Write access mode"""


class CoEIndexGroup(str, Enum):
    """Device Parameter Indices (Hi-Word)."""

    DEVICE_TYPE_INDEX = "0x1000"
    """Device type identification"""
    DEVICE_NAME_INDEX = "0x1008"
    """Device name of the EtherCAT device"""
    HARDWARE_VERSION = "0x1009"
    """Hardware version of the EtherCAT device"""
    FIRMWARE_VERSION = "0x100A"
    """Firmware version of the EtherCAT device"""
    IDENTIFICATION_INDEX = "0x1018"
    """Information for identifying the EtherCAT device"""
    OPERATIONAL_SETTINGS_INDEX = "0x8000"
    """Base operational settings index"""
    INTERNAL_SETTINGS_INDEX = "0x800E"
    """Profile-specific internal settings index"""


class CoEIdentification(str, Enum):
    """Device Id Parameter CoE Sub-Indices (Lo-Word)."""

    VENDOR_ID_SUBINDEX = "0x0001"
    """Vendor identification"""
    PRODUCT_CODE_SUBINDEX = "0x0002"
    """Product code"""
    REVISION_NB_SUBINDEX = "0x0003"
    """Revision number"""
    SERIAL_NB_SUBINDEX = "0x0004"
    """Serial number"""


class CNTCoESettings(str, Enum):
    """Counter Device Operation Parameter CoE Sub-Indices (Lo-Word)."""

    ENABLE_SET_OUTPUT_SUBINDEX = "0x0001"
    """Enable function to set output"""
    ENABLE_RESET_OUTPUT_SUBINDEX = "0x0002"
    """Enable function to reset output"""
    ENABLE_RELOAD_SUBINDEX = "0x0003"
    """Enable reload"""
    COUNT_DOWN_SUBINDEX = "0x0004"
    """Counting direction"""
    ON_THRESHOLD_SUBINDEX = "0x0011"
    """Switch on threshold value"""
    OFF_THRESHOLD_SUBINDEX = "0x0012"
    """Switch off threshold value"""
    RELOAD_SUBINDEX = "0x0013"
    """Counter reload value"""


class AICoESettings(str, Enum):
    """Analog Input Device Operation Parameter CoE Sub-Indices (Lo-Word)."""

    ENABLE_USER_SCALE_SUBINDEX = "0x0001"
    """User scale is active"""
    ENABLE_FILTER_SUBINDEX = "0x0006"
    """Digital filter is active"""
    ENABLE_LIMIT_1_SUBINDEX = "0x0007"
    """First limit value is active"""
    ENABLE_LIMIT_2_SUBINDEX = "0x0008"
    """Second limit value is active"""
    USER_SCALE_OFFSET_SUBINDEX = "0x0011"
    """User scaling offset value"""
    USER_SCALE_GAIN_SUBINDEX = "0x0012"
    """User scaling gain value"""
    LIMIT_1_VALUE_SUBINDEX = "0x0013"
    """First limit value for setting the status bits"""
    LIMIT_2_VALUE_SUBINDEX = "0x0014"
    """Second limit value for setting the status bits"""
    FILTER_SETTINGS_SUBINDEX = "0x0015"
    """Digital filter selection"""
    MEASURING_RANGE_SUBINDEX = "0x0019"
    """Measuring range"""


class AOCoESettings(str, Enum):
    """Analog Output Device Operation Parameter CoE Sub-Indices (Lo-Word)."""

    ENABLE_USER_SCALE_SUBINDEX = "0x0001"
    """User scale is active"""
    WATCHDOG_SUBINDEX = "0x0005"
    """Watchdog safety setting"""
    USER_SCALE_OFFSET_SUBINDEX = "0x0011"
    """User scaling offset value"""
    USER_SCALE_GAIN_SUBINDEX = "0x0012"
    """User scaling gain value"""
    DEFAULT_OUTPUT_SUBINDEX = "0x0013"
    """Default value for the output safety value"""
    DEFAULT_RAMP_SUBINDEX = "0x0014"
    """Default ramp to reach the output safety value"""
    DAC_RAW_SUBINDEX = "0x0001"
    """(Internal) DAC raw value"""


class MultiFunctionCoESettings(str, Enum):
    """Multi Function Device Operation Parameter CoE Sub-Indices (Lo-Word)."""

    MEASUREMENT_CONFIG_SUBINDEX = "0x0001"
    """Measurement configuration"""

    # ... SO many more settings to implement! ...


@dataclass
class CoEIndex:
    """Index and Subindex for a CoE parameter."""

    hiword: str
    """High word of the index."""
    loword: str = "0x0000"
    """Low word of the index."""


@dataclass
class CoEParameter:
    """CANopen-over-EtherCAT (CoE) parameter definition."""

    alias: str
    """Alias name for the CoE parameter."""
    type: np.dtype
    """Data type of the CoE parameter."""
    index: CoEIndex
    """Index and Subindex of the CoE parameter."""
    access_mode: CoEAccessMode
    """Access mode: 'read-only' or 'read-write'."""
    description: str = ""
    """Description of the CoE parameter."""
    group: str = ""
    """Group name for categorizing the CoE parameter."""

    def create_fastcs_attribute(
        self,
        address: AmsAddress,
    ) -> AttrR[DType]:
        """
        Create a FastCS Attribute for the CoE parameter.

        :param address: AmsAddress of the target controller

        :returns: the created FastCS Attribute

        :raises: TypeError if the CoE parameter type is not a numpy data type
        """
        # Import currently required to prevent circular import
        # TO DO: change architecture to avoid this issue
        from fastcs_catio.catio_attribute_io import CATioControllerCoEAttributeIORef

        if isinstance(self.type, np.dtype):
            fcs_type = coe_parameter_to_fastcs_datatype(self.type)

            coe_reference: AttributeIORef = CATioControllerCoEAttributeIORef(
                self.alias,
                address=address,
                index=self.index.hiword,
                subindex=self.index.loword,
                dtype=self.type,
            )

            match self.access_mode:
                case CoEAccessMode.READ_ONLY:
                    return AttrR(
                        datatype=fcs_type,
                        io_ref=coe_reference,
                        group=re.sub(r"[_\s]", "", self.group),
                        initial_value=None,
                        description=self.description,
                    )
                case CoEAccessMode.READ_WRITE:
                    return AttrRW(
                        datatype=fcs_type,
                        io_ref=coe_reference,
                        group=self.group,
                        initial_value=None,
                        description=self.description,
                    )

        raise TypeError("CoE parameter must be a numpy data type object.")


@dataclass
class IdentificationCoEParameters:
    """
    Generic CANopen-over-EtherCAT (CoE) read-only parameters.
    """

    type = CoEParameter(
        alias="ID_TYPE",
        type=np.dtype(np.uint32),
        index=CoEIndex(CoEIndexGroup.DEVICE_TYPE_INDEX),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Device type identifier",
        group="Identification",
    )
    """Device type identifier"""
    name = CoEParameter(
        alias="ID_NAME",
        type=np.dtype("<S32"),
        index=CoEIndex(CoEIndexGroup.DEVICE_NAME_INDEX),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Device name",
        group="Identification",
    )
    """Device name"""
    v_hardware = CoEParameter(
        alias="ID_HARDWARE",
        type=np.dtype("<S16"),
        index=CoEIndex(CoEIndexGroup.HARDWARE_VERSION),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Hardware version",
        group="Identification",
    )
    """Hardware version"""
    v_firmware = CoEParameter(
        alias="ID_FIRMWARE",
        type=np.dtype("<S16"),
        index=CoEIndex(CoEIndexGroup.FIRMWARE_VERSION),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Firmware version",
        group="Identification",
    )
    """Firmware version"""
    vendor_id = CoEParameter(
        alias="ID_VENDOR",
        type=np.dtype(np.uint32),
        index=CoEIndex(
            CoEIndexGroup.IDENTIFICATION_INDEX, CoEIdentification.VENDOR_ID_SUBINDEX
        ),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Vendor identification",
        group="Identification",
    )
    """Vendor identification"""
    product_code = CoEParameter(
        alias="ID_PRODUCT",
        type=np.dtype(np.uint32),
        index=CoEIndex(
            CoEIndexGroup.IDENTIFICATION_INDEX, CoEIdentification.PRODUCT_CODE_SUBINDEX
        ),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Product code",
        group="Identification",
    )
    """Product code"""
    revision = CoEParameter(
        alias="ID_REVISION",
        type=np.dtype(np.uint32),
        index=CoEIndex(
            CoEIndexGroup.IDENTIFICATION_INDEX, CoEIdentification.REVISION_NB_SUBINDEX
        ),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Revision number",
        group="Identification",
    )
    """Revision number"""
    serial = CoEParameter(
        alias="ID_SERIAL",
        type=np.dtype(np.uint32),
        index=CoEIndex(
            CoEIndexGroup.IDENTIFICATION_INDEX, CoEIdentification.SERIAL_NB_SUBINDEX
        ),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Serial number",
        group="Identification",
    )
    """Serial number"""


class ChannelCoEParameters:
    """Generic channel CoE parameters."""

    def get_channel_number_and_index(
        self,
        channel: int,
        hiword: CoEIndexGroup = CoEIndexGroup.OPERATIONAL_SETTINGS_INDEX,
    ) -> tuple[int, str]:
        channel_id: int = channel + 1
        """The analog input channel number (not zero-indexed)."""
        channel_index = hex(int(hiword, 16) + int(f"0x{channel * 16:04x}", 16))
        """The CoE operational settings index for this channel """
        return channel_id, channel_index


class CNTChannelCoEParameters(ChannelCoEParameters):
    """Generic channel CoE parameters for a counter terminal."""

    def __init__(self, channel_nb: int) -> None:
        channel, index = self.get_channel_number_and_index(channel_nb)

        self.set_output_enabled = CoEParameter(
            alias=f"CNT{channel}_SET_STATE",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, CNTCoESettings.ENABLE_SET_OUTPUT_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Output settings enabled state",
            group=f"Channel{channel}",
        )
        """Activates the function for setting the Output"""
        self.reset_output_enabled = CoEParameter(
            alias=f"CNT{channel}_RESET_STATE",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, CNTCoESettings.ENABLE_RESET_OUTPUT_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Output reset enabled state",
            group=f"Channel{channel}",
        )
        """Activates the function for resetting the Output"""
        self.count_direction = CoEParameter(
            alias=f"CNT{channel}_COUNT_DIRECTION",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, CNTCoESettings.COUNT_DOWN_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Counting direction",
            group=f"Channel{channel}",
        )
        """Counting direction (up|down) of the counter"""
        self.on_threshold = CoEParameter(
            alias=f"CNT{channel}_ON_THRESHOLD",
            type=np.dtype(np.uint32),
            index=CoEIndex(index, CNTCoESettings.ON_THRESHOLD_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Switch on threshold value",
            group=f"Channel{channel}",
        )
        """Switch-on threshold value for the Output"""
        self.off_threshold = CoEParameter(
            alias=f"CNT{channel}_OFF_THRESHOLD",
            type=np.dtype(np.uint32),
            index=CoEIndex(index, CNTCoESettings.OFF_THRESHOLD_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Switch off threshold value",
            group=f"Channel{channel}",
        )
        """Switch-off threshold value for the Output"""
        self.reload_enabled = CoEParameter(
            alias=f"CNT{channel}_RELOAD_STATUS",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, CNTCoESettings.ENABLE_RELOAD_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Reload to value enabled state",
            group=f"Channel{channel}",
        )
        """The counter counts to the counter reload value"""
        self.reload_value = CoEParameter(
            alias=f"CNT{channel}_RELOAD_VALUE",
            type=np.dtype(np.int32),
            index=CoEIndex(index, CNTCoESettings.RELOAD_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Counter reload value",
            group=f"Channel{channel}",
        )
        """Limit to which the counter counts before resetting to zero"""


class AIChannelCoEParameters(ChannelCoEParameters):
    """
    Generic channel CoE parameters for an analog input terminal.

    Note that for some AI terminals, the filter frequencies are set for all channels \
        centrally via index 0x8000:15 (channel 1) [see EL3104/EL3602 datasheet].
    """

    def __init__(self, channel_nb: int) -> None:
        channel, index = self.get_channel_number_and_index(channel_nb)

        self.filter_enabled = CoEParameter(
            alias=f"AI{channel}_FILTER_STATE",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, AICoESettings.ENABLE_FILTER_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Digital filter enabled state",
            group=f"Channel{channel}",
        )
        """Digital filter enabled state"""
        self.filter_type = CoEParameter(
            alias=f"AI{channel}_FILTER_TYPE",
            type=np.dtype(np.uint16),
            index=CoEIndex(
                CoEIndexGroup.OPERATIONAL_SETTINGS_INDEX,
                AICoESettings.FILTER_SETTINGS_SUBINDEX,
            ),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Digital filter type",
            group=f"Channel{channel}",
        )
        """Digital filter type"""
        self.limit1_enabled = CoEParameter(
            alias=f"AI{channel}_LIMIT1_STATUS",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, AICoESettings.ENABLE_LIMIT_1_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="First limit enabled state",
            group=f"Channel{channel}",
        )
        """First limit enabled state"""
        self.limit1 = CoEParameter(
            alias=f"AI{channel}_LIMIT1_VALUE",
            type=np.dtype(np.int16),
            index=CoEIndex(index, AICoESettings.LIMIT_1_VALUE_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="First limit value",
            group=f"Channel{channel}",
        )
        """First limit value"""
        self.limit2_enabled = CoEParameter(
            alias=f"AI{channel}_LIMIT2_STATUS",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, AICoESettings.ENABLE_LIMIT_2_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Second limit enabled state",
            group=f"Channel{channel}",
        )
        """Second limit enabled state"""
        self.limit2 = CoEParameter(
            alias=f"AI{channel}_LIMIT2_VALUE",
            type=np.dtype(np.int16),
            index=CoEIndex(index, AICoESettings.LIMIT_2_VALUE_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Second limit value",
            group=f"Channel{channel}",
        )
        """Second limit value"""
        self.scale_enabled = CoEParameter(
            alias=f"AI{channel}_SCALE_STATUS",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, AICoESettings.ENABLE_USER_SCALE_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling enabled state",
            group=f"Channel{channel}",
        )
        """User scaling enabled state"""
        self.scale_gain = CoEParameter(
            alias=f"AI{channel}_SCALE_GAIN",
            type=np.dtype(np.int32),
            index=CoEIndex(index, AICoESettings.USER_SCALE_GAIN_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling gain value",
            group=f"Channel{channel}",
        )
        """User scaling gain value"""
        self.scale_offset = CoEParameter(
            alias=f"AI{channel}_SCALE_OFFSET",
            type=np.dtype(np.int16),
            index=CoEIndex(index, AICoESettings.USER_SCALE_OFFSET_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling offset value",
            group=f"Channel{channel}",
        )
        """User scaling offset value"""


class AOChannelCoEParameters(ChannelCoEParameters):
    """Generic channel CoE parameters for an analog output terminal."""

    def __init__(self, channel_nb: int) -> None:
        channel, index = self.get_channel_number_and_index(channel_nb)

        self.scale_enabled = CoEParameter(
            alias=f"AO{channel}_SCALE_STATUS",
            type=np.dtype(np.bool_),
            index=CoEIndex(index, AOCoESettings.ENABLE_USER_SCALE_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling enabled state",
            group=f"Channel{channel}",
        )
        """User scaling enabled state"""
        self.scale_gain = CoEParameter(
            alias=f"AO{channel}_SCALE_GAIN",
            type=np.dtype(np.int32),
            index=CoEIndex(index, AOCoESettings.USER_SCALE_GAIN_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling gain value",
            group=f"Channel{channel}",
        )
        """User scaling gain value"""
        self.scale_offset = CoEParameter(
            alias=f"AO{channel}_SCALE_OFFSET",
            type=np.dtype(np.int16),
            index=CoEIndex(index, AOCoESettings.USER_SCALE_OFFSET_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="User scaling offset value",
            group=f"Channel{channel}",
        )
        """User scaling offset value"""
        self.watchdog = CoEParameter(
            alias=f"AO{channel}_WATCHDOG",
            type=np.dtype(np.uint8),
            index=CoEIndex(index, AOCoESettings.WATCHDOG_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Watchdog safety mode",
            group=f"Channel{channel}",
        )
        """Watchdog settings"""
        self.default_output = CoEParameter(
            alias=f"AO{channel}_DEFAULT_OUTPUT",
            type=np.dtype(np.int16),
            index=CoEIndex(index, AOCoESettings.DEFAULT_OUTPUT_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Default output value",
            group=f"Channel{channel}",
        )
        """Default output value used by the watchdog"""
        self.default_ramp = CoEParameter(
            alias=f"AO{channel}_DEFAULT_RAMP",
            type=np.dtype(np.uint16),
            index=CoEIndex(index, AOCoESettings.DEFAULT_RAMP_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Default output ramp in digits/ms",
            group=f"Channel{channel}",
        )
        """Ramp used by the watchdog for moving to the default output value"""

        # Get CoE parameter from a different index group to default
        _, index = self.get_channel_number_and_index(
            channel_nb, CoEIndexGroup.INTERNAL_SETTINGS_INDEX
        )
        self.dac_raw = CoEParameter(
            alias=f"AO{channel}_DAC_RAW",
            type=np.dtype(np.uint16),
            index=CoEIndex(index, AOCoESettings.DAC_RAW_SUBINDEX),
            access_mode=CoEAccessMode.READ_ONLY,
            description="DAC raw value",
            group=f"Channel{channel}",
        )
        """DAC raw value for the channel output"""


class MultiFunctionChannelCoEParameters(ChannelCoEParameters):
    """Generic channel CoE parameters for a multi-function terminal."""

    def __init__(self, channel_nb: int) -> None:
        channel, index = self.get_channel_number_and_index(channel_nb)

        self.interface = CoEParameter(
            alias=f"MF{channel}_INTERFACE",
            type=np.dtype(np.uint16),
            index=CoEIndex(index, MultiFunctionCoESettings.MEASUREMENT_CONFIG_SUBINDEX),
            access_mode=CoEAccessMode.READ_WRITE,
            description="Measurement configuration",
            group=f"Channel{channel}",
        )
        """Select the measurement configuration (voltage, current...)"""

        # ... SO many more parameters to implement! ...


@dataclass
class CNTCoEParameters(IdentificationCoEParameters):
    """CoE parameters specific to an analog input terminal."""

    channel_params: list[CNTChannelCoEParameters] = field(default_factory=list)
    """List of analog input channel CoE parameters, one per channel."""

    def add_specific_channel_parameters(
        self, channel: int, index: str
    ) -> dict[str, CoEParameter] | None:
        """
        Add specific CoE parameters for the counter terminal channels.
        This method can be overridden in subclasses to add \
            terminal-specific channel parameters.

        :returns: A dictionary of added CoE parameters for the terminal channels or None
        """
        pass

    async def initialise(self, num_channels: int) -> list[CoEParameter]:
        """Initialize all CoE parameters for a counter terminal."""
        # Define standard CoE channel parameters for each available channel
        for n in range(num_channels):
            self.channel_params.append(CNTChannelCoEParameters(n))
        # Add extra CoE parameters for the counter channels (if required)
        for n, cnt_ch in enumerate(self.channel_params):
            channel, index = cnt_ch.get_channel_number_and_index(n)
            extras = self.add_specific_channel_parameters(channel, index)
            if extras is not None:
                for name, param in extras.items():
                    setattr(cnt_ch, name, param)
        # Get all attributes available from this class instance
        attr = get_all_attributes(self)

        # Get a list of all CoE parameters for this terminal
        coe_attr = list(filter(lambda x: type(x) is CoEParameter, attr))

        # Remove potential duplicates, i.e. digital filter type
        params: list[CoEParameter] = []
        for item in coe_attr:
            if item not in params:
                params.append(item)

        return params


@dataclass
class AICoEParameters(IdentificationCoEParameters):
    """CoE parameters specific to an analog input terminal."""

    channel_params: list[AIChannelCoEParameters] = field(default_factory=list)
    """List of analog input channel CoE parameters, one per channel."""

    def add_specific_channel_parameters(
        self, channel: int, index: str
    ) -> dict[str, CoEParameter] | None:
        """
        Add specific CoE parameters for the analog input terminal channels.
        This method can be overridden in subclasses to add \
            terminal-specific channel parameters.

        :returns: A dictionary of added CoE parameters for the terminal channels or None
        """
        pass

    async def initialise(self, num_channels: int) -> list[CoEParameter]:
        """Initialize all CoE parameters for an analog input terminal."""
        # Define standard CoE channel parameters for each available channel
        for n in range(num_channels):
            self.channel_params.append(AIChannelCoEParameters(n))
        # Add extra CoE parameters for the analog channels (if required)
        for n, ai_ch in enumerate(self.channel_params):
            channel, index = ai_ch.get_channel_number_and_index(n)
            extras = self.add_specific_channel_parameters(channel, index)
            if extras is not None:
                for name, param in extras.items():
                    setattr(ai_ch, name, param)
        # Get all attributes available from this class instance
        attr = get_all_attributes(self)

        # Get a list of all CoE parameters for this terminal
        coe_attr = list(filter(lambda x: type(x) is CoEParameter, attr))

        # Remove potential duplicates, i.e. digital filter type
        params: list[CoEParameter] = []
        for item in coe_attr:
            if item not in params:
                params.append(item)

        return params


@dataclass
class AOCoEParameters(IdentificationCoEParameters):
    """CoE parameters specific to an analog output terminal."""

    channel_params: list[AOChannelCoEParameters] = field(default_factory=list)
    """List of analog output channel CoE parameters, one per channel."""

    def add_specific_channel_parameters(
        self, channel: int, index: str
    ) -> dict[str, CoEParameter] | None:
        """
        Add specific CoE parameters for the analog output terminal channels.
        This method can be overridden in subclasses to add \
            terminal-specific channel parameters.

        :returns: A dictionary of added CoE parameters for the terminal channels or None
        """
        pass

    async def initialise(self, num_channels: int) -> list[CoEParameter]:
        """Initialize all CoE parameters for an analog output terminal."""
        # Define standard CoE channel parameters for each available channel
        for n in range(num_channels):
            self.channel_params.append(AOChannelCoEParameters(n))
        # Add extra CoE parameters for the analog channels (if required)
        for n, ao_ch in enumerate(self.channel_params):
            channel, index = ao_ch.get_channel_number_and_index(n)
            extras = self.add_specific_channel_parameters(channel, index)
            if extras is not None:
                for name, param in extras.items():
                    setattr(ao_ch, name, param)
        # Get all attributes available from this class instance
        attr = get_all_attributes(self)

        # Get a list of all CoE parameters for this terminal
        coe_attr = list(filter(lambda x: type(x) is CoEParameter, attr))

        # Remove potential duplicates, i.e. digital filter type
        params: list[CoEParameter] = []
        for item in coe_attr:
            if item not in params:
                params.append(item)

        return params


@dataclass
class MultiFunctionCoEParameters(IdentificationCoEParameters):
    """CoE parameters specific to a multi-function terminal."""

    channel_params: list[MultiFunctionChannelCoEParameters] = field(
        default_factory=list
    )
    """List of multi-function channel CoE parameters, one per channel."""

    def add_specific_channel_parameters(
        self, channel: int, index: str
    ) -> dict[str, CoEParameter] | None:
        """
        Add specific CoE parameters for the multi-function terminal channels.
        This method can be overridden in subclasses to add \
            terminal-specific channel parameters.

        :returns: A dictionary of added CoE parameters for the terminal channels or None
        """
        pass

    async def initialise(self, num_channels: int) -> list[CoEParameter]:
        """Initialize all CoE parameters for a multi-function terminal."""
        # Define standard CoE channel parameters for each available channel
        for n in range(num_channels):
            self.channel_params.append(MultiFunctionChannelCoEParameters(n))
        # Add extra CoE parameters for the analog channels (if required)
        for n, ao_ch in enumerate(self.channel_params):
            channel, index = ao_ch.get_channel_number_and_index(n)
            extras = self.add_specific_channel_parameters(channel, index)
            if extras is not None:
                for name, param in extras.items():
                    setattr(ao_ch, name, param)
        # Get all attributes available from this class instance
        attr = get_all_attributes(self)

        # Get a list of all CoE parameters for this terminal
        coe_attr = list(filter(lambda x: type(x) is CoEParameter, attr))

        # Remove potential duplicates, i.e. digital filter type
        params: list[CoEParameter] = []
        for item in coe_attr:
            if item not in params:
                params.append(item)

        return params


@dataclass
class CoEManager:
    """Generic Manager class for EtherCAT slave CoE operations"""

    def __init__(
        self,
        connection: CATioConnection,
        ams_address: AmsAddress,
        parameters: CNTCoEParameters
        | AICoEParameters
        | AOCoEParameters
        | MultiFunctionCoEParameters,
        name: str = "",
    ):
        """"""
        self._connection = connection
        """CATio connection to the device."""
        self._ams_address = ams_address
        """AmsAddress of the target device for CoE communication."""
        self._parameters = parameters
        """Parameter definition for the terminal type associated with this manager."""
        self._name: str = name
        """Name of the terminal device."""
        self.coe_params: list[CoEParameter] = []
        logger.debug(
            f"Initialized {self.__class__.__name__} for {self._name} "
            f"at AMS address {self._ams_address}"
        )

    async def read_io_configuration(self, num_channels: int = 1):
        """
        Read the I/O device configuration for all channels.

        :param num_channels: Number of channels to read the configuration for

        :return: I/O device configuration
        """
        self.coe_params = await self._parameters.initialise(num_channels)

    async def get_io_attributes(self) -> dict[str, Attribute]:
        """
        Get the I/O attributes for the device configuration.
        The configuration is defined by the CoE parameters.

        :returns: Dictionary of attribute name to Attribute instance
        """

        d: dict[str, Attribute] = {}
        for param in self.coe_params:
            # Create a fastCS attribute for each CoE parameter
            # (parameter name must be adjusted to match fastCS attribute name specs)
            name = re.sub(r"[_\s]", "", param.alias)
            d[name] = param.create_fastcs_attribute(self._ams_address)
        logger.debug(f"Found {len(d)} attributes for the CoE parameters: {d}")

        return d


@dataclass
class EtherCATMasterCoEParameters(AICoEParameters):
    """CoE parameters specific to the EtherCAT Master Device."""

    ...


class EtherCATMasterCoEManager(CoEManager):
    """Manager for EtherCAT Master Device CoE operations."""

    ...


@dataclass
class EL1502CoEParameters(CNTCoEParameters):
    """CoE parameters specific to the EL1502 terminal."""

    ...


class EL1502CoEManager(CoEManager):
    """Manager for EL1502 digital input terminal CoE operations."""

    ...


@dataclass
class EL3104CoEParameters(AICoEParameters):
    """CoE parameters specific to the EL3104 terminal."""

    ...


class EL3104CoEManager(CoEManager):
    """Manager for EL3104 analog input terminal CoE operations."""

    ...


@dataclass
class EL3602CoEParameters(AICoEParameters):
    """CoE parameters specific to the EL3104 terminal."""

    # Declare any terminal-specific parameters here, e.g.
    test_param = CoEParameter(
        alias="TEST1_ADDITION",
        type=np.dtype(np.uint8),
        index=CoEIndex("0x10F0", "0x0000"),
        access_mode=CoEAccessMode.READ_ONLY,
        description="Extra Terminal Test param",
        group="Identification",
    )

    def add_specific_channel_parameters(
        self, channel: int, index: str
    ) -> dict[str, CoEParameter] | None:
        # EL3602 terminal has measuring range parameter and different datatypes!
        return {
            "measuring_range": CoEParameter(
                alias=f"AI{channel}_RANGE",
                type=np.dtype(np.uint16),
                index=CoEIndex(index, AICoESettings.MEASURING_RANGE_SUBINDEX),
                access_mode=CoEAccessMode.READ_WRITE,
                description="Measuring range selection",
                group=f"Channel{channel}",
            ),
            "limit1": CoEParameter(
                alias=f"AI{channel}_LIMIT1_VALUE",
                type=np.dtype(np.int32),
                index=CoEIndex(index, AICoESettings.LIMIT_1_VALUE_SUBINDEX),
                access_mode=CoEAccessMode.READ_WRITE,
                description="First limit value",
                group=f"Channel{channel}",
            ),
            "limit2": CoEParameter(
                alias=f"AI{channel}_LIMIT2_VALUE",
                type=np.dtype(np.int32),
                index=CoEIndex(index, AICoESettings.LIMIT_2_VALUE_SUBINDEX),
                access_mode=CoEAccessMode.READ_WRITE,
                description="Second limit value",
                group=f"Channel{channel}",
            ),
            "scale_offset": CoEParameter(
                alias=f"AI{channel}_SCALE_OFFSET",
                type=np.dtype(np.int32),
                index=CoEIndex(index, AICoESettings.USER_SCALE_OFFSET_SUBINDEX),
                access_mode=CoEAccessMode.READ_WRITE,
                description="User scaling offset value",
                group=f"Channel{channel}",
            ),
        }


class EL3602CoEManager(CoEManager):
    """Manager for EL3602 analog input terminal CoE operations."""

    ...


@dataclass
class EL4134CoEParameters(AOCoEParameters):
    """CoE parameters specific to the EL4134 terminal."""

    ...


class EL4134CoEManager(CoEManager):
    """Manager for EL4134 analog output terminal CoE operations."""

    ...


@dataclass
class ELM3704CoEParameters(MultiFunctionCoEParameters):
    """CoE parameters specific to the ELM3704 multi-function terminal."""

    ...


class ELM3704CoEManager(CoEManager):
    """Manager for ELM3704 analog input multi-function terminal CoE operations."""

    ...


# ============================================================================
# Classes specific to the defined I/O devices/terminals
# ============================================================================


class EtherCATMasterController(CATioDeviceController):
    """A sub-controller for an EtherCAT Master I/O device."""

    io_function: str = "EtherCAT Master Device"
    """Function description of the I/O controller."""

    # Depending on number of notification streams, we'll have more attr!!!
    # e.g. 3 streams -> Frm0State, Frm1State, Frm2State
    # This depends on the size of the notif system. For now, just implement Frm0*
    num_ads_streams: int = 1
    """Number of ADS streams currently implemented for specific parameters."""

    coe_manager: EtherCATMasterCoEManager | None = None
    """Manager instance which controls the Master device CoE parameters."""

    # Also from TwinCAT, it should be:
    # attr_dict["Inputs.Frm0State"] = AttrR(...)
    # but '.' is not allowed in fastCS attribute name -> error
    # name string should match pattern '^([A-Z][a-z0-9]*)*$'
    # so we map it as aliases in self.ads_name_map below

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the EtherCAT Master device."""
        # Not Implemented (but could be: it has CoE wich is already used in the client)
        pass
        """Read the configuration of the EL1004 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = EtherCATMasterCoEManager(
                connection, ams_address, EtherCATMasterCoEParameters(), self.ecat_name
            )
        await self.coe_manager.read_io_configuration(0)

    async def get_io_attributes(self) -> None:
        """
        Get and create all Master Device attributes.
        """
        # Get the generic CATio device controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of device
        self.add_attribute(
            "InputsSlaveCount",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("inputs_slave_count"),
                group=self.attr_group_name,
                initial_value=None,
                description="Number of slaves reached in last cycle",
            ),
        )
        self.add_attribute(
            "InputsDevState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("inputs_device_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="EtherCAT device input cycle frame status",
            ),
        )
        self.add_attribute(
            "OutputsDevCtrl",
            AttrRW(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("outputs_device_control"),
                group=self.attr_group_name,
                initial_value=None,
                description="EtherCAT device output control value",
            ),
        )
        for i in range(0, self.num_ads_streams):
            self.add_attribute(
                f"InFrm{i}State",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(
                        f"inputs_frame{i}_status"
                    ),
                    group=self.attr_group_name,
                    initial_value=None,
                    description="Cyclic Ethernet input frame status",
                ),
            )
            self.add_attribute(
                f"InFrm{i}WcState",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(
                        f"inputs_frame{i}_wcounter"
                    ),
                    group=self.attr_group_name,
                    initial_value=None,
                    description="Inputs accumulated working counter",
                ),
            )
            self.add_attribute(
                f"InFrm{i}InpToggle",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(
                        f"inputs_frame{i}_update"
                    ),
                    group=self.attr_group_name,
                    initial_value=None,
                    description="EtherCAT cyclic frame update indicator",
                ),
            )
            self.add_attribute(
                f"OutFrm{i}Ctrl",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(
                        f"outputs_frame{i}_control"
                    ),
                    group=self.attr_group_name,
                    initial_value=None,
                    description="EtherCAT output frame control value",
                ),
            )
            self.add_attribute(
                f"OutFrm{i}WcCtrl",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(
                        f"outputs_frame{i}_wcounter"
                    ),
                    group=self.attr_group_name,
                    initial_value=None,
                    description="Outputs accumulated working counter",
                ),
            )

            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"InFrm{i}State"] = f"Inputs.Frm{i}State"
            self.ads_name_map[f"InFrm{i}WcState"] = f"Inputs.Frm{i}WcState"
            self.ads_name_map[f"InFrm{i}InpToggle"] = f"Inputs.Frm{i}InputToggle"
            self.ads_name_map[f"OutFrm{i}Ctrl"] = f"Outputs.Frm{i}Ctrl"
            self.ads_name_map[f"OutFrm{i}WcCtrl"] = f"Outputs.Frm{i}WcCtrl"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["InputsSlaveCount"] = "Inputs.SlaveCount"
        self.ads_name_map["InputsDevState"] = "Inputs.DevState"
        self.ads_name_map["OutputsDevCtrl"] = "Outputs.DevCtrl"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EK1100Controller(CATioTerminalController):
    """A sub-controller for an EK1100 EtherCAT Coupler terminal."""

    io_function: str = "EtherCAT coupler at the head of a segment"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all coupler terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        # n/a


class EK1101Controller(CATioTerminalController):
    """A sub-controller for an EK1101 EtherCAT Coupler terminal."""

    io_function: str = "EtherCAT coupler with three ID switches for variable topologies"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all coupler terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "ID",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("ID"),
                group=self.attr_group_name,
                initial_value=None,
                description="Unique ID for the group of components",
            ),
        )

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["ID"] = "ID"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EK1110Controller(CATioTerminalController):
    """A sub-controller for an EK1110 EtherCAT Extension terminal."""

    io_function: str = "EtherCAT extension coupler for line topology"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all coupler terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        # n/a

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1004Controller(CATioTerminalController):
    """A sub-controller for an EL1004 EtherCAT digital input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 3ms filter"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital input channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL1004 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1014Controller(CATioTerminalController):
    """A sub-controller for an EL1014 EtherCAT wcounter input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 10us filter"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital input channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL1014 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1124Controller(CATioTerminalController):
    """A sub-controller for an EL1124 EtherCAT digital input terminal."""

    io_function: str = "4-channel digital input, 5V DC, 0.05us filter"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital input channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL1124 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1084Controller(CATioTerminalController):
    """A sub-controller for an EL1084 EtherCAT digital input terminal."""

    io_function: str = "4-channel digital input, 24V DC, 3ms filter, GND switching"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital input channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL1084 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1502Controller(CATioTerminalController):
    """A sub-controller for an EL1502 EtherCAT digital input terminal."""

    io_function: str = "2-channel digital input, counter, 24V DC, 100kHz"
    """Function description of the I/O controller."""
    num_channels = 2
    """Number of digital input channels."""
    coe_manager: EL1502CoEManager | None = None
    """Manager instance which controls the terminal CoE parameters."""

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the EL1502 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = EL1502CoEManager(
                connection, ams_address, EL1502CoEParameters(), self.ecat_name
            )
        assert 1 <= self.num_channels <= 2, (
            f"{self.ecat_name} has a maximum of 2 DI channels; "
            f"got a configuration request for {self.num_channels} channels."
        )
        await self.coe_manager.read_io_configuration(self.num_channels)

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL1502 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )
        self.add_attribute(
            "CNTInputStatus",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_counter_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="Input channel counter status",
            ),
        )
        self.add_attribute(
            "CNTInputValue",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_counter_value"),
                group=self.attr_group_name,
                initial_value=None,
                description="Input channel counter value",
            ),
        )
        self.add_attribute(
            "CNTOutputStatus",
            AttrRW(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("output_counter_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="Output channel counter status",
            ),
        )
        self.add_attribute(
            "CNTOutputValue",
            AttrRW(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("output_counter_value"),
                group=self.attr_group_name,
                initial_value=None,
                description="Output channel counter set value",
            ),
        )
        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"
        self.ads_name_map["CNTInputStatus"] = "CNT Inputs.Status"
        self.ads_name_map["CNTInputValue"] = "CNT Inputs.Counter value"
        self.ads_name_map["CNTOutputStatus"] = "CNT Outputs.Control"
        self.ads_name_map["CNTOutputValue"] = "CNT Outputs.Set counter value"

        # Get the attributes for the available CoE parameters
        assert self.coe_manager is not None
        coe_attributes = await self.coe_manager.get_io_attributes()
        if coe_attributes:
            for name, attr in coe_attributes.items():
                self.add_attribute(name, attr)

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL2024Controller(CATioTerminalController):
    """A sub-controller for an EL2024 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 24V DC, 2A"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital output channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL2024 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL2024v0010Controller(CATioTerminalController):
    """A sub-controller for an EL2024-0010 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 12V DC, 2A"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital output channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL2024-0010 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL2124Controller(CATioTerminalController):
    """A sub-controller for an EL2124 EtherCAT digital output terminal."""

    io_function: str = "4-channel digital output, 5V DC, 20mA"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of digital output channels."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL2124 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel {i}"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL3104Controller(CATioTerminalController):
    """A sub-controller for an EL3104 EtherCAT analog input terminal."""

    io_function: str = "4-channel analog input, +/-10V, 16-bit, differential"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of analog input channels."""
    coe_manager: EL3104CoEManager | None = None
    """Manager instance which controls the terminal CoE parameters."""

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the EL3104 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = EL3104CoEManager(
                connection, ams_address, EL3104CoEParameters(), self.ecat_name
            )
        assert 1 <= self.num_channels <= 4, (
            f"{self.ecat_name} has a maximum of 4 AI channels; "
            f"got a configuration request for {self.num_channels} channels."
        )
        await self.coe_manager.read_io_configuration(self.num_channels)

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL3104 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated analog value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_status"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} voltage status",
                ),
            )
            self.add_attribute(
                f"AICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} analog input value",
                ),
            )
            # Map the FastCS channel attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AI Standard Channel {i}.Status"
            self.ads_name_map[f"AICh{i}Value"] = f"AI Standard Channel {i}.Value"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        # Get the attributes for the available CoE parameters
        assert self.coe_manager is not None
        coe_attributes = await self.coe_manager.get_io_attributes()
        if coe_attributes:
            for name, attr in coe_attributes.items():
                self.add_attribute(name, attr)
        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL3602Controller(CATioTerminalController):
    """A sub-controller for an EL3602 EtherCAT analog input terminal."""

    io_function: str = "2-channel analog input, up to +/-10V, 24-bit, high-precision"
    """Function description of the I/O controller."""
    num_channels: int = 2
    """Number of analog input channels."""
    coe_manager: EL3602CoEManager | None = None
    """Manager instance which controls the terminal CoE parameters."""

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the EL3602 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = EL3602CoEManager(
                connection, ams_address, EL3602CoEParameters(), self.ecat_name
            )
        assert 1 <= self.num_channels <= 2, (
            f"{self.ecat_name} has a maximum of 2 AI channels; "
            f"got a configuration request for {self.num_channels} channels."
        )
        await self.coe_manager.read_io_configuration(self.num_channels)

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL3602 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated analog value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_status"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} voltage status",
                ),
            )
            self.add_attribute(
                f"AICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} analog input value",
                ),
            )
            # Map the FastCS channel attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AI Inputs Channel {i}"
            self.ads_name_map[f"AICh{i}Value"] = f"AI Inputs Channel {i}.Value"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        # Get the attributes for the available CoE parameters
        assert self.coe_manager is not None
        coe_attributes = await self.coe_manager.get_io_attributes()
        if coe_attributes:
            for name, attr in coe_attributes.items():
                self.add_attribute(name, attr)

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL3702Controller(CATioTerminalController):
    """A sub-controller for an EL3702 EtherCAT analog input terminal."""

    io_function: str = "2-channel analog input, +/-10V, 16-bit, oversampling"
    """Function description of the I/O controller."""

    # TO DO: Can we get those values from ads read or catio config file ???
    operating_channels: int = 2
    """Number of operating oversampling input channels"""
    oversampling_factor: int = OVERSAMPLING_FACTOR
    """Oversampling factor applied to the analog input channels"""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL3702 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated analog value",
            ),
        )
        for i in range(1, self.operating_channels + 1):
            self.add_attribute(
                f"AICh{i}CycleCount",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_cycle"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Record transfer counter for channel#{i}",
                ),
            )
            if self.oversampling_factor == 1:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Int(),
                        io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                        group=self.attr_group_name,
                        initial_value=None,
                        description=f"Analog sample value(s) for channel#{i}",
                    ),
                )
            else:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Waveform(
                            array_dtype=np.int16, shape=(self.oversampling_factor,)
                        ),
                        io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                        group=self.attr_group_name,
                        initial_value=np.zeros(
                            (self.oversampling_factor,), dtype=np.int16
                        ),
                        description=f"Analog sample value(s) for channel#{i}",
                    ),
                )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}CycleCount"] = f"Ch{i} CycleCount"
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = f"Ch{i} Sample 0"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL4134Controller(CATioTerminalController):
    """A sub-controller for an EL4134 EtherCAT analog output terminal."""

    io_function: str = "4-channel analog output, +/-10V, 16-bit"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of analog output channels."""
    coe_manager: EL4134CoEManager | None = None
    """Manager instance which controls the terminal CoE parameters."""

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the EL4134 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = EL4134CoEManager(
                connection, ams_address, EL4134CoEParameters(), self.ecat_name
            )
        assert 1 <= self.num_channels <= 4, (
            f"{self.ecat_name} has a maximum of 4 AO channels; "
            f"got a configuration request for {self.num_channels} channels."
        )
        await self.coe_manager.read_io_configuration(self.num_channels)

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL4134 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AOCh{i}Value",
                AttrRW(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} analog output value",
                ),
            )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"AOCh{i}Value"] = f"AO Output Channel {i}.Analog output"

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"

        # Get the attributes for the available CoE parameters
        assert self.coe_manager is not None
        coe_attributes = await self.coe_manager.get_io_attributes()
        if coe_attributes:
            for name, attr in coe_attributes.items():
                self.add_attribute(name, attr)

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL9410Controller(CATioTerminalController):
    """A sub-controller for an EL9410 EtherCAT power supply terminal."""

    io_function: str = "2A power supply for E-bus"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL9410 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUp",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("contacts_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="Power contacts voltage diagnostic status",
            ),
        )
        self.add_attribute(
            "StatusUs",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("ebus_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="E-bus supply voltage diagnostic status",
            ),
        )

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"
        self.ads_name_map["StatusUp"] = "Status Up"
        self.ads_name_map["StatusUs"] = "Status Us"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL9505Controller(CATioTerminalController):
    """A sub-controller for an EL9505 EtherCAT power supply terminal."""

    io_function: str = "5V DC output power supply"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL9505 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUo",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("output_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="Output voltage status",
            ),
        )

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"
        self.ads_name_map["StatusUo"] = "Status Uo"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL9512Controller(CATioTerminalController):
    """A sub-controller for an EL9512 EtherCAT power supply terminal."""

    io_function: str = "12V DC output power supply"
    """Function description of the I/O controller."""

    async def get_io_attributes(self) -> None:
        """
        Get and create all EL9512 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal
        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUo",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("output_status"),
                group=self.attr_group_name,
                initial_value=None,
                description="Output voltage status",
            ),
        )

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"
        self.ads_name_map["StatusUo"] = "Status Uo"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class ELM3704v0000Controller(CATioTerminalController):
    """A sub-controller for an ELM3704-0000 EtherCAT analog input terminal."""

    io_function: str = "4-channel analog input, multi-function, 24-bit, 10 ksps"
    """Function description of the I/O controller."""
    oversampling_factor: int = ELM_OVERSAMPLING_FACTOR  # complex setup, see TwinCAT
    """Oversampling factor applied to the analog input channels"""
    num_channels = 4
    """Number of analog input channels."""
    coe_manager: ELM3704CoEManager | None = None
    """Manager instance which controls the terminal CoE parameters."""

    async def read_configuration(
        self, connection: CATioConnection, ams_address: AmsAddress, io_name: str
    ) -> None:
        """Read the configuration of the ELM3704 terminal."""
        logger.debug(f"Updating configuration for {self.name} (a.k.a. {self.name})... ")
        if self.coe_manager is None:
            self.coe_manager = ELM3704CoEManager(
                connection, ams_address, ELM3704CoEParameters(), self.ecat_name
            )
        assert 1 <= self.num_channels <= 4, (
            f"{self.ecat_name} has a maximum of 4 AI channels; "
            f"got a configuration request for {self.num_channels} channels."
        )
        await self.coe_manager.read_io_configuration(self.num_channels)

    async def get_io_attributes(self) -> None:
        """
        Get and create all ELM3704-0000 terminal attributes.
        """
        # Get the generic CATio terminal controller attributes
        initial_attr_count = len(self.attributes)
        await super().get_io_attributes()

        # Get the attributes specific to this type of terminal

        self.add_attribute(
            "WcState",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("wcounter_state"),
                group=self.attr_group_name,
                initial_value=None,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=CATioControllerSymbolAttributeIORef("input_toggle"),
                group=self.attr_group_name,
                initial_value=None,
                description="Availability of an updated digital value",
            ),
        )
        self.add_attribute(
            "AICh1LatchTime",
            AttrR(
                datatype=Waveform(array_dtype=np.uint32, shape=(2,)),
                io_ref=CATioControllerSymbolAttributeIORef("channel1_latch"),
                group=self.attr_group_name,
                initial_value=np.zeros((2,), dtype=np.uint32),
                description="Latch time for next channel samples",
            ),
        )
        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_status"),
                    group=self.attr_group_name,
                    initial_value=None,
                    description=f"Channel#{i} Process Analog Input status",
                ),
            )
            if self.oversampling_factor == 1:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Int(),
                        io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                        group=self.attr_group_name,
                        initial_value=None,
                        description=f"ELM3704 terminal channel#{i} value",
                    ),
                )
            else:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Waveform(
                            array_dtype=np.int32, shape=(self.oversampling_factor,)
                        ),
                        io_ref=CATioControllerSymbolAttributeIORef(f"channel{i}_value"),
                        group=self.attr_group_name,
                        initial_value=np.zeros(
                            (self.oversampling_factor,), dtype=np.int32
                        ),
                        description=f"ELM3704 terminal channel#{i} value",
                    ),
                )
            # Map the FastCS channel attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"PAI Status Channel {i}.Status"
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = (
                f"PAI Samples {self.oversampling_factor} Channel {i}.Samples"
            )

        # Map the FastCS attribute name to the symbol name used by ADS
        self.ads_name_map["WcState"] = "WcState.WcState"
        self.ads_name_map["InputToggle"] = "WcState.InputToggle"
        self.ads_name_map["AICh1LatchTime"] = (
            "PAI Timestamp Channel 1.StartTimeNextLatch"
        )

        # Get the attributes for the available CoE parameters
        assert self.coe_manager is not None
        coe_attributes = await self.coe_manager.get_io_attributes()
        if coe_attributes:
            for name, attr in coe_attributes.items():
                self.add_attribute(name, attr)

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


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
    "EL2024-0010": EL2024v0010Controller,
    "EL2124": EL2124Controller,
    "EL3104": EL3104Controller,
    "EL3602": EL3602Controller,
    "EL3702": EL3702Controller,
    "EL4134": EL4134Controller,
    "EL9410": EL9410Controller,
    "EL9505": EL9505Controller,
    "EL9512": EL9512Controller,
    "ELM3704-0000": ELM3704v0000Controller,
    "ETHERCAT": EtherCATMasterController,
}


def get_supported_hardware(self) -> None:
    """
    Log the list of I/O hardware currently supported by the CATio driver.
    """
    logger.info(
        "List of I/O hardware currently supported by the CATio driver:\n "
        + f"{list(SUPPORTED_CONTROLLERS.keys())}"
    )
