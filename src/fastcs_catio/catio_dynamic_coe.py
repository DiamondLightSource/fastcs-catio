"""CoE (CANopen over EtherCAT) utilities for dynamic controller generation.

This module provides classes and functions for handling CoE objects in
dynamically generated FastCS controllers.
"""

from dataclasses import dataclass

import numpy as np
from fastcs.attributes import AttrR, AttrRW

from fastcs_catio.catio_attribute_io import CATioControllerCoEAttributeIORef
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.catio_dynamic_types import (
    AdsItemBase,
    twincat_type_to_numpy,
)
from fastcs_catio.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CoEAdsItem(AdsItemBase):
    """ADS item for CoE (CANopen over EtherCAT) objects.

    Extends AdsItemBase with CoE-specific index and subindex fields.

    Args:
        name: The CoE object name (e.g., "Hardware version").
        type_name: The TwinCAT type name (e.g., "UINT").
        fastcs_name: The FastCS attribute name (snake_case).
        access: Access type (e.g., "ro", "rw").
        index: The CoE object index (e.g., 0x8000).
        subindex: The CoE object subindex (e.g., 0x01).
        bit_size: Size in bits (for compound types like DT8020).
    """

    index: int = 0
    subindex: int = 0
    bit_size: int | None = None

    def __str__(self) -> str:
        """Return the string representation like 'CoE:8000:01'."""
        return f"CoE:{self.index:04X}:{self.subindex:02X}"

    @property
    def index_hex(self) -> str:
        """Return the index as a hex string with 0x prefix (e.g., '0x8000')."""
        return f"0x{self.index:04X}"

    @property
    def subindex_hex(self) -> str:
        """Return the subindex as a hex string with 0x prefix (e.g., '0x0001')."""
        return f"0x{self.subindex:04X}"

    @property
    def numpy_dtype(self) -> np.dtype:
        """Return the numpy dtype for this CoE item's type_name.

        Overrides base class to use bit_size for compound types.

        Returns:
            numpy dtype corresponding to the TwinCAT type.

        Raises:
            ValueError: If the type_name is not recognized and no bit_size.
        """
        return twincat_type_to_numpy(self.type_name, self.bit_size)


def add_coe_attribute(
    controller: CATioTerminalController,
    ads_item: CoEAdsItem,
) -> None:
    """Add a CoE FastCS attribute to a controller.

    Creates a CATioControllerCoEAttributeIORef with:
    - index_hex and subindex_hex: CoE address (from YAML via ads_item)
    - numpy_dtype: Data type for the CoE parameter (from YAML via ads_item)
    - AmsAddress: Obtained from client.get_coe_ams_address(controller.io)

    Args:
        controller: The controller to add the attribute to.
        ads_item: The CoE ADS item containing index, subindex, type, fastcs_name,
            and access.

    Raises:
        AssertionError: If controller.io is not an IOSlave.
    """
    from fastcs_catio.devices import IOSlave

    # CoE parameters only apply to terminal controllers (IOSlave)
    assert isinstance(controller.io, IOSlave), (
        f"CoE attributes require IOSlave, got {type(controller.io)}"
    )

    # Skip io_ref for compound types - only create for primitive types
    if not ads_item.is_primitive_type:
        # For compound types, just record the mapping without creating an attribute
        logger.warning(f"Skipping creation of CoE item {ads_item}")
        return

    # Get AmsAddress from the client using the controller's IOSlave
    address = controller.connection.client.get_coe_ams_address(controller.io)

    # skip compound types as we do their sub indices separately
    if not ads_item.is_primitive_type:
        return

    io_ref = CATioControllerCoEAttributeIORef(
        name=ads_item.fastcs_name,
        index=ads_item.index_hex,
        subindex=ads_item.subindex_hex,
        address=address,
        dtype=ads_item.numpy_dtype,
    )

    if ads_item.readonly:
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrR(
                datatype=ads_item.fastcs_datatype,
                io_ref=io_ref,
                group=ads_item.fastcs_group or controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    else:
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrRW(
                datatype=ads_item.fastcs_datatype,
                io_ref=io_ref,
                group=ads_item.fastcs_group or controller.attr_group_name,
                initial_value=None,
                description=str(ads_item),
            ),
        )
    controller.ads_name_map[ads_item.fastcs_name] = str(ads_item)
