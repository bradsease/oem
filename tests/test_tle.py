import pytest
from astropy import units
from astropy.time import Time, TimeDelta

from oem.tle import tle_to_oem

SAMPLE_TLE = (
    "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
    "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
)


@pytest.mark.parametrize("frame", ("TEME", "ICRF"))
def test_sample(frame):
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc")
    stop_epoch = start_epoch + TimeDelta(1 * units.day)
    oem = tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 3600, frame=frame)
    assert len(oem._segments) == 1
    assert oem.segments[0].metadata["REF_FRAME"] == frame


@pytest.mark.parametrize("frame", ("TEME", "ICRF"))
def test_convert_and_compare(frame):
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc")
    stop_epoch = start_epoch + TimeDelta(1 * units.day)
    origin = tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 600, frame=frame)
    target = tle_to_oem(SAMPLE_TLE, *origin.span, 600, frame=frame)
    compare = target - origin
    assert not compare.is_empty
    for compare in compare.steps(3600):
        assert compare.range == 0 and compare.range_rate == 0


def test_bad_frame():
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc")
    stop_epoch = start_epoch + TimeDelta(1 * units.day)
    with pytest.raises(ValueError):
        tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 3600, frame="aBcDe")


def test_bad_tle():
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc")
    stop_epoch = start_epoch + TimeDelta(1 * units.day)
    with pytest.raises(ValueError):
        tle_to_oem(["", ""], start_epoch, stop_epoch, 3600)
