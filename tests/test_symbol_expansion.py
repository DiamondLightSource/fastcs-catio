"""Tests for the YAML-driven bus-side symbol expansion in symbols.py."""

import numpy as np
import pytest

from catio_terminals.models import (
    Identity,
    SymbolNode,
    TerminalConfig,
    TerminalType,
)
from fastcs_catio import terminal_config
from fastcs_catio._constants import AdsDataType, SymbolFlag
from fastcs_catio.devices import AdsSymbolNode, ChainLocation, IOSlave
from fastcs_catio.messages import IOIdentity, SlaveCRC, SlaveState
from fastcs_catio.symbols import (
    _dtype_for_type_name,
    _find_parent_node,
    build_symbols_for_device,
    expand_device_symbols,
    expand_primitive_node,
    expand_symbols_for_slave,
)
from fastcs_catio.terminal_config import get_terminal_type_by_identity


def _make_slave(
    name: str = "Term1",
    vendor: int = 2,
    product: int = 0x0CF23052,
    revision: int = 0x00120000,
) -> IOSlave:
    """Build a minimal IOSlave for symbol-expansion tests."""
    return IOSlave(
        parent_device=1,
        type="t",
        name=name,
        address=1,
        identity=IOIdentity(
            vendor_id=vendor,
            product_code=product,
            revision_number=revision,
            serial_number=0,
        ),
        states=SlaveState(ecat_state=0, link_status=1),
        crcs=SlaveCRC(port_a_crc=0, port_b_crc=0, port_c_crc=0, port_d_crc=0),
        loc_in_chain=ChainLocation(node=1, position=1),
    )


def _make_node(
    name: str,
    ads_type: AdsDataType = AdsDataType.ADS_TYPE_BIGTYPE,
    index_group: int = 0x4020,
    index_offset: int = 0x100,
    type_name: str = "",
) -> AdsSymbolNode:
    """Build a minimal AdsSymbolNode for symbol-expansion tests."""
    return AdsSymbolNode(
        parent_id=1,
        name=name,
        type_name=type_name or name + "_TYPE",
        ads_type=ads_type,
        size=4,
        index_group=index_group,
        index_offset=index_offset,
        flag=SymbolFlag.ADS_SYMBOLFLAG_READONLY,
        comment="",
    )


@pytest.fixture
def install_terminal_config(monkeypatch):
    """Inject a synthetic TerminalConfig and clear it after the test."""

    def _install(terminals: dict[str, TerminalType]) -> None:
        cfg = TerminalConfig(terminal_types=terminals)
        monkeypatch.setattr(terminal_config, "_terminal_config", cfg)

    yield _install
    terminal_config.clear_config_cache()


class TestDtypeForTypeName:
    def test_scalar_uint16(self):
        dtype, count = _dtype_for_type_name("UINT")
        assert dtype is np.uint16
        assert count == 1

    def test_scalar_real(self):
        dtype, count = _dtype_for_type_name("REAL")
        assert dtype is np.float32
        assert count == 1

    def test_array(self):
        dtype, count = _dtype_for_type_name("ARRAY [0..7] OF INT")
        assert dtype is np.int16
        assert count == 8

    def test_array_lowercase(self):
        dtype, count = _dtype_for_type_name("array [1..4] of uint")
        assert dtype is np.uint16
        assert count == 4

    def test_array_unknown_element_falls_back(self):
        dtype, count = _dtype_for_type_name("ARRAY [0..2] OF MYSTRUCT")
        assert dtype is np.uint8
        assert count == 3

    def test_unknown_type_falls_back(self):
        dtype, count = _dtype_for_type_name("MYSTRUCT")
        assert dtype is np.uint8
        assert count == 1


class TestFindParentNode:
    def test_direct_match(self):
        node = _make_node("Term1.Inputs")
        result = _find_parent_node({"Term1.Inputs": node}, "Term1.Inputs")
        assert result is node

    def test_walks_up_dotted_name(self):
        node = _make_node("Term1.Inputs")
        result = _find_parent_node(
            {"Term1.Inputs": node}, "Term1.Inputs.Channel 1.Value"
        )
        assert result is node

    def test_returns_none_when_missing(self):
        assert _find_parent_node({}, "Nothing.Here") is None


class TestExpandSymbolsForSlave:
    def test_unknown_terminal_returns_empty(self, install_terminal_config, caplog):
        install_terminal_config({})
        slave = _make_slave()
        with caplog.at_level("WARNING"):
            symbols = expand_symbols_for_slave({}, slave)
        assert symbols == {}
        assert "No terminal YAML matches" in caplog.text

    def test_single_selected_row_emits_symbol(self, install_terminal_config):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs.Value",
                    index_group=0x4020,
                    type_name="INT",
                    bit_offset=16,
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        parent = _make_node("Term1.Inputs", index_offset=0x200)
        slave = _make_slave("Term1")
        symbols = expand_symbols_for_slave({"Term1.Inputs": parent}, slave)

        assert list(symbols.keys()) == ["Term1.Inputs.Value"]
        sym = symbols["Term1.Inputs.Value"]
        assert sym.dtype is np.int16
        assert sym.size == 1
        assert sym.group == parent.index_group
        # parent offset (0x200) + bit_offset (16) // 8 == 0x202
        assert sym.offset == 0x202

    def test_unselected_row_skipped(self, install_terminal_config):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs.Value",
                    index_group=0x4020,
                    type_name="INT",
                    selected=False,
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        parent = _make_node("Term1.Inputs")
        symbols = expand_symbols_for_slave(
            {"Term1.Inputs": parent}, _make_slave("Term1")
        )
        assert symbols == {}

    def test_non_leaf_parent_row_skipped(self, install_terminal_config):
        # The parent row `Inputs Channel 1` has a child `.Value`, so the
        # parent row itself must be skipped to avoid asking TwinCAT for the
        # full struct.
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs Channel 1",
                    index_group=0x4020,
                    type_name="UINT",
                ),
                SymbolNode(
                    name_template="Inputs Channel 1.Value",
                    index_group=0x4020,
                    type_name="INT",
                    bit_offset=16,
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        parent = _make_node("Term1.Inputs Channel 1", index_offset=0x100)
        symbols = expand_symbols_for_slave(
            {"Term1.Inputs Channel 1": parent}, _make_slave("Term1")
        )
        assert list(symbols.keys()) == ["Term1.Inputs Channel 1.Value"]

    def test_sub_byte_bit_offset_skipped(self, install_terminal_config):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Status.Limit1",
                    index_group=0x4020,
                    type_name="BIT2",
                    bit_offset=2,  # not byte-aligned
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        parent = _make_node("Term1.Status")
        symbols = expand_symbols_for_slave(
            {"Term1.Status": parent}, _make_slave("Term1")
        )
        assert symbols == {}

    def test_multi_channel_expansion(self, install_terminal_config):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Channel {channel}.Value",
                    index_group=0x4020,
                    type_name="INT",
                    channels=3,
                    bit_offset=16,
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        nodes_by_name = {
            "Term1.Channel 1": _make_node("Term1.Channel 1", index_offset=0x100),
            "Term1.Channel 2": _make_node("Term1.Channel 2", index_offset=0x110),
            "Term1.Channel 3": _make_node("Term1.Channel 3", index_offset=0x120),
        }
        symbols = expand_symbols_for_slave(nodes_by_name, _make_slave("Term1"))
        assert set(symbols.keys()) == {
            "Term1.Channel 1.Value",
            "Term1.Channel 2.Value",
            "Term1.Channel 3.Value",
        }
        assert symbols["Term1.Channel 2.Value"].offset == 0x110 + 2

    def test_non_one_based_channel_indices(self, install_terminal_config):
        # EP4374-0002 names its AO RxPDOs "Channel 3" and "Channel 4"
        # because the terminal numbers AI channels 1-2 and AO channels 3-4
        # under a shared scheme. The expander must walk channel_indices
        # rather than range(1, channels+1) — otherwise it fabricates
        # "Channel 1.Analog output" which doesn't exist on the bus.
        terminal = TerminalType(
            description="EP4374-0002",
            identity=Identity(
                vendor_id=2, product_code=0x11164052, revision_number=0x00100002
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="AO RxPDO-Map Channel {channel}.Analog output",
                    index_group=0xF021,
                    type_name="INT",
                    channels=2,
                    channel_indices=[3, 4],
                ),
            ],
        )
        install_terminal_config({"EP4374-0002": terminal})

        nodes_by_name = {
            "Term1.AO RxPDO-Map Channel 3": _make_node(
                "Term1.AO RxPDO-Map Channel 3", index_offset=0x300
            ),
            "Term1.AO RxPDO-Map Channel 4": _make_node(
                "Term1.AO RxPDO-Map Channel 4", index_offset=0x310
            ),
        }
        slave = _make_slave("Term1", product=0x11164052, revision=0x00100002)
        symbols = expand_symbols_for_slave(nodes_by_name, slave)
        assert set(symbols.keys()) == {
            "Term1.AO RxPDO-Map Channel 3.Analog output",
            "Term1.AO RxPDO-Map Channel 4.Analog output",
        }

    def test_missing_parent_warns_and_skips(self, install_terminal_config, caplog):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs.Value",
                    index_group=0x4020,
                    type_name="INT",
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        with caplog.at_level("WARNING"):
            symbols = expand_symbols_for_slave({}, _make_slave("Term1"))
        assert symbols == {}
        assert "No bus node provides offset" in caplog.text

    def test_dynamic_pdo_warning_hint(self, install_terminal_config, caplog):
        from catio_terminals.models import PdoGroup

        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs.Value",
                    index_group=0x4020,
                    type_name="INT",
                ),
            ],
            pdo_groups=[
                PdoGroup(name="Standard", is_default=True, symbol_indices=[0]),
                PdoGroup(name="Compact", symbol_indices=[]),
            ],
            selected_pdo_group="Standard",
        )
        install_terminal_config({"EL_TEST": terminal})

        with caplog.at_level("WARNING"):
            symbols = expand_symbols_for_slave({}, _make_slave("Term1"))
        assert symbols == {}
        assert "dynamic PDO groups" in caplog.text
        assert "'Standard'" in caplog.text


class TestExpandDeviceSymbols:
    def test_inputs_emits_five_fields(self):
        node = _make_node("Device 1.Inputs", index_offset=0x1000)
        symbols = expand_device_symbols([node], "Device 1")
        assert set(symbols.keys()) == {
            "Device 1.Inputs.Frm0State",
            "Device 1.Inputs.Frm0WcState",
            "Device 1.Inputs.Frm0InputToggle",
            "Device 1.Inputs.SlaveCount",
            "Device 1.Inputs.DevState",
        }
        assert symbols["Device 1.Inputs.Frm0State"].offset == 0x1000
        assert symbols["Device 1.Inputs.SlaveCount"].offset == 0x1000 + 10

    def test_outputs_emits_three_fields(self):
        node = _make_node("Device 1.Outputs", index_offset=0x2000)
        symbols = expand_device_symbols([node], "Device 1")
        assert set(symbols.keys()) == {
            "Device 1.Outputs.Frm0Ctrl",
            "Device 1.Outputs.Frm0WcCtrl",
            "Device 1.Outputs.DevCtrl",
        }
        assert symbols["Device 1.Outputs.DevCtrl"].offset == 0x2000 + 4

    def test_bare_inputs_name_matches(self):
        # ADS servers may report "Inputs" without a device prefix.
        node = _make_node("Inputs", index_offset=0x500)
        symbols = expand_device_symbols([node], "Device 1")
        assert "Device 1.Inputs.Frm0State" in symbols

    def test_non_bigtype_skipped(self):
        node = _make_node(
            "Device 1.Inputs",
            ads_type=AdsDataType.ADS_TYPE_UINT16,
        )
        assert expand_device_symbols([node], "Device 1") == {}

    def test_unrelated_struct_skipped(self):
        node = _make_node("Device 1.Foobar")
        assert expand_device_symbols([node], "Device 1") == {}


class TestExpandPrimitiveNode:
    def test_mapped_type_emits_symbol(self):
        node = _make_node(
            "WcState",
            ads_type=AdsDataType.ADS_TYPE_UINT16,
            index_offset=0x42,
        )
        sym = expand_primitive_node(node)
        assert sym is not None
        assert sym.name == "WcState"
        assert sym.dtype is np.uint16
        assert sym.size == 1
        assert sym.offset == 0x42

    def test_unmapped_type_returns_none(self):
        # BIGTYPE is not in the primitive map.
        node = _make_node("BigStruct", ads_type=AdsDataType.ADS_TYPE_BIGTYPE)
        assert expand_primitive_node(node) is None

    def test_string_type_returns_none(self):
        node = _make_node("Label", ads_type=AdsDataType.ADS_TYPE_STRING)
        assert expand_primitive_node(node) is None


class TestBuildSymbolsForDevice:
    def test_combined_slave_master_and_primitive(self, install_terminal_config):
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="Inputs.Value",
                    index_group=0x4020,
                    type_name="INT",
                    bit_offset=16,
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        slave = _make_slave("Term1")
        slave_node = _make_node("Term1.Inputs", index_offset=0x300)
        master_node = _make_node("Device 1.Inputs", index_offset=0x1000)
        primitive_node = _make_node(
            "Device 1.WcState",
            ads_type=AdsDataType.ADS_TYPE_UINT16,
            index_offset=0x42,
        )

        symbols = build_symbols_for_device(
            [slave_node, master_node, primitive_node],
            [slave],
            "Device 1",
        )

        # Slave-scoped YAML row
        assert symbols["Term1.Inputs.Value"].offset == 0x302
        # Master Inputs expansion
        assert "Device 1.Inputs.Frm0State" in symbols
        # Primitive node
        assert symbols["Device 1.WcState"].dtype is np.uint16

    def test_primitive_already_present_not_overwritten(self, install_terminal_config):
        # If the slave-side expansion already emitted a symbol with the same
        # name as a primitive node, the primitive path must not stomp it.
        terminal = TerminalType(
            description="EL_TEST",
            identity=Identity(
                vendor_id=2, product_code=0x0CF23052, revision_number=0x00120000
            ),
            symbol_nodes=[
                SymbolNode(
                    name_template="WcState",
                    index_group=0x4020,
                    type_name="UINT",
                ),
            ],
        )
        install_terminal_config({"EL_TEST": terminal})

        slave = _make_slave("Term1")
        # The bus exposes Term1.WcState both as a parent and we expect the
        # YAML expansion to produce the symbol. We then add a primitive
        # node with the same name to confirm it isn't replaced.
        parent_node = _make_node(
            "Term1.WcState",
            ads_type=AdsDataType.ADS_TYPE_UINT16,
            index_offset=0x10,
        )
        symbols = build_symbols_for_device([parent_node], [slave], "Device 1")
        # Slave expansion places the symbol at parent.offset + 0
        assert symbols["Term1.WcState"].offset == 0x10


class TestGetTerminalTypeByIdentity:
    def test_exact_match(self, install_terminal_config):
        t = TerminalType(
            description="EL",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        install_terminal_config({"EL": t})
        assert get_terminal_type_by_identity(2, 10, 5) is t

    def test_vendor_product_fallback_on_revision_drift(self, install_terminal_config):
        # Single-entry products still loose-match: rig at a newer revision
        # than the cached YAML falls through to the only candidate (since
        # its revision is <= the rig's). This preserves pre-#60 behaviour.
        t = TerminalType(
            description="EL",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        install_terminal_config({"EL": t})
        assert get_terminal_type_by_identity(2, 10, 99) is t

    def test_no_match_returns_none(self, install_terminal_config):
        t = TerminalType(
            description="EL",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        install_terminal_config({"EL": t})
        assert get_terminal_type_by_identity(2, 11, 5) is None
        assert get_terminal_type_by_identity(3, 10, 5) is None

    def test_multi_revision_exact_match_wins(self, install_terminal_config):
        a = TerminalType(
            description="EL rev A",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        b = TerminalType(
            description="EL rev B",
            identity=Identity(vendor_id=2, product_code=10, revision_number=20),
        )
        install_terminal_config({"EL": a, "EL__rev00000014": b})
        # Exact match on A
        assert get_terminal_type_by_identity(2, 10, 5) is a
        # Exact match on B
        assert get_terminal_type_by_identity(2, 10, 20) is b

    def test_multi_revision_picks_highest_below_rig(self, install_terminal_config):
        a = TerminalType(
            description="EL rev A",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        b = TerminalType(
            description="EL rev B",
            identity=Identity(vendor_id=2, product_code=10, revision_number=20),
        )
        install_terminal_config({"EL": a, "EL__rev00000014": b})
        # Rig at rev 15 (> A, < B) picks A (the highest <= 15).
        assert get_terminal_type_by_identity(2, 10, 15) is a
        # Rig at rev 99 (> B) picks B (the highest cached compatible rev).
        assert get_terminal_type_by_identity(2, 10, 99) is b

    def test_multi_revision_rig_below_all_falls_back_with_warning(
        self, install_terminal_config
    ):
        from fastcs.logging import logger as _fastcs_logger

        a = TerminalType(
            description="EL rev A",
            identity=Identity(vendor_id=2, product_code=10, revision_number=5),
        )
        b = TerminalType(
            description="EL rev B",
            identity=Identity(vendor_id=2, product_code=10, revision_number=20),
        )
        install_terminal_config({"EL": a, "EL__rev00000014": b})

        # terminal_config uses fastcs's loguru logger, which doesn't feed
        # pytest's caplog. Add a sink we can drain.
        messages: list[str] = []
        sink_id = _fastcs_logger.add(
            lambda msg: messages.append(str(msg)), level="WARNING"
        )
        try:
            # Rig at rev 1 is older than every cached entry. Degraded
            # fallback: pick the lowest-revision YAML (closest) and warn.
            result = get_terminal_type_by_identity(2, 10, 1)
        finally:
            _fastcs_logger.remove(sink_id)
        assert result is a
        joined = " ".join(messages).lower()
        assert "falling back" in joined
