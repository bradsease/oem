from sgp4.api import Satrec
from astropy.coordinates import (
    CartesianDifferential, CartesianRepresentation, TEME, GCRS
)
from astropy.time import Time
from astropy import units as u
from oem.components import (
    HeaderSection, MetaDataSection, State, EphemerisSegment, DataSection
)
from oem import OrbitEphemerisMessage
from oem.tools import time_range


def _build_header():
    return HeaderSection({
        "CCSDS_OEM_VERS": "2.0",
        "CREATION_DATE": Time.now().isot,
        "ORIGINATOR": "OEM-Python"
    })


def _build_metadata(satrec, start_epoch, stop_epoch):
    return MetaDataSection({
        "OBJECT_NAME": str(satrec.satnum),
        "OBJECT_ID": str(satrec.satnum),
        "CENTER_NAME": "Earth",
        "REF_FRAME": "ICRF",
        "TIME_SYSTEM": "UTC",
        "START_TIME": start_epoch.isot,
        "STOP_TIME": stop_epoch.isot,
    })


def _build_state(satrec, epoch, frame):
    return State(
        epoch,
        frame,
        "Earth",
        *_sample_tle_at_epoch(satrec, epoch, frame)
    )


def _build_segment(satrec, start_epoch, stop_epoch, step, frame):
    return EphemerisSegment(
        _build_metadata(satrec, start_epoch, stop_epoch),
        DataSection([
            _build_state(satrec, epoch, frame)
            for epoch in time_range(start_epoch, stop_epoch, step)
        ])
    )


def _build_oem(satrec, start_epoch, stop_epoch, step, frame):
    return OrbitEphemerisMessage(
        _build_header(),
        [_build_segment(satrec, start_epoch, stop_epoch, step, frame)]
    )


def _sample_tle_at_epoch(satrec, epoch, frame):
    if frame not in ("TEME", "ICRF"):
        raise ValueError(f"Unsupported frame: {frame}")
    err, r, v = satrec.sgp4(epoch.jd1, epoch.jd2)
    if err:
        raise ValueError(f"SGP4 propagation failed: {err}")
    else:
        teme_p = CartesianRepresentation(r*u.km)
        teme_v = CartesianDifferential(v*u.km/u.s)
        state = TEME(teme_p.with_differentials(teme_v), obstime=epoch)
        if frame == "ICRF":
            state = state.transform_to(GCRS(obstime=epoch))
        return (
            state.cartesian.get_xyz().value,
            state.cartesian.differentials["s"].get_d_xyz().value
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
