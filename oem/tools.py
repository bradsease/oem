import datetime as dt


def parse_epoch(epoch):
    """Parse OEM standard epoch.

    Args:
        epoch (str): OEM epoch string.

    Returns:
        parsed_epoch (DateTime): Parsed epoch.
    """
    if "." in epoch:
        return dt.datetime.strptime(
            epoch.replace("Z", "")[:epoch.index(".")+7].strip(),
            "%Y-%m-%dT%H:%M:%S.%f"
        )
    else:
        return dt.datetime.strptime(
            epoch.replace("Z", "").strip(),
            "%Y-%m-%dT%H:%M:%S"
        )


def parse_integer(input):
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


def is_ascii(file_path):
    """Determine if a file is ASCII or XML.

    Args:
        file_path (str or Path): Path of file to check.

    returns:
        result (bool): True if file is ASCII, false if XML.
    """
    with open(file_path, "r") as target_file:
        if "<?xml" in target_file.readline():
            result = False
        else:
            result = True
    return result
