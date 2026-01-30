from __future__ import annotations

import inspect
import logging
import re
import socket
from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from ._constants import TWINCAT_STRING_ENCODING


def get_localhost_name() -> str:
    """
    Get the hostname of the local machine.

    :returns: the local machine hostname
    """
    return socket.gethostname()


def get_localhost_ip() -> str:
    """
    Get the IP address of the local machine.

    :returns: the local machine IP address
    """
    return socket.gethostbyname(get_localhost_name())


def get_local_netid_str() -> str:
    """
    Create the ams netid string value of the Ads client (localhost).

    :returns: the string representing the local client netid
    """
    return get_localhost_ip() + ".1.1"


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


def process_notifications(
    func: Callable,
    notifications: npt.NDArray,
) -> npt.NDArray:
    """
    Manipulate the received notification array by applying a given function.
    This method may be used to test the load on the client resources.

    :param func: the processing function to apply to the notification data
    :param notifications: a numpy array comprising multiple ADS notifications

    :returns: the post-processed notification array
    """
    args = inspect.getfullargspec(func).args
    assert len(args) == 1, (
        f"The processing function {func.__name__} takes more than 1 argument."
    )
    input = inspect.signature(func).parameters[args[0]]
    assert input.annotation == "np.ndarray", (
        f"The processing function {func.__name__} requires a numpy array as argument."
    )
    data = func(notifications)
    logging.debug(
        f"Applied '{func.__name__}' function "
        + f"to notification data comprising {len(data[0])} fields"
    )
    return data


def average(array: np.ndarray) -> np.ndarray:
    """
    Average data from all fields in a numpy structured array.

    :param array: a numpy structured array comprising multiple fields

    :returns: a 1D numpy array with averaged values
    """
    mean_array = np.empty(1, dtype=array.dtype)
    # TODO: Vectorize - call numpy once to do all the averaging
    # See https://github.com/DiamondLightSource/fastcs-catio/issues/22
    assert array.dtype.fields is not None
    for field in array.dtype.fields:
        mean_array[field] = np.mean(array[field])
    return mean_array


def get_notification_changes(
    new_array: np.ndarray, old_array: np.ndarray
) -> np.ndarray:
    """
    Compare two notification arrays and return the differences.
    Each array is expected to be a numpy structured arra.
    Both arrays must have the same shape and dtype.

    :param new_array: the new structured array with updated values
    :param old_array: the old structured array to compare against

    :returns: a numpy array containing the differences between the two arrays
    """
    assert new_array.shape == old_array.shape
    assert new_array.dtype == old_array.dtype
    assert new_array[0].size == old_array[0].size

    mask = []
    for a, b in zip(new_array[0], old_array[0], strict=True):
        mask.append(not np.array_equal(a, b) if isinstance(a, np.ndarray) else a != b)

    diff = []
    assert new_array.dtype.names
    for val, name in zip(mask, new_array.dtype.names, strict=True):
        if val:
            diff.append(name)
    return new_array[diff]


def filetime_to_dt(filetime: int) -> np.datetime64:
    """
    Convert a Windows FILETIME timestamp to a numpy datetime64 object.
    FILETIME is in 100-nanosecond intervals since January 1, 1601 (UTC).
    Numpy datetime64 is in nanoseconds since January 1, 1970 (UTC).

    :param filetime: the FILETIME timestamp as a 64-bit integer

    :returns: the corresponding numpy datetime64 object
    """
    # Difference between epochs in 100-nanosecond intervals
    epoch_diff = 116444736000000000
    # Number of 100-nanosecond intervals in a second
    hundred_nanoseconds = 10_000_000

    # Convert FILETIME to seconds since Unix epoch
    unix_time = (filetime - epoch_diff) / hundred_nanoseconds

    # Convert to numpy datetime64 inc. seconds to nanoseconds conversion
    return np.datetime64(int(unix_time * 1e9), "ns")


def trim_ecat_name(name: str) -> str:
    """
    Shorten and remove spaces from the original EtherCAT name.

    :param name: the original EtherCAT device/terminal name

    :returns: a trimmed name without spaces
    """
    matches = re.search(r"^(\w+\s+)\d+", name)
    return matches.group(0).replace(" ", "") if matches else name


def check_ndarray(
    obj: npt.NDArray,
    expected_dtype: npt.DTypeLike,
    expected_shape: tuple[int,] | tuple[int, int],
) -> bool:
    """
    Check if an object is a numpy ndarray and verifies its dtype and shape.

    :param obj:
    :param expected_dtype:
    :param expected_shape:

    :returns: true if the object is a numpy array with the expected dtype and shape
    """
    return (
        isinstance(obj, np.ndarray)
        and obj.dtype == expected_dtype
        and obj.shape == expected_shape
    )
