"""Shared type aliases for OEM values."""

import datetime as dt
from typing import Tuple, Union

from astropy.time import Time

Epoch = Union[Time, dt.datetime]
EpochSpan = Tuple[Epoch, Epoch]
