import bz2
import datetime as dt
import gzip
import lzma
import warnings

import numpy as np
from astropy.time import Time, TimeDelta


def parse_str(input_string, metadata):
    """Parse string input.

    Args:
        input_string (str): String to parse.
        metadata (MetaDataSection): Metadata corresponding to this string.

    Returns:
        parsed_str (str): Parsed string.
    """
    return str(input_string)


def parse_datetime(epoch):
    """Convert OEM standard epoch to a DateTime.

    Args:
        epoch (str): OEM epoch string.

    Returns:
        parsed_epoch (DateTime):  Parsed epoch.
    """
    ymd_fmt = "%Y-%m-%d" if epoch.count("-") == 2 else "%Y-%j"
    if "." in epoch:
        return dt.datetime.strptime(
            epoch.replace("Z", "")[: epoch.index(".") + 7].strip(),
            f"{ymd_fmt}T%H:%M:%S.%f",
        )
    else:
        return dt.datetime.strptime(
            epoch.replace("Z", "").strip(), f"{ymd_fmt}T%H:%M:%S"
        )


def parse_utc(epoch, metadata):
    """Parse OEM standard UTC epoch.

    Args:
        epoch (str): OEM epoch string.

    Returns:
        parsed_epoch (Time): UTC epoch.
    """
    return Time(parse_datetime(epoch), format="datetime", scale="utc", precision=6)


def parse_epoch(epoch, metadata):
    """Parse OEM standard epoch using metadata TIME_SYSTEM.

    Args:
        epoch (str): OEM epoch string.
        metadata (MetaDataSection): Metadata corresponding to this epoch.

    Returns:
        parsed_epoch (Time): Parsed epoch with assigned time scale. If the
            timescale indicated by TIME_SYSTEM is not supported by astropy,
            then parsed_epoch will warn the user and fall back to DateTime. In
            this case, time calculations may be inaccurate.
    """
    time_system = metadata["TIME_SYSTEM"].lower()
    dt_epoch = parse_datetime(epoch)
    if time_system in Time.SCALES:
        parsed_epoch = Time(dt_epoch, format="datetime", scale=time_system, precision=6)
    else:
        warnings.warn(
            f"Unsupported TIME_SYSTEM '{time_system}', falling back to "
            f"DateTime. Use caution with time calculations."
        )
        parsed_epoch = dt_epoch
    return parsed_epoch


def _identify_epoch_format(epoch):
    if epoch.count("-") == 2:
        fmt = "isot"
    else:
        fmt = "yday"
    return fmt


def _coerce_epoch_yday(epoch):
    return epoch.replace("-", ":").replace("T", ":")


def _bulk_parse_epochs(epochs, metadata):
    """Parse OEM standard epochs using metadata TIME_SYSTEM.

    Applies time-ordered constraint to input epochs. For faster comparisons,
    the strings are compared directly prior to parsing.

    Args:
        epochs (list of str):
        metadata (MetaDataSection): Metadata corresponding to this epoch.

    Returns:
        parsed_epochs (list of Time):
    """
    time_system = metadata["TIME_SYSTEM"].lower()
    fmt = _identify_epoch_format(epochs[0])
    if fmt != "isot":
        epochs = tuple(_coerce_epoch_yday(epoch) for epoch in epochs)

    if time_system in Time.SCALES:
        parsed_epochs = Time(epochs, format=fmt, scale=time_system, precision=6)
    else:
        warnings.warn(
            f"Unsupported TIME_SYSTEM '{time_system}', falling back to "
            f"DateTime. Use caution with time calculations."
        )
        parsed_epochs = tuple(parse_epoch(epoch, metadata) for epoch in epochs)

    return parsed_epochs


def parse_integer(input, metadata):
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


def format_float(value):
    """Convert float to a common string format.

    Args:
        value: Any input that can be cast as a float.

    Returns:
        formatted_value (str): Float following standard format.
    """
    return f"{value:+.14e}"


def format_epoch(epoch):
    """Format an epoch in the standard OEM format.

    Args:
        epoch (Time, DateTime): Epoch to convert to string.

    Returns:
        formatted_epoch (str): Epoch in YYYY-MM-DDTHH:MM:SS.ssssss format.
    """
    return epoch.strftime("%Y-%m-%dT%H:%M:%S.%f")


def require(boolean, message):
    """Require a boolean condition.

    Args:
        boolean (bool): Condition boolean.
        message (str): Error message.

    Raises:
        ValueError: message
    """
    if not boolean:
        raise ValueError(message)


def require_field(field, metadata):
    """Require a field in a dict.

    Args:
        field (str): String containing the required field.
        metadata (dict): Dictionary to check for key.

    Raises:
        ValueError: Missing required header.
    """
    require(field in metadata, f"Missing required header: {field}")


def is_kvn(file_path):
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


def time_range(start_time, stop_time, step_sec):
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


def epoch_span_contains(span, epoch):
    """Determine if a given epoch falls within a given timespan.

    Args:
        span (tuple of Time): Pair of Time objects in increasing order.
        epoch (Time): Epoch to compare with span.

    Returns:
        contains (bool): True if input epoch is in the input span, inclusive of
            the endpoint epochs.
    """
    return epoch >= span[0] and epoch <= span[1]


def epoch_span_overlap(span1, span2):
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


def _get_compression(path):
    headers = {
        b"\x1F\x8b": "gzip",
        b"\x42\x5A\x68": "bz2",
        b"\x5d\x00\x00": "lzma",
        b"\xFD\x37\x7A\x58\x5A\x00": "lzma",
    }
    compression = None
    with open(path, "rb") as fid:
        header = fid.read(6)
        for key, value in headers.items():
            if header.startswith(key):
                compression = value
                break
    return compression


def _open(path, mode, compression=None):
    if mode == "rt":
        compression = _get_compression(path)
    openers = {"gzip": gzip.open, "bz2": bz2.open, "lzma": lzma.open, None: open}
    return openers[compression](path, mode)
