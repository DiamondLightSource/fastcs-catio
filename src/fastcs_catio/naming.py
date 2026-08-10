"""Static prediction of the PV names fastcs-catio gives an EtherCAT chain.

At runtime the names in this module are produced as a side effect of ADS
discovery: :meth:`~fastcs_catio.client.FastCSClient._get_ethercat_chains`
stamps each slave's :class:`~fastcs_catio.devices.ChainLocation`, and
:meth:`~fastcs_catio.catio_controller.CATioServerController._resolve_controller_name_and_path`
renders it through :class:`~fastcs_catio.catio_controller.CATioNameMappings`.
Both need a live bus.

Tools that migrate an existing installation onto fastcs-catio need the same
names *before* any hardware exists — they have to rewrite the PV references in
other IOCs' databases ahead of time. This module derives them from the chain
order alone, keyed on terminal **type names** (``"EL3104"``), because that is
what a static description of a chain carries; the runtime instead keys on the
``(vendor_id, product_code, revision_number)`` identity reported over ADS.

Nothing here connects to hardware, runs a coroutine, or touches FastCS
controllers. ``tests/test_naming.py`` locks the output against the runtime
code path so the two cannot drift apart silently.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field

from fastcs_catio.catio_controller import CATioNameMappings
from fastcs_catio.terminal_config import get_terminal_type

__all__ = [
    "ChainEntry",
    "PredictedSlave",
    "UnknownTerminalTypeError",
    "predict_chain",
    "predict_names",
]

#: Exact type string that opens a new coupler node (``client.py``).
COUPLER_TYPE = "EK1100"

#: Bus extension. Before the first coupler it burns one position to reserve the
#: slot of an EK1200 that TwinCAT does not report (``client.py``).
EXTENSION_TYPE = "EK1110"

#: A box is a coupler-and-terminals in one housing. Anchored, as in ``client.py``.
BOX_TYPE_RE = re.compile(r"(E[PQR]{1}P?\d{4})")

#: Rendered in place of ``{group_alias}`` when the terminal type has no alias.
DEFAULT_GROUP_ALIAS = "MOD"

COUPLER = "coupler"
BOX = "box"
SLAVE = "slave"


class UnknownTerminalTypeError(KeyError):
    """A chain entry names a terminal absent from ``terminal_types.yaml``.

    Raised only when ``strict=True``. The runtime is more forgiving — an
    unrecognised identity simply renders as ``MOD<position>`` — but a migration
    tool that silently emitted ``MOD`` would rewrite live PV references to
    names the IOC never creates, so callers that are generating names for real
    hardware should ask for the error.
    """


@dataclass(frozen=True)
class ChainEntry:
    """One slave in bus order.

    :param type_name: CANopen type string, e.g. ``"EL3104"`` or
        ``"EL2024-0010"``. Must match a key of ``terminal_types.yaml``.
    :param revision: EtherCAT revision, e.g. ``0x00120000``. Recorded for
        diagnostics only: the alias is looked up by type name, which is
        revision-independent, mirroring the vendor+product fallback that
        :func:`~fastcs_catio.terminal_config.get_terminal_type_by_identity`
        applies when a rig runs newer firmware than the cached description.
    """

    type_name: str
    revision: int | None = None


@dataclass(frozen=True)
class PredictedSlave:
    """Where one slave lands, and what it will be called.

    :param node: 1-based coupler/box ordinal; 0 for slaves ahead of the first.
    :param position: 0 on the coupler itself, then 1, 2, ... along its terminals.
    :param category: :data:`COUPLER`, :data:`BOX` or :data:`SLAVE`.
    :param group_alias: alias from ``terminal_types.yaml``, or None when the
        type is unknown.
    :param index: the number actually rendered into this slave's template.
    :param path: PV path segments; ``prefix`` is these joined with ``":"``.
    """

    node: int
    position: int
    type_name: str
    category: str
    group_alias: str | None
    index: int
    path: list[str] = field(default_factory=list)

    @property
    def prefix(self) -> str:
        """The controller's PV prefix."""
        return ":".join(self.path)


def _as_entries(chain) -> list[ChainEntry]:
    """Accept ``ChainEntry``, ``(type_name, revision)`` or a bare type name."""
    entries: list[ChainEntry] = []
    for item in chain:
        if isinstance(item, ChainEntry):
            entries.append(item)
        elif isinstance(item, str):
            entries.append(ChainEntry(item))
        else:
            type_name, revision = item
            entries.append(ChainEntry(type_name, revision))
    return entries


def _group_alias(type_name: str, strict: bool) -> str | None:
    try:
        return get_terminal_type(type_name).group_alias
    except KeyError as err:
        if strict:
            raise UnknownTerminalTypeError(
                f"terminal type {type_name!r} is not in terminal_types.yaml, so "
                f"its group_alias is unknown and its PV names would silently "
                f"fall back to {DEFAULT_GROUP_ALIAS!r}"
            ) from err
        return None


def _render(template: str, index: int, context: dict[str, str]) -> str:
    """Render one name template exactly as the runtime does.

    The index is passed positionally *and* as ``n``, so ``{}``, ``{:02d}``,
    ``{n}`` and ``{n:02d}`` all work.
    """
    try:
        result = template.format(index, n=index, **context)
    except KeyError as err:
        raise ValueError(
            f"Unknown placeholder {err} in name mapping template {template!r}. "
            f"Available keys: {sorted(context)}"
        ) from err
    except (IndexError, ValueError) as err:
        raise ValueError(f"Invalid name mapping template {template!r}: {err}") from err
    if "_" in result:
        raise ValueError(
            f"Rendered PV name segment {result!r} contains an underscore. "
            "PV name components must use hyphens, not underscores."
        )
    return result


def _uses_group_alias(template: str) -> bool:
    return any(
        key == "group_alias" for _, key, _, _ in string.Formatter().parse(template)
    )


def _locate(entries: list[ChainEntry]) -> list[tuple[int, int, str]]:
    """Assign ``(node, position, category)`` to each entry, in bus order.

    A port of the loop in ``FastCSClient._get_ethercat_chains``. The two type
    tests are kept independent, as they are there; they are mutually exclusive
    in practice because ``EK1100`` cannot match :data:`BOX_TYPE_RE`.
    """
    located: list[tuple[int, int, str]] = []
    node = 0
    position = 0
    for entry in entries:
        type_name = entry.type_name
        category = SLAVE
        if type_name == EXTENSION_TYPE and node == 0:
            position += 1
        if type_name == COUPLER_TYPE:
            category = COUPLER
            node += 1
            position = 0
        if BOX_TYPE_RE.match(type_name) is not None:
            category = BOX
            node += 1
            position = 0
        located.append((node, position, category))
        position += 1
    return located


def predict_chain(
    chain,
    mappings: CATioNameMappings | None = None,
    root_id: str = "",
    device_id: int = 1,
    strict: bool = True,
) -> dict[tuple[int, int], PredictedSlave]:
    """Predict every controller name for one EtherCAT device's chain.

    :param chain: the device's slaves **in bus order** — :class:`ChainEntry`,
        ``(type_name, revision)`` pairs, or bare type-name strings.
    :param mappings: name templates; the :class:`CATioNameMappings` defaults
        are used when omitted.
    :param root_id: the ``id:`` from ``fastcs.yaml``, e.g.
        ``"BL21I-VA-CATIO-01"``. Rendered wherever a template says ``{id}``.
    :param device_id: the TwinCAT device id rendered into ``device_prefix``.
        Not derivable from a static chain — it is read over ADS — so callers
        with a single EtherCAT master should leave it at 1.
    :param strict: raise :exc:`UnknownTerminalType` for a terminal missing from
        ``terminal_types.yaml`` instead of letting its alias fall back to
        ``"MOD"``.

    :returns: ``(node, position)`` → :class:`PredictedSlave`, covering couplers
        and boxes as well as terminals.

    :raises UnknownTerminalType: in strict mode, per above.
    :raises ValueError: for a template that references an unknown placeholder
        or renders an underscore into a PV segment.

    Call it once per EtherCAT device: ``node`` restarts at 0 for each, so
    merging two devices into one chain would collide.
    """
    mappings = mappings or CATioNameMappings()
    entries = _as_entries(chain)
    located = _locate(entries)

    aliases = [
        _group_alias(entry.type_name, strict)
        if category not in (COUPLER, BOX)
        else _group_alias(entry.type_name, strict=False)
        for entry, (_, _, category) in zip(entries, located, strict=True)
    ]

    # Number the modules on each coupler per alias, so "{group_alias}{:02d}"
    # yields 24VDI01, 24VDI02, ... independently of the chain position. Keyed
    # as the runtime keys it, including the empty-string bucket for no alias.
    alias_seq: dict[tuple[int, int], int] = {}
    counters: dict[tuple[int, str], int] = {}
    for (node, position, category), alias in zip(located, aliases, strict=True):
        if category in (COUPLER, BOX):
            continue
        key = (node, alias or "")
        counters[key] = counters.get(key, 0) + 1
        alias_seq[(node, position)] = counters[key]

    device_path = [
        s
        for s in _render(mappings.device_prefix, device_id, {"id": root_id}).split(":")
        if s
    ]

    module_uses_alias = _uses_group_alias(mappings.module_prefix)

    predicted: dict[tuple[int, int], PredictedSlave] = {}
    # Only an EK1100 opens a new tree parent. A box gets its own node index but
    # stays a leaf, so terminals following it hang off the coupler still open.
    coupler_path: list[str] | None = None

    for entry, (node, position, category), alias in zip(
        entries, located, aliases, strict=True
    ):
        if category in (COUPLER, BOX):
            parent = coupler_path if category == BOX and coupler_path else device_path
            rendered = _render(
                mappings.node_prefix,
                node,
                {"id": root_id, "device_prefix": ":".join(parent)},
            )
            index = node
        else:
            parent = coupler_path if coupler_path is not None else device_path
            index = (
                alias_seq.get((node, position), position)
                if module_uses_alias
                else position
            )
            rendered = _render(
                mappings.module_prefix,
                index,
                {
                    "id": root_id,
                    "node_prefix": ":".join(parent),
                    "device_prefix": ":".join(parent[:-1]) if len(parent) >= 2 else "",
                    "group_alias": alias or DEFAULT_GROUP_ALIAS,
                },
            )

        path = [s for s in rendered.split(":") if s]
        predicted[(node, position)] = PredictedSlave(
            node=node,
            position=position,
            type_name=entry.type_name,
            category=category,
            group_alias=alias,
            index=index,
            path=path,
        )
        if category == COUPLER:
            coupler_path = path

    return predicted


def predict_names(
    chain,
    mappings: CATioNameMappings | None = None,
    root_id: str = "",
    device_id: int = 1,
    strict: bool = True,
) -> dict[tuple[int, int], str]:
    """``(node, position)`` → PV prefix, for one EtherCAT device's chain.

    The prefix-only view of :func:`predict_chain`; see it for the arguments and
    for the group alias, category and rendered index of each slave.

    >>> from fastcs_catio.naming import predict_names
    >>> from fastcs_catio.catio_controller import CATioNameMappings
    >>> names = predict_names(
    ...     ["EK1100", "EL3104", "EL1014"],
    ...     CATioNameMappings(
    ...         node_prefix="BL21I-VA-E1RIO-{:02d}",
    ...         module_prefix="{node_prefix}:{group_alias}{:02d}",
    ...     ),
    ...     root_id="BL21I-VA-CATIO-01",
    ... )
    >>> names[(1, 1)]
    'BL21I-VA-E1RIO-01:10VAI01'
    >>> names[(1, 2)]
    'BL21I-VA-E1RIO-01:24VDI01'
    """
    return {
        key: slave.prefix
        for key, slave in predict_chain(
            chain,
            mappings=mappings,
            root_id=root_id,
            device_id=device_id,
            strict=strict,
        ).items()
    }
