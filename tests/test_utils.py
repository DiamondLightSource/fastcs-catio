from catio.utils import get_local_netid_str


def test_local_netid_creation():
    assert get_local_netid_str()[-4:] == ".1.1"
