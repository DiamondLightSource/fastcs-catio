from collections.abc import Sequence
from typing import (
    TYPE_CHECKING,
    SupportsInt,
    TypeAlias,
)

import numpy as np

if TYPE_CHECKING:
    BYTES16 = bytes
    USINT = SupportsInt
    UINT = SupportsInt
    UDINT = SupportsInt
    NETID = Sequence[int]
    # STRING = SupportsBytes
else:
    BYTES16: TypeAlias = np.dtype("S16")
    USINT: TypeAlias = np.uint8
    UINT: TypeAlias = np.uint16
    UDINT: TypeAlias = np.uint32
    NETID: TypeAlias = np.dtype((np.uint8, 6))
