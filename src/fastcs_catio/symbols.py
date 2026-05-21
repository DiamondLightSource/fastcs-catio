"""YAML-driven bus-side symbol expansion.

For each AdsSymbolNode discovered on the bus we decide how to turn it
into one or more :class:`AdsSymbol` entries:

* **Non-BIGTYPE primitives** (BIT, UINT16, REAL, ...) are emitted as-is
  with the dtype implied by their ADS type.
* **BIGTYPE structs owned by a slave** are expanded by walking the
  matching terminal's YAML rows: each ``selected: true`` row produces
  one AdsSymbol at ``parent.offset + row.bit_offset // 8``.
* **Master-device structs** (``Inputs_TYPE`` / ``Outputs_TYPE``) carry
  the bus-level frame state used by :mod:`fastcs_catio.catio_hardware`.
  They are expanded from a tiny built-in layout — they are not
  user-extensible, so they don't live in YAML.

Replaces the legacy ``AdsSymbolTypePattern`` LUT removed in issue #54.
"""

import re
from collections.abc import Iterable
from logging import getLogger

import numpy as np
import numpy.typing as npt

from ._constants import AdsDataType
from .devices import AdsSymbol, AdsSymbolNode, IOSlave
from .terminal_config import get_terminal_type_by_identity

logger = getLogger(__name__)


# YAML type_name → (numpy dtype, element size in bytes)
_DTYPE_MAP: dict[str, tuple[npt.DTypeLike, int]] = {
    "SINT": (np.int8, 1),
    "USINT": (np.uint8, 1),
    "BYTE": (np.uint8, 1),
    "INT": (np.int16, 2),
    "UINT": (np.uint16, 2),
    "WORD": (np.uint16, 2),
    "DINT": (np.int32, 4),
    "UDINT": (np.uint32, 4),
    "DWORD": (np.uint32, 4),
    "LINT": (np.int64, 8),
    "ULINT": (np.uint64, 8),
    "LWORD": (np.uint64, 8),
    "REAL": (np.float32, 4),
    "LREAL": (np.float64, 8),
    "BIT": (np.uint8, 1),
    "BOOL": (np.uint8, 1),
    "BIT2": (np.uint8, 1),
    "BIT3": (np.uint8, 1),
    "BIT4": (np.uint8, 1),
}

_ARRAY_RE = re.compile(r"^ARRAY\s*\[\s*(\d+)\s*\.\.\s*(\d+)\s*\]\s*OF\s+(\S+)", re.I)

# AdsDataType (from the bus) → numpy dtype, for primitive (non-BIGTYPE) nodes.
_PRIMITIVE_DTYPE_MAP: dict[AdsDataType, npt.DTypeLike] = {
    AdsDataType.ADS_TYPE_BIT: np.uint8,
    AdsDataType.ADS_TYPE_INT8: np.int8,
    AdsDataType.ADS_TYPE_UINT8: np.uint8,
    AdsDataType.ADS_TYPE_INT16: np.int16,
    AdsDataType.ADS_TYPE_UINT16: np.uint16,
    AdsDataType.ADS_TYPE_INT32: np.int32,
    AdsDataType.ADS_TYPE_UINT32: np.uint32,
    AdsDataType.ADS_TYPE_REAL32: np.float32,
    AdsDataType.ADS_TYPE_REAL64: np.float64,
    AdsDataType.ADS_TYPE_INT64: np.int64,
    AdsDataType.ADS_TYPE_UINT64: np.uint64,
}


# Master-device frame-state struct layouts.
# Kept tiny and built-in: these structures aren't user-extensible.
_DEVICE_INPUTS_FIELDS: list[tuple[str, npt.DTypeLike, int]] = [
    ("Frm0State", np.uint16, 0),
    ("Frm0WcState", np.uint16, 2),
    ("Frm0InputToggle", np.uint16, 4),
    ("SlaveCount", np.uint16, 10),
    ("DevState", np.uint16, 14),
]
_DEVICE_OUTPUTS_FIELDS: list[tuple[str, npt.DTypeLike, int]] = [
    ("Frm0Ctrl", np.uint16, 0),
    ("Frm0WcCtrl", np.uint16, 2),
    ("DevCtrl", np.uint16, 4),
]


def _dtype_for_type_name(type_name: str) -> tuple[npt.DTypeLike, int]:
    """Resolve a YAML ``type_name`` into ``(numpy dtype, element count)``."""
    m = _ARRAY_RE.match(type_name)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        element = m.group(3).upper()
        elem_dtype, _ = _DTYPE_MAP.get(element, (np.uint8, 1))
        return elem_dtype, hi - lo + 1
    return _DTYPE_MAP.get(type_name.upper(), (np.uint8, 1))


def _find_parent_node(
    nodes_by_name: dict[str, AdsSymbolNode],
    full_name: str,
) -> AdsSymbolNode | None:
    """Walk up a dotted name to find an enclosing bus node, or None."""
    name = full_name
    while name:
        if name in nodes_by_name:
            return nodes_by_name[name]
        dot = name.rfind(".")
        if dot == -1:
            return None
        name = name[:dot]
    return None


def expand_symbols_for_slave(
    nodes_by_name: dict[str, AdsSymbolNode],
    slave: IOSlave,
) -> dict[str, AdsSymbol]:
    """Emit AdsSymbols for one slave, driven by its YAML rows."""
    ident = slave.identity
    terminal = get_terminal_type_by_identity(
        int(ident.vendor_id),
        int(ident.product_code),
        int(ident.revision_number),
    )
    if terminal is None:
        logger.warning(
            f"No terminal YAML matches slave '{slave.name}' identity "
            f"(vendor={ident.vendor_id}, product={ident.product_code}, "
            f"revision={ident.revision_number}); no symbols expanded."
        )
        return {}

    symbols: dict[str, AdsSymbol] = {}
    for row in terminal.symbol_nodes:
        if not row.selected:
            continue
        # ADS addresses are byte-granular. Sub-byte bit-field rows
        # (e.g. EL3104's `.Status__Limit 1` at bit 2) can't be
        # subscribed independently — the data lives inside the parent
        # status byte, and the ADS server rejects the notification
        # request with ADSERR_DEVICE_SYMBOLVERSIONINVALID. Skip them.
        if row.bit_offset % 8 != 0:
            continue
        channels: Iterable[int | None] = (
            range(1, row.channels + 1) if row.channels > 1 else (None,)
        )
        for ch in channels:
            resolved = row.name_template
            if ch is not None and "{channel}" in resolved:
                resolved = resolved.replace("{channel}", str(ch))

            full_name = f"{slave.name}.{resolved}"
            parent = _find_parent_node(nodes_by_name, full_name)
            if parent is None:
                logger.debug(
                    f"No bus node provides offset for '{full_name}'; skipping."
                )
                continue

            dtype, count = _dtype_for_type_name(row.type_name)
            byte_offset = int(parent.index_offset) + row.bit_offset // 8
            symbols[full_name] = AdsSymbol(
                parent_id=parent.parent_id,
                name=full_name,
                dtype=dtype,
                size=count,
                group=parent.index_group,
                offset=byte_offset,
                comment=parent.comment,
            )
    return symbols


def expand_device_symbols(
    nodes: Iterable[AdsSymbolNode],
    device_name: str,
) -> dict[str, AdsSymbol]:
    """Emit AdsSymbols for the EtherCAT master's Inputs / Outputs structs."""
    symbols: dict[str, AdsSymbol] = {}
    for node in nodes:
        if node.ads_type != AdsDataType.ADS_TYPE_BIGTYPE:
            continue
        # Match against both bare ("Inputs") and device-prefixed
        # ("ETH1.Inputs") names — different ADS servers report differently.
        bare = node.name.rsplit(".", 1)[-1]
        if bare == "Inputs":
            fields = _DEVICE_INPUTS_FIELDS
        elif bare == "Outputs":
            fields = _DEVICE_OUTPUTS_FIELDS
        else:
            continue
        for field_name, dtype, offset_shift in fields:
            sym_name = f"{device_name}.{bare}.{field_name}"
            symbols[sym_name] = AdsSymbol(
                parent_id=node.parent_id,
                name=sym_name,
                dtype=dtype,
                size=1,
                group=node.index_group,
                offset=int(node.index_offset) + offset_shift,
                comment=node.comment,
            )
    return symbols


def expand_primitive_node(node: AdsSymbolNode) -> AdsSymbol | None:
    """Expand a non-BIGTYPE primitive symbol node to an AdsSymbol."""
    dtype = _PRIMITIVE_DTYPE_MAP.get(node.ads_type)
    if dtype is None:
        return None
    return AdsSymbol(
        parent_id=node.parent_id,
        name=node.name,
        dtype=dtype,
        size=1,
        group=node.index_group,
        offset=int(node.index_offset),
        comment=node.comment,
    )


def build_symbols_for_device(
    nodes: Iterable[AdsSymbolNode],
    slaves: Iterable[IOSlave],
    device_name: str,
) -> dict[str, AdsSymbol]:
    """Compute the full AdsSymbol map for one EtherCAT device.

    Driven by the bus's discovered node list. Order of resolution:

    1. Slave-scoped YAML rows produce AdsSymbols for every BIGTYPE owned
       by a known slave.
    2. Master-device Inputs / Outputs structs are expanded from the
       built-in layouts.
    3. Any remaining non-BIGTYPE primitive nodes are emitted as-is so
       runtime symbols (WcState, InputToggle, etc.) still bind.
    """
    nodes_list = list(nodes)
    nodes_by_name = {n.name: n for n in nodes_list}
    symbols: dict[str, AdsSymbol] = {}

    for slave in slaves:
        symbols.update(expand_symbols_for_slave(nodes_by_name, slave))

    symbols.update(expand_device_symbols(nodes_list, device_name))

    for node in nodes_list:
        if node.ads_type == AdsDataType.ADS_TYPE_BIGTYPE:
            continue
        if node.name in symbols:
            continue
        prim = expand_primitive_node(node)
        if prim is not None:
            symbols[prim.name] = prim
    return symbols
