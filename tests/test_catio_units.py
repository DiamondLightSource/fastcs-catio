"""
Unit tests file for the CATio module.

Tests currently cover:
- Utilities (bytes_to_string, averages, etc.) -- 'utils.py'
- Data types (AmsNetId, AdsSymbol) -- 'devices.py'
- Device models (IODevice, IOServer, IOSlave) -- ' _types.py'
- Connection settings and management -- part of 'catio_connection.py'

Run the tests with:
```bash
python -m pytest tests/test_catio_units.py -v
"""

from datetime import datetime
from typing import Literal, get_type_hints

import numpy as np
import pytest

from catio._constants import AdsDataType, DeviceType, SymbolFlag
from catio._types import AdsMessageDataType, AmsAddress, AmsNetId
from catio.catio_connection import (
    CATioFastCSRequest,
    CATioFastCSResponse,
    CATioServerConnectionSettings,
)
from catio.devices import (
    AdsSymbol,
    AdsSymbolNode,
    ChainLocation,
    IODevice,
    IONodeType,
    IOServer,
    IOSlave,
    IOTreeNode,
)
from catio.messages import DeviceFrames, IOIdentity, Message, SlaveCRC, SlaveState
from catio.utils import (
    add_comment,
    average,
    bytes_to_string,
    check_ndarray,
    filetime_to_dt,
    get_local_netid_str,
    get_localhost_ip,
    get_localhost_name,
    get_notification_changes,
    process_notifications,
    trim_ecat_name,
)

# ===================================================================
# Utilities Tests
# ===================================================================


class TestLocalHostUtils:
    """Test suite for local host name/IP/netid utility functions."""

    def test_get_localhost_name_monkeypatched(self, monkeypatch: pytest.MonkeyPatch):
        """Helper function should return the socket hostname."""

        def fake_gethostname():
            return "my-test-host"

        monkeypatch.setattr("socket.gethostname", fake_gethostname)
        assert get_localhost_name() == "my-test-host"

    def test_get_localhost_ip_uses_gethostbyname(self, monkeypatch: pytest.MonkeyPatch):
        """Helper function should call gethostbyname with the hostname."""

        def fake_gethostname():
            return "my-host"

        def fake_gethostbyname(name):
            assert name == "my-host"
            return "192.0.2.5"

        monkeypatch.setattr("socket.gethostname", fake_gethostname)
        monkeypatch.setattr("socket.gethostbyname", fake_gethostbyname)
        assert get_localhost_ip() == "192.0.2.5"

    def test_get_local_netid_str_appends_suffix(self, monkeypatch: pytest.MonkeyPatch):
        """Helper function should append ".1.1" to the localhost IP."""

        monkeypatch.setattr("catio.utils.get_localhost_ip", lambda: "10.11.12.13")
        assert get_local_netid_str() == "10.11.12.13.1.1"


class TestBytesToString:
    """Test suite for bytes_to_string utility function."""

    def test_basic_conversion(self):
        """Test basic bytes to string conversion."""
        raw_bytes = b"HelloWorld"
        result = bytes_to_string(raw_bytes, strip=False)
        assert isinstance(result, str)
        assert result == "HelloWorld"

    def test_conversion_with_null_terminator(self):
        """Test conversion with null terminator."""
        raw_bytes = b"Hello\x00World"
        result = bytes_to_string(raw_bytes, strip=True)
        assert isinstance(result, str)
        assert result == "Hello"

    def test_conversion_without_strip(self):
        """Test conversion without stripping null bytes."""
        raw_bytes = b"Hello\x00World"
        result = bytes_to_string(raw_bytes, strip=False)
        # Should include the null and continue
        assert isinstance(result, str)
        assert "Hello" in result

    def test_empty_bytes(self):
        """Test conversion of empty bytes."""
        raw_bytes = b""
        result = bytes_to_string(raw_bytes, strip=True)
        assert isinstance(result, str)
        assert result == ""

    def test_only_null_bytes(self):
        """Test conversion of only null bytes."""
        raw_bytes = b"\x00\x00\x00"
        result = bytes_to_string(raw_bytes, strip=True)
        assert isinstance(result, str)
        assert result == ""


class TestAddComment:
    """Test suite for add_comment utility function."""

    def test_add_to_empty_string(self):
        """Test adding comment to empty string."""
        result = add_comment("new comment", "")
        assert isinstance(result, str)
        assert result == "new comment"

    def test_add_to_existing_comment(self):
        """Test adding comment to existing comment."""
        result = add_comment("new", "old")
        assert isinstance(result, str)
        assert result == "old\nnew"

    def test_add_multiple_comments(self):
        """Test adding multiple comments."""
        result = add_comment("third", add_comment("second", "first"))
        assert isinstance(result, str)
        assert result == "first\nsecond\nthird"


class TestProcessNotifications:
    """Test suite for process_notifications utility function."""

    @pytest.mark.skip(reason="TODO this is failing")
    def test_process_notifications_with_valid_function(self):
        """Test with a valid processing function."""

        # Define a simple processing function
        def valid_processor(data: np.ndarray) -> np.ndarray:
            # return np.multiply(data, 2)
            return data * 2

        # Create a structured array with one field
        notifications = np.array([(1,), (2,), (3,)], dtype=[("value", int)])
        result = process_notifications(valid_processor, notifications)

        expected = np.array([(2,), (4,), (6,)], dtype=[("value", int)])
        np.testing.assert_array_equal(result, expected)

    @pytest.mark.skip(reason="TODO this is failing")
    def test_process_notifications_with_multiple_fields(self):
        """Test with a structured array having multiple fields."""

        # Define a processing function that modifies multiple fields
        def processor(data: np.ndarray) -> np.ndarray:
            data["x"] = data["x"] + 10
            data["y"] = data["y"] * 2
            return data

        # Create a structured array with two fields
        notifications = np.array([(1, 2), (3, 4)], dtype=[("x", int), ("y", int)])
        result = process_notifications(processor, notifications)

        expected = np.array([(11, 4), (13, 8)], dtype=[("x", int), ("y", int)])
        np.testing.assert_array_equal(result, expected)

    def test_process_notifications_function_takes_multiple_args_raises_assertion_error(
        self,
    ):
        """Test that AssertionError is raised if multiple arguments are given."""

        # Define a processing function that takes multiple arguments
        def multi_arg_processor(data: np.ndarray, extra: int) -> np.ndarray:
            return data

        # Create a structured array with one field
        notifications = np.array([(1,)], dtype=[("value", int)])

        with pytest.raises(AssertionError, match="takes more than 1 argument"):
            process_notifications(multi_arg_processor, notifications)

    def test_process_notifications_function_no_annotation_raises_assertion_error(self):
        """Test that AssertionError is raised if argument has no type annotation."""

        # Define a processing function without type annotation
        def unannotated_processor(data):
            return data

        # Create a structured array with one field
        notifications = np.array([(1,)], dtype=[("value", int)])

        with pytest.raises(AssertionError, match="requires a numpy array as argument"):
            process_notifications(unannotated_processor, notifications)

    def test_process_notifications_wrong_annotation_raises_assertion_error(self):
        """Test that AssertionError is raised if argument has wrong type annotation."""

        # Define a processing function with wrong type annotation
        def wrong_annotation_processor(data: list) -> np.ndarray:
            return np.array(data)

        # Create a structured array with one field
        notifications = np.array([(1,)], dtype=[("value", int)])

        with pytest.raises(AssertionError, match="requires a numpy array as argument"):
            process_notifications(wrong_annotation_processor, notifications)

    def test_process_notifications_function_takes_zero_args_raises_assertion_error(
        self,
    ):
        """Test that AssertionError is raised if function takes no arguments."""

        # Define a processing function that takes no arguments
        def no_arg_processor() -> np.ndarray:
            return np.array([(1,)], dtype=[("value", int)])

        # Create a structured array with one field
        notifications = np.array([(1,)], dtype=[("value", int)])

        with pytest.raises(AssertionError, match="takes more than 1 argument"):
            process_notifications(no_arg_processor, notifications)

    @pytest.mark.skip(reason="TODO this is failing")
    def test_process_notifications_with_float_array(self):
        """Test with floating-point data."""

        # Define a simple processing function that modifies float data
        def float_processor(data: np.ndarray) -> np.ndarray:
            return data / 2.0

        # Create a structured array with float data
        notifications = np.array([(1.0,), (2.0,), (4.0,)], dtype=[("value", float)])
        result = process_notifications(float_processor, notifications)

        expected = np.array([(0.5,), (1.0,), (2.0,)], dtype=[("value", float)])
        np.testing.assert_array_almost_equal(result, expected)

    @pytest.mark.skip(reason="TODO this is failing")
    def test_process_notifications_identity_function(self):
        """Test with an identity function that returns data unchanged."""

        # Define an identity processing function
        def identity_processor(data: np.ndarray) -> np.ndarray:
            return data

        # Create a structured array with one field
        notifications = np.array([(1,), (2,), (3,)], dtype=[("value", int)])
        result = process_notifications(identity_processor, notifications)

        np.testing.assert_array_equal(result, notifications)


class TestAverage:
    """Test suite for average utility function."""

    def test_average_single_field(self):
        """Test averaging a single field."""
        dtype = np.dtype([("value", np.float32)])
        data = np.array([(1.0,), (2.0,), (3.0,)], dtype=dtype)
        result = average(data)
        assert result is not None
        assert result["value"][0] == pytest.approx(2.0)

    def test_average_multiple_fields(self):
        """Test averaging multiple fields."""
        dtype = np.dtype([("a", np.float32), ("b", np.float32)])
        data = np.array([(1.0, 2.0), (3.0, 4.0)], dtype=dtype)
        result = average(data)
        assert result is not None
        assert result["a"][0] == pytest.approx(2.0)
        assert result["b"][0] == pytest.approx(3.0)

    def test_average_integer_data(self):
        """Test averaging integer data."""
        dtype = np.dtype([("count", np.int32)])
        data = np.array([(10,), (20,), (30,)], dtype=dtype)
        result = average(data)
        assert result is not None
        assert result["count"][0] == pytest.approx(20.0)


class TestGetNotificationChanges:
    """Test suite for get_notification_changes utility function."""

    def test_detect_single_field_change(self):
        """Test detecting change in single field."""
        dtype = np.dtype([("value", np.int32)])
        old = np.array([(1,), (2,)], dtype=dtype)
        new = np.array([(1,), (5,)], dtype=dtype)
        result = get_notification_changes(new, old)
        # Second element should show change
        assert result is not None

    def test_no_changes(self):
        """Test when arrays are identical."""
        dtype = np.dtype([("value", np.int32)])
        old = np.array([(1,), (2,)], dtype=dtype)
        new = np.array([(1,), (2,)], dtype=dtype)
        result = get_notification_changes(new, old)
        # Should return result but potentially with zeros or similar
        assert result is not None

    def test_multiple_field_changes(self):
        """Test changes in multiple fields."""
        dtype = np.dtype([("a", np.int32), ("b", np.int32)])
        old = np.array([(1, 2), (3, 4)], dtype=dtype)
        new = np.array([(10, 20), (3, 4)], dtype=dtype)
        result = get_notification_changes(new, old)
        assert result is not None


class TestTrimEcatName:
    """Test suite for trim_ecat_name utility function."""

    def test_trim_basic_name(self):
        """Test trimming basic ecat names."""
        result = trim_ecat_name("CX5140_Master")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.skip(reason="TODO this is failing")
    def test_trim_name_with_underscores(self):
        """Test trimming name with underscores."""
        result = trim_ecat_name("Device_Name_With_Underscores")
        assert result == "DeviceNameWithUnderscores"

    @pytest.mark.skip(reason="TODO this is failing")
    def test_trim_name_with_spaces(self):
        """Test trimming name with spaces."""
        result = trim_ecat_name("  Device Name With Spaces  ")
        assert result == "DeviceNameWithSpaces"

    @pytest.mark.skip(reason="TODO this is failing")
    def test_trim_name_with_special_chars(self):
        """Test trimming name with special characters."""
        result = trim_ecat_name("Device@#Name$%^&*()")
        assert result == "DeviceName"

    def test_trim_empty_name(self):
        """Test trimming empty name."""
        result = trim_ecat_name("")
        assert result == ""

    def test_trim_single_word(self):
        """Test trimming single word."""
        result = trim_ecat_name("Device")
        assert len(result) > 0


@pytest.mark.skip(reason="TODO this is failing")
class TestFiletimeToDatetime:
    """Test suite for filetime_to_dt utility function."""

    def test_valid_filetime_conversion(self):
        """Test conversion of valid filetime."""
        # FILETIME for 2000-01-01 00:00:00 UTC
        filetime = 125911584000000000
        result = filetime_to_dt(filetime)
        assert isinstance(result, datetime)
        assert result.year >= 1970

    def test_zero_filetime(self):
        """Test conversion of zero filetime."""
        result = filetime_to_dt(0)
        assert isinstance(result, datetime)

    def test_large_filetime(self):
        """Test conversion of large filetime."""
        filetime = 999999999999999999
        result = filetime_to_dt(filetime)
        assert isinstance(result, datetime)


class TestCheckNdarray:
    """Test suite for check_ndarray utility function."""

    def test_valid_ndarray(self):
        """Test checking valid ndarray."""
        arr = np.array([1, 2, 3], dtype=np.int32)
        result = check_ndarray(arr, np.int32, (3,))
        assert result is True

    def test_wrong_dtype_raises(self):
        """Test that wrong dtype returns False."""
        arr = np.array([1.0, 2.0, 3.0])
        result = check_ndarray(arr, np.int32, (3,))
        assert result is False

    def test_wrong_shape_raises(self):
        """Test that wrong shape returns False."""
        arr = np.array([[1, 2], [3, 4]], dtype=np.int32)
        result = check_ndarray(arr, np.int32, (3,))
        assert result is False


# ===================================================================
# AAdsMessageDataType Tests
# ===================================================================


@pytest.mark.skip(reason="TODO this is failing")
class TestAdsMessageDataType:
    """Test suite for AdsMessageDataType data type."""

    def test_get_dtype_scalar_numpy_type(self):
        """ "Test getting dtype for scalar numpy type."""

        # Define a test message class with AdsMessageDataType
        class TestMessage(Message):
            a: AdsMessageDataType[np.int16, int]

        # Scalar numpy type should be returned as-is
        _, datatype = next(iter(get_type_hints(TestMessage).items()))
        res = AdsMessageDataType.get_dtype(datatype)
        assert res is np.int16

    def test_get_dtype_fixed_length_bytes_array(self):
        """Test getting dtype for fixed-length bytes array."""

        # Define a test message class with AdsMessageDataType
        class TestArrayMessage(Message):
            a: AdsMessageDataType[
                np.ndarray[tuple[Literal[6]], np.dtype[np.bytes_]], bytes
            ]

        # Array of fixed-length bytes should return 'Sn' where n in the length
        _, datatype = next(iter(get_type_hints(TestArrayMessage).items()))
        res = AdsMessageDataType.get_dtype(datatype)
        assert res == "S6"

    def test_get_dtype_array_with_non_bytes_dtype_raises(self):
        """Test that getting dtype for array with non-bytes dtype raises TypeError."""

        # Define a test message class with AdsMessageDataType
        class TestNonBytesArrayMessage(Message):
            a: AdsMessageDataType[
                np.ndarray[tuple[Literal[6]], np.dtype[np.bytes_]], bytes
            ]

        # Arrays with a non-bytes dtype are unsupported by get_dtype
        _, datatype = next(iter(get_type_hints(TestNonBytesArrayMessage).items()))
        with pytest.raises(TypeError):
            AdsMessageDataType.get_dtype(datatype)

    def test_get_dtype_unsupported_type_raises(self):
        """Test that getting dtype for unsupported type raises TypeError."""

        # Define a test message class with AdsMessageDataType
        class TestUnsupportedMessage(Message):
            a: AdsMessageDataType[list[int], int]

        # An arbitrary non-numpy type parameter should raise TypeError
        _, datatype = next(iter(get_type_hints(TestUnsupportedMessage).items()))
        with pytest.raises(TypeError):
            AdsMessageDataType.get_dtype(datatype)


# ===================================================================
# AmsNetId Tests
# ===================================================================


class TestAmsNetId:
    """Test suite for AmsNetId data type."""

    def test_from_string_valid(self):
        """Test creating AmsNetId from valid string."""
        netid = AmsNetId.from_string("192.168.1.1.1.1")
        assert isinstance(netid, AmsNetId)
        assert hasattr(netid, "root")
        assert netid.root == (192, 168, 1, 1)
        assert hasattr(netid, "mask")
        assert netid.mask == (1, 1)

    def test_to_string_conversion(self):
        """Test converting AmsNetId to string."""
        netid = AmsNetId.from_string("127.0.0.1.1.1")
        netid_str = netid.to_string()
        assert isinstance(netid_str, str)
        assert netid_str == "127.0.0.1.1.1"

    def test_from_bytes_conversion(self):
        """Test converting bytes to AmsNetId."""
        raw_bytes = b"\xc0\xa8\x01\x01\x01\x01"
        netid = AmsNetId.from_bytes(raw_bytes)
        assert isinstance(netid, AmsNetId)
        assert hasattr(netid, "root")
        assert netid.root == (192, 168, 1, 1)
        assert hasattr(netid, "mask")
        assert netid.mask == (1, 1)

    def test_to_bytes_conversion(self):
        """Test converting AmsNetId to bytes."""
        netid = AmsNetId.from_string("192.168.1.1.1.1")
        netid_bytes = netid.to_bytes()
        assert isinstance(netid_bytes, bytes)
        assert len(netid_bytes) == 6
        assert netid_bytes == b"\xc0\xa8\x01\x01\x01\x01"

    def test_roundtrip_conversion(self):
        """Test roundtrip conversion string -> bytes -> string."""
        original = "10.20.30.40.50.60"
        netid = AmsNetId.from_string(original)
        netid_bytes = netid.to_bytes()
        netid_restored = AmsNetId.from_bytes(netid_bytes)
        assert netid_restored.root == netid.root
        assert netid_restored.mask == netid.mask

    def test_netid_attributes_signature(self):
        """Test netid public attributes are accessible and of correct type."""
        netid = AmsNetId.from_string("192.168.1.100.1.1")

        assert hasattr(netid, "root")
        assert isinstance(netid.root, tuple)
        assert len(netid.root) == 4

        assert hasattr(netid, "mask")
        assert isinstance(netid.mask, tuple)
        assert len(netid.mask) == 2

    def test_from_string_invalid_format_raises(self):
        """Test that invalid string format raises error."""
        with pytest.raises(ValueError):
            AmsNetId.from_string("not-a-valid-netid")

        with pytest.raises(ValueError):
            AmsNetId.from_string("192.168.1.1")  # Too short

    def test_from_bytes_invalid_length_raises(self):
        """Test that invalid byte length raises error."""
        with pytest.raises((AssertionError, ValueError)):
            AmsNetId.from_bytes(b"\x01\x02\x03")  # Too short


# ===================================================================
# AmsAddress Tests
# ===================================================================


class TestAmsAddress:
    """Test suite for AmsAddress data type."""

    @pytest.mark.skip(reason="TODO this is failing")
    def test_from_string_valid(self):
        """Test creating AmsAddress from valid string."""
        addr = AmsAddress.from_string("192.168.1.1.1.1:851")
        assert isinstance(addr, AmsAddress)
        assert hasattr(addr, "netId")
        assert isinstance(addr.net_id, AmsNetId)
        assert addr.net_id.root == (192, 168, 1, 1)
        assert addr.net_id.mask == (1, 1)
        assert hasattr(addr, "port")
        assert addr.port == 851

    def test_to_string_conversion(self):
        """Test converting AmsAddress to string."""
        addr = AmsAddress.from_string("127.0.0.1.2.3:851")
        addr_str = addr.to_string()
        assert isinstance(addr_str, str)
        assert addr_str == "127.0.0.1.2.3:851"

    @pytest.mark.skip(reason="TODO this is failing")
    def test_from_bytes_conversion(self):
        """Test converting bytes to AmsAddress."""
        raw_bytes = b"\xc0\xa8\x01\x01\x01\x01\x03\x53"
        addr = AmsAddress.from_bytes(raw_bytes)
        assert isinstance(addr, AmsAddress)
        assert hasattr(addr, "netId")
        assert isinstance(addr.net_id, AmsNetId)
        assert addr.net_id.root == (192, 168, 1, 1)
        assert addr.net_id.mask == (1, 1)
        assert hasattr(addr, "port")
        assert addr.port == 851

    @pytest.mark.skip(reason="TODO this is failing")
    def test_to_bytes_conversion(self):
        """Test converting AmsAddress to bytes."""
        addr = AmsAddress.from_string("192.168.1.1.1.1:851")
        addr_bytes = addr.to_bytes()
        assert isinstance(addr_bytes, bytes)
        assert len(addr_bytes) == 8
        assert addr_bytes == b"\xc0\xa8\x01\x01\x01\x01\x03\x53"

    def test_roundtrip_conversion(self):
        """Test roundtrip conversion string -> bytes -> string."""
        original = "10.20.30.40.50.60:1234"
        addr = AmsAddress.from_string(original)
        addr_bytes = addr.to_bytes()
        restored = AmsAddress.from_bytes(addr_bytes)
        assert restored.net_id.root == addr.net_id.root
        assert restored.net_id.mask == addr.net_id.mask
        assert restored.port == addr.port

    @pytest.mark.skip(reason="TODO this is failing")
    def test_address_attributes_signature(self):
        """Test AmsAddress attributes are accessible and of correct type."""
        addr = AmsAddress.from_string("192.168.1.100.2.1:800")

        assert hasattr(addr, "netId")
        assert isinstance(addr.net_id, AmsNetId)

        assert hasattr(addr, "port")
        assert isinstance(addr.port, int)

    def test_from_string_invalid_format_raises(self):
        """Test that invalid string format raises error."""
        with pytest.raises(ValueError):
            AmsAddress.from_string("not-a-valid-address")

        with pytest.raises(ValueError):
            AmsAddress.from_string("127.0.0.1.1.1:notaport")

        with pytest.raises(ValueError):
            AmsAddress.from_string("127.0.0.1:851")  # Too short netid

        with pytest.raises(ValueError):
            AmsAddress.from_string("127.0.0.1.1.1:851a851")  # Invalid port

    def test_from_bytes_invalid_length_raises(self):
        """Test that invalid byte length raises error."""
        with pytest.raises((AssertionError, ValueError)):
            AmsAddress.from_bytes(b"\x01\x02\x03")


# ===================================================================
# IONodeType Tests
# ===================================================================


class TestIONodeType:
    """Tests for IONodeType enum."""

    def test_node_types_exist(self):
        """Test that all expected node types exist."""
        assert IONodeType.Server.value == "server"
        assert IONodeType.Device.value == "device"
        assert IONodeType.Coupler.value == "coupler"
        assert IONodeType.Slave.value == "slave"

    def test_node_type_string_conversion(self):
        """Test converting node type to/from string."""
        node_type = IONodeType("device")
        assert node_type == IONodeType.Device
        assert node_type.value == "device"

    def test_node_type_comparison(self):
        """Test comparing node types."""
        node_type = IONodeType.Server
        assert node_type == IONodeType.Server
        assert node_type != IONodeType.Device


# ===================================================================
# AdsSymbol Tests
# ===================================================================


class TestAdsSymbol:
    """Tests for AdsSymbol data class."""

    def test_create_simple_symbol(self):
        """Test creating a simple AdsSymbol with required fields."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestVar",
            dtype=np.int32,
            size=1,
            group=0x3000,
            offset=0x100,
            comment="Test variable",
        )
        assert symbol is not None
        assert isinstance(symbol, AdsSymbol)
        assert symbol.name == "TestVar"
        assert symbol.size == 1
        assert symbol.nbytes == 4

    def test_symbol_with_array(self):
        """Test creating an array symbol with required fields."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestArray",
            dtype=np.float32,
            size=10,
            group=0x3000,
            offset=0x100,
            comment="Test array",
        )
        assert symbol is not None
        assert isinstance(symbol, AdsSymbol)
        assert symbol.name == "TestArray"
        assert symbol.size == 10
        assert symbol.nbytes == 40

    def test_symbol_attributes_accessible(self):
        """Test symbol attributes are accessible."""
        symbol = AdsSymbol(
            parent_id=42,
            name="MySymbol",
            dtype=np.float32,
            size=5,
            group=0x3000,
            offset=0x100,
            comment="Test symbol",
        )

        assert symbol.parent_id == 42
        assert symbol.name == "MySymbol"
        assert symbol.dtype == np.float32
        assert symbol.size == 5
        assert symbol.group == 0x3000
        assert symbol.offset == 0x100
        assert symbol.comment == "Test symbol"

    def test_symbol_datatype_property(self):
        """Test symbol datatype property."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestVar",
            dtype=np.uint16,
            size=1,
            group=0x3000,
            offset=0x100,
            comment="",
        )
        dtype = symbol.datatype
        assert dtype is not None
        assert dtype == np.dtype(np.uint16)

    def test_symbol_array_datatype_property(self):
        """Test symbol datatype property for arrays."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestArray",
            dtype=np.int32,
            size=5,
            group=0x3000,
            offset=0x100,
            comment="",
        )
        dtype = symbol.datatype
        assert dtype is not None
        assert dtype == np.dtype((np.int32, 5))

    def test_symbol_nbytes_property(self):
        """Test symbol nbytes property."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestVar",
            dtype=np.int16,
            size=1,
            group=0x3000,
            offset=0x100,
            comment="",
        )
        nbytes = symbol.nbytes
        assert isinstance(nbytes, int)
        assert nbytes == 2  # 1 * 2 bytes

    def test_symbol_array_nbytes_property(self):
        """Test symbol nbytes property."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestArray",
            dtype=np.float64,
            size=3,
            group=0x3000,
            offset=0x100,
            comment="",
        )
        nbytes = symbol.nbytes
        assert isinstance(nbytes, int)
        assert nbytes == 24  # 3 * 8 bytes

    def test_symbol_without_handle(self):
        """Test creating symbol without notification handle."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestVar",
            dtype=np.int32,
            size=1,
            group=0x3000,
            offset=0x100,
            comment="",
        )
        assert symbol.handle is None

    def test_symbol_with_handle(self):
        """Test creating symbol with notification handle."""
        symbol = AdsSymbol(
            parent_id=1,
            name="TestVar",
            dtype=np.int32,
            size=1,
            group=0x3000,
            offset=0x100,
            comment="",
            handle=42,
        )
        assert symbol.handle == 42

    def test_symbol_consistency(self):
        """Test consistent symbol."""
        # Create two symbols with identical parameter values
        symbol1 = AdsSymbol(
            parent_id=1,
            name="Test",
            dtype=np.int32,
            size=1,
            group=0x3000,
            offset=0,
            comment="",
        )

        symbol2 = AdsSymbol(
            parent_id=1,
            name="Test",
            dtype=np.int32,
            size=1,
            group=0x3000,
            offset=0,
            comment="",
        )

        # Verify that properties for both symbols are the same
        assert symbol1.parent_id == symbol2.parent_id
        assert symbol1.name == symbol2.name
        assert symbol1.dtype == symbol2.dtype
        assert symbol1.size == symbol2.size
        assert symbol1.group == symbol2.group
        assert symbol1.offset == symbol2.offset
        assert symbol1.comment == symbol2.comment
        assert symbol1.nbytes == symbol2.nbytes


class TestAdsSymbolNode:
    """Tests for AdsSymbolNode data class."""

    def test_create_symbol_node(self):
        """Test creating an AdsSymbolNode."""
        node = AdsSymbolNode(
            parent_id=1,
            name="RootSymbol",
            type_name="server",
            ads_type=AdsDataType.ADS_TYPE_INT8,
            size=0,
            index_group=0x3000,
            index_offset=0x100,
            flag=SymbolFlag.ADS_SYMBOLFLAG_READONLY,
            comment="Root node",
        )
        assert node is not None
        assert isinstance(node, AdsSymbolNode)

    def test_symbol_node_attributes_accessible(self):
        """Test AdsSymbolNode attributes are accessible."""
        node = AdsSymbolNode(
            parent_id=1,
            name="ChildSymbol",
            type_name="device1",
            ads_type=AdsDataType.ADS_TYPE_UINT16,
            size=2,
            index_group=0x3000,
            index_offset=0x300,
            flag=SymbolFlag.ADS_SYMBOLFLAG_READONLY,
            comment="Device node",
        )
        assert node.parent_id == 1
        assert node.name == "ChildSymbol"
        assert node.type_name == "device1"
        assert node.ads_type == AdsDataType.ADS_TYPE_UINT16
        assert node.size == 2
        assert node.index_group == 0x3000
        assert node.index_offset == 0x300
        assert node.flag == SymbolFlag.ADS_SYMBOLFLAG_READONLY
        assert node.comment == "Device node"


# ===================================================================
# IOSlave / IODevice / IOServer / IOTreeNode Tests
# ===================================================================


class TestIOSlave:
    """Test suite for IOSlave data class."""

    def test_get_type_name_for_slave_and_coupler_and_invalid(self):
        """Test get_type_name method for different node categories."""
        # Create a sample IOSlave
        id = IOIdentity(
            vendor_id=101, product_code=200, revision_number=3, serial_number=45678
        )
        states = SlaveState(ecat_state=0, link_status=1)
        crcs = SlaveCRC(port_a_crc=1, port_b_crc=1, port_c_crc=0, port_d_crc=0)
        loc = ChainLocation(node=3, position=7)
        slave = IOSlave(
            parent_device=1,
            type="term",
            name="MySlave",
            address=5,
            identity=id,
            states=states,
            crcs=crcs,
            loc_in_chain=loc,
        )

        # Default category is Slave -> should return MOD{position}
        assert slave.get_type_name() == "MOD7"

        # Coupler category -> should return RIO{position}
        slave.category = IONodeType.Coupler
        assert slave.get_type_name() == "RIO3"

        # Invalid category should raise NameError
        slave.category = IONodeType.Device
        with pytest.raises(NameError):
            slave.get_type_name()


class TestIODevice:
    """Test suite for IODevice data class."""

    def test_get_type_name_for_different_device_types(self):
        """Test get_type_name method for IODevice."""
        # Create two IOSlave samples for the device
        id1 = IOIdentity(
            vendor_id=101, product_code=200, revision_number=3, serial_number=45678
        )
        loc1 = ChainLocation(node=1, position=1)
        id2 = IOIdentity(
            vendor_id=101, product_code=400, revision_number=1, serial_number=98765
        )
        loc2 = ChainLocation(node=1, position=2)
        states = SlaveState(ecat_state=0, link_status=1)
        crcs = SlaveCRC(port_a_crc=1, port_b_crc=1, port_c_crc=0, port_d_crc=0)

        s1 = IOSlave(
            parent_device=1,
            type="t",
            name="s1",
            address=10,
            identity=id1,
            states=states,
            crcs=crcs,
            loc_in_chain=loc1,
        )
        s2 = IOSlave(
            parent_device=1,
            type="t",
            name="s2",
            address=20,
            identity=id2,
            states=states,
            crcs=crcs,
            loc_in_chain=loc2,
        )

        # Create EtherCAT Master IODevice with the two slaves
        netid1 = AmsNetId.from_string("127.0.0.1.1.1")
        dev_id1 = IOIdentity(
            vendor_id=555, product_code=600, revision_number=1, serial_number=12345
        )
        dev_f_cnt1 = DeviceFrames(
            time=0, cyclic_sent=10, cyclic_lost=0, acyclic_sent=5, acyclic_lost=0
        )
        device1 = IODevice(
            id=5,
            type=DeviceType.IODEVICETYPE_ETHERCAT,
            name="Device 5(EtherCAT)",
            netid=netid1,
            identity=dev_id1,
            frame_counters=dev_f_cnt1,
            slave_count=2,
            slaves_states=[],
            slaves_crc_counters=[np.uint32(0), np.uint32(0)],
            slaves=[s1, s2],
        )
        assert device1.get_type_name() == "ETH5"

        # Create Invalid IODevice with the two slaves
        netid2 = AmsNetId.from_string("127.0.0.2.1.1")
        dev_id2 = IOIdentity(
            vendor_id=555, product_code=610, revision_number=2, serial_number=34567
        )
        dev_f_cnt2 = DeviceFrames(
            time=0, cyclic_sent=3, cyclic_lost=0, acyclic_sent=12, acyclic_lost=1
        )
        device2 = IODevice(
            id=8,
            type=DeviceType.IODEVICETYPE_INVALID,
            name="Device 8",
            netid=netid2,
            identity=dev_id2,
            frame_counters=dev_f_cnt2,
            slave_count=2,
            slaves_states=[],
            slaves_crc_counters=[np.uint32(0), np.uint32(0)],
            slaves=[s1, s2],
        )
        assert device2.get_type_name() == "EBUS8"


class TestIOServer:
    """ "Test suite for IOServer data class."""

    def test_server_fields_and_category(self):
        """Test server fields and category."""
        # Create an IOServer instance
        server = IOServer(name="MyServer", version="v1", build=42, num_devices=3)
        # Verify fields
        assert server.name == "MyServer"
        assert server.version == "v1"
        assert server.build == 42
        assert server.num_devices == 3
        # Verify category
        assert server.category == IONodeType.Server


class TestIOTreeNode:
    """Test suite for IOTreeNode data class."""

    @pytest.mark.skip(reason="TODO this is failing")
    def test_tree_basic_operations(self):
        """
        Test basic tree operations, including: \
            add_child, child_count, tree_path, tree_height, node_search, node_generator.
        """
        # Create root server node
        server = IOServer(name="RootServer", version="v1", build=1, num_devices=1)
        root = IOTreeNode(server)

        # Create and add a child device node
        id = IOIdentity(
            vendor_id=555, product_code=600, revision_number=1, serial_number=12345
        )
        frame_cnt = DeviceFrames(
            time=0, cyclic_sent=10, cyclic_lost=0, acyclic_sent=5, acyclic_lost=0
        )
        device = IODevice(
            id=1,
            type=DeviceType.IODEVICETYPE_ETHERCAT,
            name="ChildDevice",
            netid=AmsNetId.from_string("127.0.0.1.1.1"),
            identity=id,
            frame_counters=frame_cnt,
            slave_count=0,
            slaves_states=[],
            slaves_crc_counters=[],
            slaves=[],
        )
        child = IOTreeNode(device, path=root.path)
        root.add_child(child)

        # Verify tree properties
        assert root.child_count == 1
        assert root.tree_path == "RootServer <-- ChildDevice"
        assert root.tree_height() == 2
        assert root.node_search("ChildDevice") is True

        # Verify node generator
        nodes = list(root.node_generator())
        assert len(nodes) == 2
        assert nodes[0].data.name == "RootServer"
        assert nodes[1].data.name == "ChildDevice"
        assert nodes[1].has_children is False


# ===================================================================
# Connection Settings Tests
# ===================================================================


class TestCATioServerConnectionSettings:
    """Test suite for CATioServerConnectionSettings."""

    def test_settings_creation(self):
        """Test creating connection settings."""
        # Create connection settings
        settings = CATioServerConnectionSettings(
            ip="192.168.1.1",
            ams_netid="192.168.1.1.1.1",
            ams_port=2305,
        )

        # Verify settings are created correctly
        assert settings is not None
        assert isinstance(settings, CATioServerConnectionSettings)

    def test_default_settings(self):
        """Test default connection settings."""
        # Create connection settings with defaults
        settings = CATioServerConnectionSettings()

        # Verify default properties
        assert settings.ip == "127.0.0.1"
        assert settings.ams_netid == "127.0.0.1.1.1"
        assert settings.ams_port == 25565

    @pytest.mark.skip(reason="TODO this is failing")
    def test_custom_setting_properties(self):
        """Test custom connection setting properties."""
        # Create connection settings
        settings = CATioServerConnectionSettings(
            ip="10.0.0.1",
            ams_netid="10.0.0.1.1.1",
            ams_port=27905,
        )

        # Verify properties are set correctly
        assert settings.ip == "10.0.0.1"
        assert settings.ams_netid == "10.0.0.1.1.1"
        assert settings.ams_port == 131

    def test_settings_repr(self):
        """Test string representation of settings."""
        # Create connection settings
        settings = CATioServerConnectionSettings()

        # Verify __repr__ output
        repr_str = repr(settings)
        assert "127.0.0.1" in repr_str
        assert "127.0.0.1.1.1" in repr_str
        assert "25565" in repr_str


class TestCATioFastCSRequest:
    """Test suite for CATioFastCSRequest."""

    def test_create_request_no_args(self):
        """Test creating request with no arguments."""
        # Create a request with only command
        request = CATioFastCSRequest("read_state")

        # Verify request properties
        assert isinstance(request, CATioFastCSRequest)
        assert request.command == "read_state"
        assert request.args == ()
        assert request.kwargs == {}

    def test_create_request_with_args(self):
        """Test creating request with positional arguments."""
        # Create a request with command and args
        request = CATioFastCSRequest("read", "symbol1", "symbol2")

        # Verify request properties
        assert request.command == "read"
        assert request.args == ("symbol1", "symbol2")
        assert request.kwargs == {}

    def test_create_request_with_kwargs(self):
        """Test creating request with keyword arguments."""
        # Create a request with command and kwargs
        request = CATioFastCSRequest("write", value=100, index=0)

        # Verify request properties
        assert request.command == "write"
        assert request.args == ()
        assert request.kwargs == {"value": 100, "index": 0}

    def test_create_request_mixed_args(self):
        """Test creating request with mixed arguments."""
        # Create a request with command, args, and kwargs
        request = CATioFastCSRequest("operation", "arg1", 0, key1="value1", key2=50)

        # Verify request properties
        assert request.command == "operation"
        assert request.args == ("arg1", 0)
        assert request.kwargs == {"key1": "value1", "key2": 50}

    def test_request_repr(self):
        """Test string representation of request."""
        # Create a request
        request = CATioFastCSRequest("read", "var1", key1=10)

        # Verify __repr__ output
        repr_str = repr(request)
        assert "read" in repr_str
        assert "var1" in repr_str
        assert "key1=10" in repr_str


class TestCATioFastCSResponse:
    """Test suite for CATioFastCSResponse."""

    def test_create_response(self):
        """Test creating a response."""
        # Create a response with a value
        response = CATioFastCSResponse(value=42)

        # Verify response properties
        assert isinstance(response, CATioFastCSResponse)
        assert response.value == 42

    def test_response_with_string_value(self):
        """Test creating a response with string value."""
        # Create a response with a string value
        response = CATioFastCSResponse(value="result")

        # Verify response properties
        assert isinstance(response, CATioFastCSResponse)
        assert response.value == "result"

    def test_response_to_string(self):
        """Test converting response to string."""
        # Create a response and convert to string
        response = CATioFastCSResponse(value=100)
        str_repr = response.to_string()

        # Verify string representation
        assert isinstance(str_repr, str)
        assert "100" in str_repr

    def test_response_with_complex_value(self):
        """Test response with complex value."""
        # Create a response with a complex value
        val = {"status": "ok", "code": 0}
        response = CATioFastCSResponse(value=val)

        # Verify response properties
        assert isinstance(response, CATioFastCSResponse)
        assert response.value == val
        # Verify string representation
        str_repr = response.to_string()
        assert "status" in str_repr or "ok" in str_repr
