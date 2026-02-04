"""Dynamic symbol attribute generation for FastCS controllers.

This module provides utilities for adding symbol-based FastCS attributes
to dynamically generated terminal controllers.
"""

from dataclasses import dataclass

from fastcs.attributes import AttrR, AttrRW

from catio_terminals.models import SymbolNode
from fastcs_catio.catio_attribute_io import CATioControllerSymbolAttributeIORef
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.catio_dynamic_types import AdsItemBase
from fastcs_catio.terminal_config import (
    symbol_to_ads_name,
    symbol_to_fastcs_name,
)


@dataclass
class SymbolAdsItem(AdsItemBase):
    """ADS item for processing data symbols.

    Stores the symbol name and type information for use with
    CATioControllerSymbolAttributeIORef.

    Args:
        name: The ADS symbol name (e.g., "Channel 1").
        type_name: The TwinCAT type name (e.g., "UINT", "INT").
        fastcs_name: The FastCS attribute name (snake_case).
        access: Access type (e.g., "Read-only", "Read/Write").
    """

    def __str__(self) -> str:
        """Return the symbol name."""
        return self.name


def _add_attribute(
    controller: CATioTerminalController,
    ads_item: SymbolAdsItem,
    desc: str,
) -> None:
    """Add a FastCS attribute to a controller.

    Args:
        controller: The controller to add the attribute to.
        ads_item: The ADS item containing name, type, fastcs_name, and access.
        desc: The attribute description.
    """
    if ads_item.readonly:
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrR(
                datatype=ads_item.fastcs_datatype,
                io_ref=None,
                group=controller.attr_group_name,
                initial_value=None,
                description=desc,
            ),
        )
    else:
        io_ref = CATioControllerSymbolAttributeIORef(ads_item.name)
        controller.add_attribute(
            ads_item.fastcs_name,
            AttrRW(
                datatype=ads_item.fastcs_datatype,
                io_ref=io_ref,
                group=controller.attr_group_name,
                initial_value=None,
                description=desc,
            ),
        )
    controller.ads_name_map[ads_item.fastcs_name] = str(ads_item)


def add_symbol_attribute(
    controller: CATioTerminalController, symbol: SymbolNode
) -> None:
    """Add FastCS attributes for a symbol to a controller.

    Handles both single-channel and multi-channel symbols.

    Args:
        controller: The controller to add attributes to.
        symbol: The symbol definition.
    """
    if symbol.channels > 1:
        # Multi-channel symbol - create one attribute per channel
        for ch in range(1, symbol.channels + 1):
            fastcs_name = symbol_to_fastcs_name(symbol, ch)
            ads_name = symbol_to_ads_name(symbol, ch)
            ads_item = SymbolAdsItem(
                name=ads_name,
                type_name=symbol.type_name,
                fastcs_name=fastcs_name,
                access=symbol.access,
            )
            desc = symbol.tooltip or f"{symbol.name_template} ch {ch}"
            _add_attribute(controller, ads_item, desc)
    else:
        # Single-channel symbol - use fastcs_name from YAML
        fastcs_name = symbol_to_fastcs_name(symbol)
        ads_name = symbol_to_ads_name(symbol)
        ads_item = SymbolAdsItem(
            name=ads_name,
            type_name=symbol.type_name,
            fastcs_name=fastcs_name,
            access=symbol.access,
        )
        desc = symbol.tooltip or symbol.name_template
        _add_attribute(controller, ads_item, desc)
