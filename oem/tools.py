import warnings
import re
import datetime as dt
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
            epoch.replace("Z", "")[:epoch.index(".")+7].strip(),
            f"{ymd_fmt}T%H:%M:%S.%f"
        )
    else:
        return dt.datetime.strptime(
            epoch.replace("Z", "").strip(),
            f"{ymd_fmt}T%H:%M:%S"
        )


def parse_utc(epoch, metadata):
    """Parse OEM standard UTC epoch.

    Args:
        epoch (str): OEM epoch string.

    Returns:
        parsed_epoch (Time): UTC epoch.
    """
    return Time(parse_datetime(epoch), format="datetime", scale="utc")


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
        parsed_epoch = Time(dt_epoch, format="datetime", scale=time_system)
    else:
        warnings.warn(
            f"Unsupported TIME_SYSTEM '{time_system}', falling back to "
            f"DateTime. Use caution with time calculations."
        )
        parsed_epoch = dt_epoch
    return parsed_epoch


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
        formatted_epoch (str): Epoch in YYYY-MM-DDTHH:MM:SS.sss format.
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
    with open(file_path, "r") as target_file:
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


def regex_block_iter(pattern, contents):
    """Iterate through blocks of file content.

    Assumes that the input pattern is repeated from the beginning to the end
    of the file. Raises an exception if every character of the input is not
    matched as part of a repeated block.

    Args:
        pattern (str): Regex pattern of repeated block.
        contents (str): Full contents of file to parse.

    Yields:
        groups (tuple): Regex match results.

    Raises:
        ValueError: Failed to parse complete file contents.
    """
    idx = 0
    while idx < len(contents):
        match = re.match(pattern, contents[idx:], re.MULTILINE)
        if match:
            idx += match.span()[1]
            yield match.groups()
        else:
            raise ValueError("Failed to parse complete file contents.")
