import numpy as np
from astropy import units as u
from astropy.coordinates import (
    GCRS,
    TEME,
    CartesianDifferential,
    CartesianRepresentation,
)
from astropy.time import Time
from sgp4.api import Satrec

from oem import OrbitEphemerisMessage
from oem.components import EphemerisSegment, HeaderSection, MetaDataSection
from oem.tools import time_range


def _build_header():
    return HeaderSection(
        {
            "CCSDS_OEM_VERS": "2.0",
            "CREATION_DATE": Time.now().isot,
            "ORIGINATOR": "OEM-Python",
        }
    )


def _build_metadata(satrec, start_epoch, stop_epoch, frame):
    return MetaDataSection(
        {
            "OBJECT_NAME": str(satrec.satnum),
            "OBJECT_ID": str(satrec.satnum),
            "CENTER_NAME": "Earth",
            "REF_FRAME": frame.upper(),
            "TIME_SYSTEM": "UTC",
            "START_TIME": start_epoch.isot,
            "STOP_TIME": stop_epoch.isot,
        }
    )


def _build_segment(satrec, start_epoch, stop_epoch, step, frame):
    epoch_range = list(time_range(start_epoch, stop_epoch, step))
    position, velocity = _sample_tle_at_epoch_array(satrec, epoch_range, frame)
    return EphemerisSegment(
        _build_metadata(satrec, start_epoch, stop_epoch, frame),
        (epoch_range, *zip(*position), *zip(*velocity)),
    )


def _build_oem(satrec, start_epoch, stop_epoch, step, frame):
    return OrbitEphemerisMessage(
        _build_header(), [_build_segment(satrec, start_epoch, stop_epoch, step, frame)]
    )


def _sample_tle_at_epoch_array(satrec, epochs, frame):
    if frame not in ("TEME", "ICRF"):
        raise ValueError(f"Unsupported frame: {frame}")
    jd1 = np.array([epoch.jd1 for epoch in epochs])
    jd2 = np.array([epoch.jd2 for epoch in epochs])
    err, r, v = satrec.sgp4_array(jd1, jd2)
    if any(err):
        raise ValueError("SGP4 propagation failed!")
    else:
        teme_p = CartesianRepresentation(r.T * u.km)
        teme_v = CartesianDifferential(v.T * u.km / u.s)
        states = TEME(teme_p.with_differentials(teme_v), obstime=epochs)
        if frame == "ICRF":
            states = states.transform_to(GCRS(obstime=epochs))
        return (
            states.cartesian.get_xyz().value.T,
            states.cartesian.differentials["s"].get_d_xyz().value.T,
        )


def tle_to_oem(tle, start_epoch, stop_epoch, step, frame="ICRF"):
    """Create an OEM instance from a Two-Line Element set.

    Args:
        tle (list of str): List of two or three line element strings.
        start_epoch (Time): Output OEM start time.
        stop_epoch (Time): Output OEM stop time.
        step (float): Output OEM step time in seconds.
        frame (str, optional): Desired output frame. Currently supported
            options are "ICRF" and "TEME". Default is "ICRF".

    Returns:
        oem (OrbitEphemerisMessage): Converted OEM instance.

    Raises:
        ValueError: Unsupported frame.
    """
    satrec = Satrec.twoline2rv(*tle[-2:])
    return satrec_to_oem(satrec, start_epoch, stop_epoch, step, frame=frame)


def satrec_to_oem(satrec, start_epoch, stop_epoch, step, frame="ICRF"):
    """Create an OEM instance from an sgp4.api.Satrec instance.

    Args:
        satrec (Satrec): Satrec instance containing desired TLE.
        start_epoch (Time): Output OEM start time.
        stop_epoch (Time): Output OEM stop time.
        step (float): Output OEM step time in seconds.
        frame (str, optional): Desired output frame. Currently supported
            options are "ICRF" and "TEME". Default is "ICRF".

    Returns:
        oem (OrbitEphemerisMessage): Converted OEM instance.

    Raises:
        ValueError: Unsupported frame.
    """
    return _build_oem(satrec, start_epoch, stop_epoch, step, frame)
