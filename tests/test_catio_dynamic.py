"""Tests for dynamic controller generation from YAML terminal definitions."""

import pytest

from catio_terminals.models import SymbolNode
from fastcs_catio.catio_controller import CATioTerminalController
from fastcs_catio.catio_dynamic import (
    clear_controller_cache,
    get_terminal_controller_class,
)
from fastcs_catio.terminal_config import symbol_to_ads_name, symbol_to_fastcs_name


class TestSymbolNameConversion:
    """Tests for symbol name conversion functions."""

    def test_fastcs_name_with_template(self) -> None:
        """Test fastcs_name with channel placeholder."""
        symbol = SymbolNode(
            name_template="Channel {channel}",
            index_group=61489,
            type_name="InputBits",
            channels=4,
            fastcs_name="channel_{channel}",
        )
        assert symbol_to_fastcs_name(symbol, 1) == "channel_1"
        assert symbol_to_fastcs_name(symbol, 2) == "channel_2"

    def test_ads_name_with_channel(self) -> None:
        """Test ADS name conversion with channel placeholder."""
        symbol = SymbolNode(
            name_template="Channel {channel}",
            index_group=61489,
            type_name="InputBits",
            channels=4,
        )
        assert symbol_to_ads_name(symbol, 1) == "Channel 1"
        assert symbol_to_ads_name(symbol, 4) == "Channel 4"

    def test_ads_name_without_channel(self) -> None:
        """Test ADS name conversion without channel placeholder."""
        symbol = SymbolNode(
            name_template="WcState",
            index_group=61489,
            type_name="UINT",
            channels=1,
        )
        assert symbol_to_ads_name(symbol) == "WcState"


class TestGetTerminalControllerClass:
    """Tests for the controller factory function."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_controller_cache()

    def test_get_el1004_controller(self) -> None:
        """Test getting a controller class for EL1004."""
        controller_class = get_terminal_controller_class("EL1004")

        # Check it's a subclass of CATioTerminalController
        assert issubclass(controller_class, CATioTerminalController)

        # Check the class name
        assert controller_class.__name__ == "DynamicEL1004Controller"

        # Check io_function is set
        assert hasattr(controller_class, "io_function")
        assert "Dig. Input" in controller_class.io_function  # type: ignore[attr-defined]

    def test_controller_caching(self) -> None:
        """Test that controller classes are cached."""
        controller_class1 = get_terminal_controller_class("EL1004")
        controller_class2 = get_terminal_controller_class("EL1004")

        # Should be the exact same class object
        assert controller_class1 is controller_class2

    def test_unknown_terminal_raises_keyerror(self) -> None:
        """Test that unknown terminal types raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_terminal_controller_class("UNKNOWN_TERMINAL")

        assert "UNKNOWN_TERMINAL" in str(exc_info.value)

    def test_clear_cache(self) -> None:
        """Test that clearing the cache works."""
        controller_class1 = get_terminal_controller_class("EL1004")
        clear_controller_cache()
        controller_class2 = get_terminal_controller_class("EL1004")

        # Should be different class objects after cache clear
        assert controller_class1 is not controller_class2


class TestDynamicControllerAttributes:
    """Tests for attributes created by dynamic controllers."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        clear_controller_cache()

    def test_el1004_has_selected_symbols(self) -> None:
        """Test that EL1004 dynamic controller has selected symbols."""
        controller_class = get_terminal_controller_class("EL1004")

        # Check that _selected_symbols class attribute exists
        assert hasattr(controller_class, "_selected_symbols")
        symbols = controller_class._selected_symbols  # type: ignore[attr-defined]

        # EL1004 should have channel symbols selected
        assert len(symbols) > 0

        # Check the first symbol has expected attributes
        first_symbol = symbols[0]
        assert hasattr(first_symbol, "name_template")
        assert hasattr(first_symbol, "channels")

    def test_el1004_has_get_io_attributes_method(self) -> None:
        """Test that dynamic controller has get_io_attributes method."""
        controller_class = get_terminal_controller_class("EL1004")

        # Check that get_io_attributes method exists
        assert hasattr(controller_class, "get_io_attributes")
        assert callable(controller_class.get_io_attributes)

    def test_el1004_terminal_id_stored(self) -> None:
        """Test that dynamic controller stores terminal_id."""
        controller_class = get_terminal_controller_class("EL1004")

        # Check that _terminal_id class attribute is set
        assert hasattr(controller_class, "_terminal_id")
        assert controller_class._terminal_id == "EL1004"  # type: ignore[attr-defined]

    def test_el1004_has_runtime_symbols(self) -> None:
        """Test that EL1004 dynamic controller has runtime symbols."""
        controller_class = get_terminal_controller_class("EL1004")

        # Check that _runtime_symbols class attribute exists
        assert hasattr(controller_class, "_runtime_symbols")
        runtime_symbols = controller_class._runtime_symbols  # type: ignore[attr-defined]

        # EL1004 is a DigIn terminal, should have WcState and InputToggle
        assert len(runtime_symbols) >= 2

        # Check runtime symbol names
        symbol_names = [s.name_template for s in runtime_symbols]
        assert "WcState.WcState" in symbol_names
        assert "WcState.InputToggle" in symbol_names
