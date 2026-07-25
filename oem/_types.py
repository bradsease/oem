"""Shared type aliases for OEM values."""

from typing import Tuple

from astropy.time import Time

Epoch = Time
EpochSpan = Tuple[Epoch, Epoch]
