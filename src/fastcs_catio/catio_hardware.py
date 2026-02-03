# =============================================================================
# ===== BECKHOFF VARIABLES -- Documentation References ========================
# =============================================================================

# WcState and InputToggle:
# https://infosys.beckhoff.com/english.php?content=../content/1033/b110_ethercat_optioninterface/1984417163.html&id=

# =============================================================================


import numpy as np
from fastcs.attributes import AttrR
from fastcs.datatypes import Int, Waveform
from fastcs.logging import bind_logger
from fastcs.tracer import Tracer

from fastcs_catio.catio_controller import (
    CATioDeviceController,
    CATioTerminalController,
)
from fastcs_catio.devices import ELM_OVERSAMPLING_FACTOR, OVERSAMPLING_FACTOR

tracer = Tracer(name=__name__)
logger = bind_logger(logger_name=__name__)


class EtherCATMasterController(CATioDeviceController):
    """A sub-controller for an EtherCAT Master I/O device."""

    io_function: str = "EtherCAT Master Device"
    """Function description of the I/O controller."""

    # Depending on number of notification streams, we'll have more attr!!!
    # e.g. 3 streams -> Frm0State, Frm1State, Frm2State
    # This depends on the size of the notif system. For now, just implement Frm0*
    num_ads_streams: int = 1
    """Number of ADS streams currently implemented for specific parameters."""

    # Also from TwinCAT, it should be:
    # attr_dict["Inputs.Frm0State"] = AttrR(...)
    # but '.' is not allowed in fastCS attribute name -> error
    # name string should match pattern '^([A-Z][a-z0-9]*)*$'
    # so we map it as aliases in self.ads_name_map below

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Number of slaves reached in last cycle",
            ),
        )
        self.add_attribute(
            "InputsDevState",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="EtherCAT device input cycle frame status",
            ),
        )
        self.add_attribute(
            "OutputsDevCtrl",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="EtherCAT device output control value",
            ),
        )
        for i in range(0, self.num_ads_streams):
            self.add_attribute(
                f"InFrm{i}State",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description="Cyclic Ethernet input frame status",
                ),
            )
            self.add_attribute(
                f"InFrm{i}WcState",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description="Inputs accumulated working counter",
                ),
            )
            self.add_attribute(
                f"InFrm{i}InpToggle",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description="EtherCAT cyclic frame update indicator",
                ),
            )
            self.add_attribute(
                f"OutFrm{i}Ctrl",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description="EtherCAT output frame control value",
                ),
            )
            self.add_attribute(
                f"OutFrm{i}WcCtrl",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=1,
                description="Unique ID for the group of components",
            ),
        )

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1124Controller(CATioTerminalController):
    """A sub-controller for an EL1124 EtherCAT digital output terminal."""

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated digital value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital input value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DICh{i}Value"] = f"Channel{i}"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL1502Controller(CATioTerminalController):
    """A sub-controller for an EL1502 EtherCAT digital input terminal."""

    io_function: str = "2-channel digital input, counter, 24V DC, 100kHz"
    """Function description of the I/O controller."""
    num_channels = 2
    """Number of digital input channels."""

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated digital value",
            ),
        )
        self.add_attribute(
            "CNTInputStatus",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Input channel counter status",
            ),
        )
        self.add_attribute(
            "CNTInputValue",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Input channel counter value",
            ),
        )
        self.add_attribute(
            "CNTOutputStatus",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Output channel counter status",
            ),
        )
        self.add_attribute(
            "CNTOutputValue",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Output channel counter set value",
            ),
        )
        # Map the FastCS attribute names to the symbol names used by ADS
        self.ads_name_map["CNTInputStatus"] = "CNTInputs.Countervalue"
        self.ads_name_map["CNTInputValue"] = "CNTOutputs.Setcountervalue"
        self.ads_name_map["CNTOutputStatus"] = "CNTInputs.Countervalue"
        self.ads_name_map["CNTOutputValue"] = "CNTOutputs.Setcountervalue"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"DOCh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} digital output value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"DOCh{i}Value"] = f"Channel{i}"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL3104Controller(CATioTerminalController):
    """A sub-controller for an EL3104 EtherCAT analog input terminal."""

    io_function: str = "4-channel analog input, +/-10V, 16-bit, differential"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of analog input channels."""

    async def read_configuration(self) -> None:
        """Read the configuration of the EL3104 terminal."""
        # TO DO: Implement reading the configuration from ADS
        # do so for all terminals
        print(f"CONFIGURATION FOR {self.name} NOT IMPLEMENTED YET")

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated analog value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} voltage status",
                ),
            )
            self.add_attribute(
                f"AICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} analog input value",
                ),
            )
            # Map the FastCS attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AIStandardChannel{i}.Status"
            self.ads_name_map[f"AICh{i}Value"] = f"AIStandardChannel{i}.Value"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL3602Controller(CATioTerminalController):
    """A sub-controller for an EL3602 EtherCAT analog input terminal."""

    io_function: str = "2-channel analog input, up to +/-10V, 24-bit, high-precision"
    """Function description of the I/O controller."""
    num_channels: int = 2
    """Number of analog input channels."""

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Availability of an updated analog value",
            ),
        )

        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} voltage status",
                ),
            )
            self.add_attribute(
                f"AICh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} analog input value",
                ),
            )
            # Map the FastCS attribute names to the symbol names used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"AIInputsChannel{i}"
            self.ads_name_map[f"AICh{i}Value"] = f"AIInputsChannel{i}.Value"

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
        for i in range(1, self.operating_channels + 1):
            self.add_attribute(
                f"AICh{i}CycleCount",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Record transfer counter for channel#{i}",
                ),
            )
            if self.oversampling_factor == 1:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Int(),
                        io_ref=None,
                        group=self.attr_group_name,
                        initial_value=0,
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
                        io_ref=None,
                        group=self.attr_group_name,
                        initial_value=np.zeros(
                            (self.oversampling_factor,), dtype=np.int16
                        ),
                        description=f"Analog sample value(s) for channel#{i}",
                    ),
                )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}CycleCount"] = f"Ch{i}CycleCount"
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = f"Ch{i}Sample0"

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


class EL4134Controller(CATioTerminalController):
    """A sub-controller for an EL4134 EtherCAT analog output terminal."""

    io_function: str = "4-channel analog output, +/-10V, 16-bit"
    """Function description of the I/O controller."""
    num_channels: int = 4
    """Number of analog output channels."""

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AOCh{i}Value",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} analog output value",
                ),
            )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AOCh{i}Value"] = f"AOOutputChannel{i}.Analogoutput"

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUp",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Power contacts voltage diagnostic status",
            ),
        )
        self.add_attribute(
            "StatusUs",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="E-bus supply voltage diagnostic status",
            ),
        )

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUo",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Output voltage status",
            ),
        )

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        self.add_attribute(
            "InputToggle",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Counter for valid telegram received",
            ),
        )
        self.add_attribute(
            "StatusUo",
            AttrR(
                datatype=Int(),
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Output voltage status",
            ),
        )

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
                io_ref=None,
                group=self.attr_group_name,
                initial_value=0,
                description="Slave working counter state value",
            ),
        )
        for i in range(1, self.num_channels + 1):
            self.add_attribute(
                f"AICh{i}Status",
                AttrR(
                    datatype=Int(),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=0,
                    description=f"Channel#{i} Process Analog Input status",
                ),
            )
            self.add_attribute(
                f"AICh{i}LatchTime",
                AttrR(
                    datatype=Waveform(array_dtype=np.uint32, shape=(2,)),
                    io_ref=None,
                    group=self.attr_group_name,
                    initial_value=np.zeros((2,), dtype=np.uint32),
                    description=f"Latch time for next channel#{i} samples",
                ),
            )
            if self.oversampling_factor == 1:
                self.add_attribute(
                    f"AICh{i}ValueOvsmpl",
                    AttrR(
                        datatype=Int(),
                        io_ref=None,
                        group=self.attr_group_name,
                        initial_value=0,
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
                        io_ref=None,
                        group=self.attr_group_name,
                        initial_value=np.zeros(
                            (self.oversampling_factor,), dtype=np.int32
                        ),
                        description=f"ELM3704 terminal channel#{i} value",
                    ),
                )
            # Map the FastCS attribute name to the symbol name used by ADS
            self.ads_name_map[f"AICh{i}Status"] = f"PAIStatusChannel{i}.Status"
            self.ads_name_map[f"AICh{i}LatchTime"] = (
                f"PAITimestampChannel{i}.StartTimeNextLatch"
            )
            self.ads_name_map[f"AICh{i}ValueOvsmpl"] = (
                f"PAISamples{self.oversampling_factor}Channel{i}.Samples"
            )

        attr_count = len(self.attributes) - initial_attr_count
        logger.debug(f"Created {attr_count} attributes for the controller {self.name}.")


# Map of supported controllers available to the FastCS CATio system
SUPPORTED_CONTROLLERS: dict[
    str, type[CATioDeviceController | CATioTerminalController]
] = {
    # "EK1100": EK1100Controller,
    # "EK1101": EK1101Controller,
    # "EK1110": EK1110Controller,
    # # "EL1004": EL1004Controller,
    # # "EL1014": EL1014Controller,
    # "EL1084": EL1084Controller,
    # "EL1124": EL1124Controller,
    # # "EL1502": EL1502Controller,
    # # "EL2024": EL2024Controller,
    # "EL2024-0010": EL2024v0010Controller,
    # "EL2124": EL2124Controller,
    # "EL3104": EL3104Controller,
    # "EL3602": EL3602Controller,
    # "EL3702": EL3702Controller,
    # "EL4134": EL4134Controller,
    # "EL9410": EL9410Controller,
    # "EL9505": EL9505Controller,
    # "EL9512": EL9512Controller,
    # "ELM3704-0000": ELM3704v0000Controller,
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
