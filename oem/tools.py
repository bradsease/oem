import bz2
import gzip
import lzma
import warnings
from pathlib import Path
from typing import (
    BinaryIO,
    Container,
    Iterator,
    Literal,
    Optional,
    Protocol,
    Sequence,
    TextIO,
    TYPE_CHECKING,
    Tuple,
    Union,
    overload,
)

import numpy as np
from astropy.time import Time, TimeDelta

if TYPE_CHECKING:
    from oem.base import KeyValueSection


class TimeSystemMetadata(Protocol):
    """Metadata exposing the CCSDS time system."""

    def __getitem__(self, key: str) -> str: ...


def parse_str(input_string: str, metadata: "KeyValueSection") -> str:
    """Parse string input.

    Args:
        input_string (str): String to parse.
        metadata (MetaDataSection): Metadata corresponding to this string.

    Returns:
        parsed_str (str): Parsed string.
    """
    return str(input_string)


def _parse_time(epoch: str, time_system: str) -> Time:
    epoch = epoch.strip()
    epoch = epoch[:-1] if epoch.endswith("Z") else epoch
    fmt = _identify_epoch_format(epoch)
    if fmt == "yday":
        epoch = _coerce_epoch_yday(epoch)
    return Time(epoch, format=fmt, scale=time_system, precision=6)


def parse_utc(epoch: str, metadata: "KeyValueSection") -> Time:
    """Parse OEM standard UTC epoch.

    Args:
        epoch (str): OEM epoch string.

    Returns:
        parsed_epoch (Time): UTC epoch.
    """
    return _parse_time(epoch, "utc")


def _get_time_scale(metadata: TimeSystemMetadata) -> str:
    time_system = metadata["TIME_SYSTEM"].lower()
    if time_system not in Time.SCALES:
        warnings.warn(
            f"Unsupported TIME_SYSTEM '{time_system}', falling back to astropy "
            "Time scale 'local'. Use caution with time calculations."
        )
        time_system = "local"
    return time_system


def parse_epoch(epoch: str, metadata: TimeSystemMetadata) -> Time:
    """Parse OEM standard epoch using metadata TIME_SYSTEM.

    Args:
        epoch (str): OEM epoch string.
        metadata (MetaDataSection): Metadata corresponding to this epoch.

    Returns:
        parsed_epoch (Time): Parsed epoch with assigned time scale. If the
            timescale indicated by TIME_SYSTEM is not supported by astropy,
            then parsed_epoch will warn the user and use the local time scale.
    """
    time_system = _get_time_scale(metadata)
    return _parse_time(epoch, time_system)


def _identify_epoch_format(epoch: str) -> str:
    if epoch.count("-") == 2:
        fmt = "isot"
    else:
        fmt = "yday"
    return fmt


def _coerce_epoch_yday(epoch: str) -> str:
    return epoch.replace("-", ":").replace("T", ":")


def _bulk_parse_epochs(epochs: Sequence[str], metadata: TimeSystemMetadata) -> Time:
    """Parse OEM standard epochs using metadata TIME_SYSTEM.

    Applies time-ordered constraint to input epochs. For faster comparisons,
    the strings are compared directly prior to parsing.

    Args:
        epochs (list of str):
        metadata (MetaDataSection): Metadata corresponding to this epoch.

    Returns:
        parsed_epochs (Time):
    """
    time_system = _get_time_scale(metadata)
    epochs = tuple(
        epoch.strip()[:-1] if epoch.strip().endswith("Z") else epoch.strip()
        for epoch in epochs
    )
    fmt = _identify_epoch_format(epochs[0])
    if fmt != "isot":
        epochs = tuple(_coerce_epoch_yday(epoch) for epoch in epochs)

    return Time(epochs, format=fmt, scale=time_system, precision=6)


def parse_integer(input: str, metadata: "KeyValueSection") -> int:
    """Parse integer value.

    Args:
        input: Any input value that can be cast as a number.

    Returns:
        integer (int): Integer equivalent of input.

    Raises:
        ValueError: Invalid integer.
    """
    if float(input).is_integer():
        return int(input)
    else:
        raise ValueError(f"Invalid integer: '{input}'")


def format_float_scientific(value: float) -> str:
    """Convert float to a common string format.

    Args:
        value: Any input that can be cast as a float.

    Returns:
        formatted_value (str): Float following standard scientific format.
    """
    return f"{value:.14e}"


def format_float_decimal(value: float) -> str:
    """Convert float to a common string format.

    Args:
        value: Any input that can be cast as a float.

    Returns:
        formatted_value (str): Float following standard decimal format.
    """
    return f"{value:.6f}"


def format_epoch(epoch: Time) -> str:
    """Format an epoch in the standard OEM format.

    Args:
        epoch (Time): Epoch to convert to string.

    Returns:
        formatted_epoch (str): Epoch in YYYY-MM-DDTHH:MM:SS.ssssss format.
    """
    return epoch.strftime("%Y-%m-%dT%H:%M:%S.%f")


def require(boolean: bool, message: str) -> None:
    """Require a boolean condition.

    Args:
        boolean (bool): Condition boolean.
        message (str): Error message.

    Raises:
        ValueError: message
    """
    if not boolean:
        raise ValueError(message)


def require_field(field: str, metadata: Container[str]) -> None:
    """Require a field in a dict.

    Args:
        field (str): String containing the required field.
        metadata (dict): Dictionary to check for key.

    Raises:
        ValueError: Missing required header.
    """
    require(field in metadata, f"Missing required header: {field}")


def is_kvn(file_path: Union[str, Path]) -> bool:
    """Determine if an OEM file is KVN or XML.

    Args:
        file_path (str or Path): Path of file to check.

    returns:
        result (bool): True if file is KVN, false if XML.
    """
    with _open(file_path, "rt") as target_file:
        if "<?xml" in target_file.readline():
            result = False
        else:
            result = True
    return result


def time_range(start_time: Time, stop_time: Time, step_sec: float) -> Iterator[Time]:
    """Sample a range of astropy Times.

    Args:
        start_time (Time): Initial time in sample span.
        stop_time (Time): Final time in sample span.
        step_sec (float): Step size in seconds.

    Returns:
        times (generator): Generator of sample astropy Times.
    """
    delta = (stop_time - start_time).sec
    for elapsed in np.arange(0, delta, step_sec):
        yield start_time + TimeDelta(elapsed, format="sec")


def epoch_span_contains(span: Tuple[Time, Time], epoch: Time) -> bool:
    """Determine if a given epoch falls within a given timespan.

    Args:
        span (tuple of Time): Pair of Time objects in increasing order.
        epoch (Time): Epoch to compare with span.

    Returns:
        contains (bool): True if input epoch is in the input span, inclusive of
            the endpoint epochs.
    """
    return epoch >= span[0] and epoch <= span[1]


def epoch_span_overlap(
    span1: Tuple[Time, Time], span2: Tuple[Time, Time]
) -> Optional[Tuple[Time, Time]]:
    """Find the overlap between two epoch spans.

    Args:
        span1 (tuple of Time): Range of epochs in increasing order.
        span2 (tuple of Time): Range of epochs in increasing order.

    Returns:
        overlap_range (tuple of Time or None): Overlapping epoch range or None
            if there is no overlap.
    """
    max_start = max(span1[0], span2[0])
    min_end = min(span1[1], span2[1])
    if max_start < min_end:
        overlap_range = (max_start, min_end)
    else:
        overlap_range = None
    return overlap_range


def _get_compression(path: Union[str, Path]) -> Optional[str]:
    headers = {
        b"\x1f\x8b": "gzip",
        b"\x42\x5a\x68": "bz2",
        b"\x5d\x00\x00": "lzma",
        b"\xfd\x37\x7a\x58\x5a\x00": "lzma",
    }
    compression = None
    with open(path, "rb") as fid:
        header = fid.read(6)
        for key, value in headers.items():
            if header.startswith(key):
                compression = value
                break
    return compression


@overload
def _open(
    path: Union[str, Path], mode: Literal["rt"], compression: Optional[str] = None
) -> TextIO: ...


@overload
def _open(
    path: Union[str, Path], mode: Literal["wb"], compression: Optional[str] = None
) -> BinaryIO: ...


@overload
def _open(
    path: Union[str, Path], mode: str, compression: Optional[str] = None
) -> Union[TextIO, BinaryIO]: ...


def _open(
    path: Union[str, Path], mode: str, compression: Optional[str] = None
) -> Union[TextIO, BinaryIO]:
    if mode == "rt":
        compression = _get_compression(path)
    openers = {"gzip": gzip.open, "bz2": bz2.open, "lzma": lzma.open, None: open}
    return openers[compression](path, mode)
