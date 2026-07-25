"""Shared type aliases for OEM values."""

from typing import Tuple

from typing_extensions import TypeAlias

from astropy.time import Time

Epoch: TypeAlias = Time
EpochSpan = Tuple[Epoch, Epoch]
