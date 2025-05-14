from __future__ import annotations

import socket
from collections.abc import Sequence

import numpy as np

from ._constants import TWINCAT_STRING_ENCODING


def get_local_netid_str() -> str:
    """
    Create the ams netid string value of the Ads client (localhost).
    :return
        rtype: str
        the string representing the local client netid
    """
    return socket.gethostbyname(socket.gethostname()) + ".1.1"


def netid_from_str(net_id: str) -> Sequence[int]:
    """
    Convert the netid string from the standard dot-notation to a sequence of integers.
    :param
        str: net_id - the netid value expressed as x.x.x.x.x.x
    :return
        rtype: list[int]
        the netid as a list of integers
    """
    sequence = [int(x) for x in net_id.split(".")]
    assert len(sequence) == 6, ValueError
    return sequence


def netid_from_bytes(data: bytes) -> str:
    """
    Convert a bytes netid address into a dot-separated string address.

    :param data: the ams netid as a byte stream

    :returns: the ams netid as a string
    """
    assert len(data) == 6
    netid = (np.frombuffer(data, dtype=np.uint8, count=6)).astype(np.str_)
    return ".".join(list(netid))


def bytes_to_string(raw_data: bytes, strip: bool = True) -> str:
    """
    Convert a bytes object into a unicode string.

    :param raw_data: an array of bytes to convert to string
    :param strip: boolean indicating whether trailing bytes must be removed

    :returns: a string object as a numpy string type
    """
    if strip:
        null_index = raw_data.find(0)
        if null_index != -1:
            raw_data = raw_data[:null_index]
    return raw_data.decode(encoding=TWINCAT_STRING_ENCODING)
