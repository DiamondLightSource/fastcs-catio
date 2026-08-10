"""Tests for the static naming API.

The point of :mod:`fastcs_catio.naming` is that it agrees with what the live
IOC does. So most of this file does not assert against hand-written strings —
it drives the *runtime* code path (``AsyncioADSClient._get_ethercat_chains``,
``CATioServerController._compute_module_alias_indices`` and
``_resolve_controller_name_and_path``) over a synthetic chain and asserts that
:func:`~fastcs_catio.naming.predict_chain` produced the same answer. Change the
rule in either place without the other and these fail.
"""

import asyncio

import pytest

from fastcs_catio._constants import DeviceType
from fastcs_catio._types import AmsNetId
from fastcs_catio.catio_controller import CATioNameMappings, CATioServerController
from fastcs_catio.client import AsyncioADSClient
from fastcs_catio.devices import (
    DeviceFrames,
    IODevice,
    IOIdentity,
    IOServer,
    IOSlave,
    IOTreeNode,
    SlaveCRC,
    SlaveState,
)
from fastcs_catio.naming import (
    ChainEntry,
    UnknownTerminalTypeError,
    predict_chain,
    predict_names,
)
from fastcs_catio.terminal_config import get_terminal_type

ROOT_ID = "BL21I-VA-CATIO-01"

DLS_MAPPINGS = CATioNameMappings(
    device_prefix="{id}:ETH{:02d}",
    node_prefix="BL21I-VA-E1RIO-{:02d}",
    module_prefix="{node_prefix}:{group_alias}{:02d}",
)

# BL21I-VA-IOC-01's chain, in the order its builder XML declares the slaves.
# Its legacy coupler labels run ERIO-04, -12, -03, -02, -01 -- the legacy
# numbers carry no ordering information, which is the whole reason this
# module exists.
I21_VA_IOC_01 = [
    "EK1100", "EL3104", "EL3104", "EL3104", "EL3104", "EL1014", "EL1014",
    "EK1100", "EL3104", "EL3104",
    "EK1100", "EL3104", "EL3104", "EL1014", "EL1014",
    "EK1100", "EL3104", "EL3104", "EL1014", "EL1014",
    "EK1100", "EL3104", "EL3104", "EL3104", "EL3104", "EL1014", "EL1014",
]  # fmt: skip


def _make_slave(type_name: str, index: int) -> IOSlave:
    """An IOSlave carrying the real identity of ``type_name``."""
    terminal = get_terminal_type(type_name)
    return IOSlave(
        parent_device=1,
        type=type_name,
        name=f"Slave{index:03d}",
        address=1000 + index,
        identity=IOIdentity(
            vendor_id=terminal.identity.vendor_id,
            product_code=terminal.identity.product_code,
            revision_number=terminal.identity.revision_number,
            serial_number=0,
        ),
        states=SlaveState(ecat_state=0, link_status=0),
        crcs=SlaveCRC(port_a_crc=0, port_b_crc=0, port_c_crc=0, port_d_crc=0),
    )


def _make_client(chain: list[str], device_id: int = 1) -> AsyncioADSClient:
    """A client with one EtherCAT device, bypassing all connection setup."""
    client = object.__new__(AsyncioADSClient)
    device = IODevice(
        id=device_id,
        type=DeviceType.IODEVICETYPE_ETHERCAT,
        name=f"Device{device_id}",
        netid=AmsNetId.from_string("127.0.0.1.1.1"),
        identity=IOIdentity(
            vendor_id=1, product_code=2, revision_number=3, serial_number=4
        ),
        frame_counters=DeviceFrames(
            time=0, cyclic_sent=0, cyclic_lost=0, acyclic_sent=0, acyclic_lost=0
        ),
        slave_count=len(chain),
        slaves_states=[],
        slaves_crc_counters=[],
        slaves=[_make_slave(t, i) for i, t in enumerate(chain)],
    )
    client._ecdevices = {device_id: device}
    client.ioserver = IOServer(name=ROOT_ID, version="1", build=0, num_devices=1)
    return client


def _drive(coro):
    """Run *coro* to completion on a private loop, leaving the global one alone.

    Deliberately not ``asyncio.run``: that clears the process-wide loop when it
    finishes. ``test_system.py`` installs a loop of its own to drive the ADS
    simulator, and clearing it strands that loop with its sockets still open --
    it is collected at some arbitrary later point and pytest reports the
    unraisable ResourceWarning against whichever test happens to be running,
    which is never this one.

    Reading the previous loop to restore it afterwards is no good either:
    ``get_event_loop()`` is deprecated from 3.12, and with
    ``filterwarnings = "error"`` the warning becomes an exception raised before
    the coroutine is ever awaited. So never touch the global loop at all --
    ``new_event_loop()`` does not install one, and ``run_until_complete``
    drives the loop object directly.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _runtime_names(
    chain: list[str], mappings: CATioNameMappings, device_id: int = 1
) -> dict[tuple[int, int], str]:
    """Run the production code path and collect ``(node, position) -> prefix``.

    Mirrors ``CATioServerController.get_subcontrollers_from_node`` closely
    enough to reach every node, without needing FastCS controllers or a bus.
    """
    client = _make_client(chain, device_id)
    _drive(client._get_ethercat_chains())
    tree = client._generate_system_tree()

    controller = object.__new__(CATioServerController)
    controller._path = [ROOT_ID]
    controller._name_mappings = mappings
    controller._module_alias_indices = controller._compute_module_alias_indices(tree)

    names: dict[tuple[int, int], str] = {}

    def walk(node: IOTreeNode, parent_path: list[str]) -> None:
        for child in node.children:
            _, path = controller._resolve_controller_name_and_path(child, parent_path)
            data = child.data
            if isinstance(data, IOSlave):
                key = (int(data.loc_in_chain.node), int(data.loc_in_chain.position))
                names[key] = ":".join(path)
            walk(child, path)

    walk(tree, controller._path)
    return names


@pytest.mark.parametrize(
    "chain",
    [
        pytest.param(I21_VA_IOC_01, id="i21-va-ioc-01"),
        pytest.param(["EK1100", "EL3104", "EL1014", "EL2024-0010"], id="mixed-aliases"),
        pytest.param(["EK1100", "EL1014", "EL1014", "EL1014"], id="same-alias-run"),
        pytest.param(["EK1110", "EK1100", "EL3104"], id="leading-ek1110"),
        pytest.param(["EK1100", "EL3104", "EK1122", "EL3104"], id="ek1122-junction"),
        pytest.param(["EK1100", "EL3104", "EK1100", "EL3104"], id="two-couplers"),
    ],
)
@pytest.mark.parametrize(
    "mappings",
    [
        pytest.param(DLS_MAPPINGS, id="dls"),
        pytest.param(CATioNameMappings(), id="library-defaults"),
        pytest.param(
            CATioNameMappings(module_prefix="{node_prefix}:MOD{:02d}"),
            id="no-group-alias",
        ),
    ],
)
def test_prediction_matches_runtime(chain, mappings):
    """The static prediction equals what the live discovery path produces."""
    predicted = predict_names(chain, mappings, root_id=ROOT_ID, strict=False)
    assert predicted == _runtime_names(chain, mappings)


def test_i21_worked_examples():
    """The three migration examples from the DLS I21 conversion design."""
    names = predict_names(I21_VA_IOC_01, DLS_MAPPINGS, root_id=ROOT_ID)

    # legacy BL21I-VA-ERIO-01:MOD1 -- 5th coupler, 1st terminal
    assert names[(5, 1)] == "BL21I-VA-E1RIO-05:10VAI01"
    # legacy BL21I-VA-ERIO-01:MOD5 -- the EL1014s restart the alias sequence
    assert names[(5, 5)] == "BL21I-VA-E1RIO-05:24VDI01"
    # legacy BL21I-VA-ERIO-04:MOD1 -- 1st coupler, so ERIO-04 becomes E1RIO-01
    assert names[(1, 1)] == "BL21I-VA-E1RIO-01:10VAI01"


def test_alias_sequence_is_per_coupler_not_per_chain():
    """Each coupler restarts the per-alias numbering."""
    names = predict_names(I21_VA_IOC_01, DLS_MAPPINGS, root_id=ROOT_ID)
    assert names[(1, 1)] == "BL21I-VA-E1RIO-01:10VAI01"
    assert names[(2, 1)] == "BL21I-VA-E1RIO-02:10VAI01"
    assert names[(3, 1)] == "BL21I-VA-E1RIO-03:10VAI01"


def test_coupler_is_position_zero():
    """A coupler sits at position 0; its first terminal is position 1."""
    chain = predict_chain(["EK1100", "EL3104"], DLS_MAPPINGS, root_id=ROOT_ID)
    assert chain[(1, 0)].category == "coupler"
    assert chain[(1, 0)].prefix == "BL21I-VA-E1RIO-01"
    assert chain[(1, 1)].category == "slave"


def test_leading_ek1110_burns_a_position():
    """An EK1110 before the first coupler reserves the unreported EK1200 slot."""
    chain = predict_chain(["EK1110", "EK1100", "EL3104"], DLS_MAPPINGS, strict=False)
    assert (0, 1) in chain  # the EK1110, shifted off position 0
    assert chain[(1, 1)].type_name == "EL3104"


def test_group_aliases_of_the_i21_terminal_types():
    """Locks the aliases the I21 substitution table is built on."""
    aliases = {
        t: get_terminal_type(t).group_alias
        for t in ("EL3104", "EL1014", "EL2024-0010", "EL3356-0010")
    }
    assert aliases == {
        "EL3104": "10VAI",
        "EL1014": "24VDI",
        "EL2024-0010": "12VDO",
        "EL3356-0010": "AI",
    }


def test_revision_is_ignored_for_alias_lookup():
    """I21 declares revisions the YAML does not carry; the alias must survive."""
    declared = predict_names(
        [ChainEntry("EK1100", 0x00120000), ChainEntry("EL3104", 0x00130000)],
        DLS_MAPPINGS,
        root_id=ROOT_ID,
    )
    assert declared[(1, 1)] == "BL21I-VA-E1RIO-01:10VAI01"


def test_unknown_terminal_type_raises_in_strict_mode():
    with pytest.raises(UnknownTerminalTypeError, match="EL9999"):
        predict_names(["EK1100", "EL9999"], DLS_MAPPINGS, root_id=ROOT_ID)


def test_unknown_terminal_type_falls_back_to_mod_when_not_strict():
    """Matches the runtime, which renders an unrecognised identity as MOD."""
    names = predict_names(["EK1100", "EL9999"], DLS_MAPPINGS, strict=False)
    assert names[(1, 1)] == "BL21I-VA-E1RIO-01:MOD01"


def test_absolute_node_prefix_keeps_the_path_short_enough_to_avoid_shortening():
    """The DLS templates must not push attribute names past the EPICS budget.

    With the library default ``node_prefix`` the module path gains two extra
    segments, the per-attribute budget collapses, and ``shorten_fastcs_name``
    truncates ``ai_standard_channel_1_value`` to ``ai_std_ch`` -- dropping the
    channel number and colliding all four EL3104 channels onto one name.
    """
    from catio_terminals.utils import shorten_fastcs_name
    from fastcs_catio.utils import max_attribute_name_length

    prefix = predict_names(I21_VA_IOC_01, DLS_MAPPINGS, root_id=ROOT_ID)[(5, 1)]
    budget = max_attribute_name_length(prefix.split(":"), is_rw=False)
    name = "ai_standard_channel_1_value"
    assert shorten_fastcs_name(name, budget) == name
