"""Create OEMs from JPL Horizons vector ephemerides."""

import csv
import io
import json
import re
from urllib.parse import urlencode
from urllib.request import urlopen

from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.components import EphemerisSegment, HeaderSection, MetaDataSection

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
TIME_SYSTEMS = {
    "UT": ("UT", "utc", "UTC"),
    "TT": ("TT", "tt", "TT"),
    "TDB": ("TDB", "tdb", "TDB"),
}


def _quoted(value):
    return f"'{value}'"


def _body_details(result, label, fallback):
    match = re.search(rf"^{label}:\s*(.+?)\s+\{{", result, re.MULTILINE)
    if not match:
        return fallback, fallback

    description = match.group(1).strip()
    match = re.match(r"(.+?)\s+\(([^)]+)\)$", description)
    if match:
        return match.group(1), match.group(2)
    return description, fallback


def _parse_vectors(result, time_scale):
    try:
        data = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    except IndexError:
        raise ValueError("Horizons response does not contain vector data.")

    rows = []
    for row in csv.reader(io.StringIO(data), skipinitialspace=True):
        if row:
            try:
                if len(row) < 8:
                    raise ValueError
                rows.append(
                    (
                        Time(float(row[0]), format="jd", scale=time_scale),
                        *map(float, row[2:8]),
                    )
                )
            except (IndexError, ValueError):
                raise ValueError("Horizons returned malformed vector data.")

    if not rows:
        raise ValueError("Horizons returned no vector data.")
    return tuple(zip(*rows))


def _request_vectors(
    target, center, start_epoch, stop_epoch, step_size, time_system, timeout
):
    if "@" not in center:
        center = f"500@{center}"

    parameters = {
        "format": "json",
        "COMMAND": _quoted(target),
        "OBJ_DATA": "YES",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": _quoted(center),
        "START_TIME": _quoted(getattr(start_epoch, time_system[1]).isot),
        "STOP_TIME": _quoted(getattr(stop_epoch, time_system[1]).isot),
        "STEP_SIZE": _quoted(step_size),
        "TIME_TYPE": time_system[0],
        "TIME_DIGITS": "FRACSEC",
        "REF_PLANE": "FRAME",
        "REF_SYSTEM": "ICRF",
        "OUT_UNITS": "KM-S",
        "VEC_TABLE": "2",
        "VEC_CORR": "NONE",
        "VEC_LABELS": "NO",
        "CSV_FORMAT": "YES",
        "CAL_FORMAT": "JD",
    }
    url = f"{HORIZONS_URL}?{urlencode(parameters)}"
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "error" in payload:
        raise ValueError(f"Horizons API error: {payload['error']}")
    return payload["result"]


def horizons_to_oem(
    target,
    center,
    start_epoch,
    stop_epoch,
    step_size="1h",
    time_system="UT",
    timeout=30,
):
    """Create an OEM from a JPL Horizons vector ephemeris.

    Args:
        target (str): Horizons target selection, such as ``"499"`` for Mars.
            Use Horizons selection syntax for small bodies, for example ``"1;"``
            for Ceres.
        center (str): Horizons central-body ID, such as ``"399"`` for Earth.
            A complete Horizons center specification (for example ``"500@399"``)
            may also be supplied.
        start_epoch (Time): Start of the requested ephemeris.
        stop_epoch (Time): End of the requested ephemeris.
        step_size (str, optional): Horizons output step size, such as ``"1h"``
            or ``"1d"``. Default is ``"1h"``.
        time_system (str, optional): Horizons output time system, ``"UT"``,
            ``"TT"``, or ``"TDB"``. Default is ``"UT"``.
        timeout (float, optional): HTTP request timeout in seconds. Default is 30.

    Returns:
        OrbitEphemerisMessage: An ICRF, UTC OEM with position in kilometers and
        velocity in kilometers per second.

    Raises:
        TypeError: Start or stop epoch is not an astropy Time instance.
        ValueError: Horizons rejects the request or returns malformed data.
    """
    if not isinstance(start_epoch, Time) or not isinstance(stop_epoch, Time):
        raise TypeError("start_epoch and stop_epoch must be astropy Time instances.")
    if start_epoch > stop_epoch:
        raise ValueError("start_epoch must not be after stop_epoch.")
    try:
        time_system = TIME_SYSTEMS[time_system.upper()]
    except (AttributeError, KeyError):
        raise ValueError("time_system must be 'UT', 'TT', or 'TDB'.")

    result = _request_vectors(
        str(target),
        str(center),
        start_epoch,
        stop_epoch,
        str(step_size),
        time_system,
        timeout,
    )
    state_data = _parse_vectors(result, time_system[1])
    object_name, object_id = _body_details(result, "Target body name", str(target))
    center_name, _ = _body_details(result, "Center body name", str(center))
    start_time, stop_time = state_data[0][0], state_data[0][-1]

    metadata = MetaDataSection(
        {
            "OBJECT_NAME": object_name,
            "OBJECT_ID": object_id,
            "CENTER_NAME": center_name,
            "REF_FRAME": "ICRF",
            "TIME_SYSTEM": time_system[2],
            "START_TIME": start_time.isot,
            "STOP_TIME": stop_time.isot,
        }
    )
    header = HeaderSection(
        {
            "CCSDS_OEM_VERS": "2.0",
            "CREATION_DATE": Time.now().isot,
            "ORIGINATOR": "NASA/JPL Horizons",
        }
    )
    return OrbitEphemerisMessage(header, [EphemerisSegment(metadata, state_data)])
