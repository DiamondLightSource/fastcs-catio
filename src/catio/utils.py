from __future__ import annotations

import socket

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


def add_comment(new_str: str, old_str: str) -> str:
    """
    Concatenate two strings with a new line.

    :param new_str: new string to append
    :param old_str: existing string to append to

    :returns: an updated string
    """
    return new_str if not old_str else "\n".join([old_str, new_str])


def average_notifications(array: np.ndarray) -> np.ndarray:
    """
    Average data from all fields in a numpy structured array.

    :param array: a numpy structured array comprising multiple fields

    :returns: a 1D numpy array with averaged values
    """
    mean_array = np.empty(1, dtype=array.dtype)
    for field in array.dtype.fields:
        mean_array[field] = np.mean(array[field])
    return mean_array
