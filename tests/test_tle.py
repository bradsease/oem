import pytest
from astropy import units
from astropy.time import Time, TimeDelta

from oem.tle import tle_to_oem
from oem.tools import format_epoch

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


def test_generated_oem_data_reaches_metadata_stop():
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc", precision=6)
    stop_epoch = start_epoch + TimeDelta(650, format="sec")

    oem = tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 600, frame="TEME")
    segment = oem.segments[0]

    final_state = list(segment.states)[-1]
    assert final_state.epoch == stop_epoch
    assert format_epoch(final_state.epoch) == format_epoch(
        segment.metadata["STOP_TIME"]
    )


def test_equivalent_time_scales_produce_same_states():
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc")
    stop_epoch = start_epoch + TimeDelta(1 * units.hour)

    utc_oem = tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 600, frame="TEME")
    tt_oem = tle_to_oem(SAMPLE_TLE, start_epoch.tt, stop_epoch.tt, 600, frame="TEME")

    for utc_state, tt_state in zip(utc_oem.states, tt_oem.states):
        assert utc_state.epoch == tt_state.epoch
        assert utc_state.position == pytest.approx(tt_state.position)
        assert utc_state.velocity == pytest.approx(tt_state.velocity)


def test_non_utc_epochs_generate_consistent_utc_oem():
    start_epoch = Time("2019-12-09T20:42:09.000", scale="utc").tt
    stop_epoch = start_epoch + TimeDelta(60 * units.s)

    oem = tle_to_oem(SAMPLE_TLE, start_epoch, stop_epoch, 60, frame="TEME")
    segment = oem.segments[0]
    state = oem.states[0]

    assert segment.metadata["TIME_SYSTEM"] == "UTC"
    assert segment.metadata["START_TIME"].scale == "utc"
    assert segment.metadata["START_TIME"] == start_epoch.utc
    assert segment.metadata["STOP_TIME"] == stop_epoch.utc
    assert state.epoch.scale == "utc"
    assert state.epoch in segment


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
