from __future__ import annotations

import inspect
import itertools
import re
import socket
from collections.abc import Callable, Iterable
from logging import getLogger
from typing import Any

import numpy as np
import numpy.typing as npt

from ._constants import TWINCAT_STRING_ENCODING

logger = getLogger(__name__)


_FASTCS_GROUP_NAME_RE = re.compile(r"^([A-Z][a-z0-9]*)*$")
_BEAMLINE_NAME_RE = re.compile(r"^(BL[0-9]+[A-Z])-([A-Z]+)-([A-Z]+)-([0-9]+)")


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
    logger.debug(
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
    new_array: np.ndarray, old_array: np.ndarray | None
) -> np.ndarray:
    """
    Compare two notification arrays and return the differences.
    Each array is expected to be a numpy structured arra.
    Both arrays must have the same shape and dtype.

    :param new_array: the new structured array with updated values
    :param old_array: the old structured array to compare against

    :returns: a numpy array containing the differences between the two arrays
    """
    if old_array is None:
        return new_array

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
    Convert an EtherCAT name into a valid fastcs group name (UpperCamelCase).

    Two transformations are applied in order:

    1. **Beckhoff-style names** (e.g. ``"Term 2 (EK1110)"``): the leading
       word-and-number prefix is extracted and the space removed
       (``"Term2"``).
    2. **General sanitization**: if the result still contains characters
       outside the fastcs pattern ``^([A-Z][a-z0-9]*)*$`` (e.g. hyphens
       as in ``"BL04I-EA-ERIO-01"``), the name is split on every run of
       non-alphanumeric characters. Letter-starting segments are
       title-cased. Numeric-only segments are appended to the last
       letter-starting segment to preserve them and avoid collisions.

    :param name: the original EtherCAT device/terminal name

    :returns: a valid fastcs UpperCamelCase group name

    Examples:
        >>> trim_ecat_name("Term 2 (EK1110)")
        'Term2'
        >>> trim_ecat_name("BL04I-EA-ERIO-01")
        'Bl04iEaErio01'
        >>> trim_ecat_name("Device_Name_With_Underscores")
        'DeviceNameWithUnderscores'
        >>> trim_ecat_name("")
        ''
    """
    matches = re.search(r"^(\w+\s+)\d+", name)
    name = matches.group(0).replace(" ", "") if matches else name

    if not _FASTCS_GROUP_NAME_RE.match(name):
        parts = re.split(r"[^a-zA-Z0-9]+", name)
        result = []
        numeric_parts = []

        for p in parts:
            if p and p[0].isalpha():
                result.append(p[0].upper() + p[1:].lower())
            elif p and p[0].isdigit():
                numeric_parts.append(p)

        # Append numeric-only segments to the last letter-starting segment
        if numeric_parts and result:
            result[-1] += "".join(numeric_parts)

        name = "".join(result)

    return name


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


def check_coe_indices_format(index: str, subindex: str) -> tuple[str, str]:
    """
    Check the format of CoE indices and remove '0x' prefix if present.

    :param index: CoE index as a string
    :param subindex: CoE subindex as a string

    :returns: tuple of formatted index and subindex
    """
    index = index.removeprefix("0x") if index.startswith("0x") else index
    subindex = subindex.removeprefix("0x") if subindex.startswith("0x") else subindex
    assert len(index) == 4 and len(subindex) == 4, (
        f"Wrong format provided for the CoE indices: {index},{subindex}"
    )
    return index, subindex


def get_all_attributes(instance: object) -> list[Any]:
    """
    Get a list of all attributes of an instance, including inherited ones.
    Also recursively retrieves attributes from iterable attributes.

    :param instance: the instance to inspect

    :returns: a list of attribute values
    """
    assert not inspect.isclass(instance), "Expected an instance, got a class."
    attributes = {}

    # Get attributes from parent classes
    attributes.update(get_parent_class_attributes(instance.__class__))
    # Get attributes from the instance itself
    attributes.update(vars(instance))

    # Recursively collect all attribute values
    all_attributes = []
    for v in attributes.values():
        if isinstance(v, Iterable):
            for item in v:
                all_attributes.extend(get_all_attributes(item))
        else:
            all_attributes.append(v)

    return all_attributes


def get_parent_class_attributes(cls: type) -> dict[str, object]:
    """
    Get a dictionary of all attributes of parent classes, including inherited ones.
    It will ignore any special/magic attributes (those starting with '__'), \
        functions and methods.

    :param cls: the class to inspect

    :returns: a dictionary of attribute names and their values
    """
    attributes: dict[str, object] = {}
    for base in cls.__bases__:
        attributes.update(get_parent_class_attributes(base))
    attributes.update(cls.__dict__)

    return {
        k: v
        for k, v in attributes.items()
        if not (k.startswith("__") or inspect.isfunction(v) or inspect.ismethod(v))
    }


def make_node_prefix(parent_path: list[str], substitution: str) -> list[str]:
    """
    Create a node prefix for the CATio controller based on the parent path.
    If the server prefix matches the beamline pattern, the substitution string is used \
        to create a new prefix based on that pattern (e.g. "BL04I-EA-ERIO-01").
    Otherwise, the substitution is simply appended to the parent path \
        (e.g. "BL04I-EA-CATIO-01:ETH1:ERIO1").

    :param parent_path: the parent path provided by the user
    :param substitution: the substitution string to use if the server prefix matches \
        the beamline pattern

    :returns: a list of strings representing the node path for the controller
    """
    server_prefix = parent_path[0]
    if _BEAMLINE_NAME_RE.match(server_prefix):
        formatted_sub = "-".join(
            p.zfill(2) if p.isdigit() else p
            for p in [
                "".join(x) for _, x in itertools.groupby(substitution, key=str.isdigit)
            ]
        )
        return [
            re.sub(
                _BEAMLINE_NAME_RE,
                r"\1-\2-" + formatted_sub,
                server_prefix,
            )
        ]

    return parent_path + [substitution]
