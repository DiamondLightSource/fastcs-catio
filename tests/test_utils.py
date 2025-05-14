from catio.utils import get_local_netid_str, netid_from_bytes, netid_from_str


def test_local_netid_creation():
    assert get_local_netid_str()[-4:] == ".1.1"


def test_netid_conversion_from_dot_string():
    input = "1.2.3.4.5.6"
    output = [1, 2, 3, 4, 5, 6]
    assert netid_from_str(input) == output


def test_netid_conversion_from_bytes():
    input = b"\x0a\x02\xff\x10\x01\x01"
    output = "10.2.255.16.1.1"
    assert netid_from_bytes(input) == output
