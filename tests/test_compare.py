from pathlib import Path

import numpy as np
import pytest
from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.compare import StateCompare
from oem.components import State

SAMPLE_DIR = Path(__file__).parent / "samples"


def test_state_self_difference():
    state = State(Time.now(), "ICRF", "EARTH", [1, 0, 0], [0, 1, 0], [0, 0, 1])
    compare = state - state
    assert compare.range == 0
    assert compare.range_rate == 0
    assert all(compare.position == 0)
    assert all(compare.velocity == 0)
    assert all(compare.position_ric == 0)
    assert all(compare.velocity_ric == 0)


def test_state_compare_frame_mismatch():
    epoch = Time.now()
    origin = State(epoch, "ICRF", "EARTH", [1, 0, 0], [0, 1, 0])
    target1 = State(epoch, "GRC", "EARTH", [1, 0, 0], [0, 1, 0])
    target2 = State(epoch, "ICRF", "MARS", [1, 0, 0], [0, 1, 0])
    with pytest.raises(ValueError):
        StateCompare(origin, target1)
    with pytest.raises(ValueError):
        StateCompare(origin, target2)


def test_state_compare_noninertial():
    state = State(Time.now(), "GRC", "EARTH", [1, 0, 0], [0, 1, 0])
    with pytest.raises(NotImplementedError):
        StateCompare(state, state).velocity


def test_state_compare_nonstandard():
    state = State(Time.now(), "ABCD", "EARTH", [1, 0, 0], [0, 1, 0])
    with pytest.warns(UserWarning):
        StateCompare(state, state)


def test_state_compare_epoch_mismatch():
    origin = State(Time.now(), "ICRF", "EARTH", [1, 0, 0], [0, 1, 0])
    target = State(Time.now(), "ICRF", "EARTH", [1, 0, 0], [0, 1, 0])
    with pytest.raises(ValueError):
        StateCompare(origin, target)


def test_segment_self_compare():
    test_file_path = SAMPLE_DIR / "real" / "GEO_20s.oem"
    segment = OrbitEphemerisMessage.open(test_file_path).segments[0]
    compare = segment - segment
    assert not compare.is_empty
    for state_compare in compare.steps(600):
        assert state_compare.range == 0 and state_compare.range_rate == 0


def test_segment_compare_mismatch():
    test_file_path = SAMPLE_DIR / "real" / "GEO_20s.oem"
    segment1 = OrbitEphemerisMessage.open(test_file_path).segments[0]
    segment2 = segment1.copy()
    _ = segment1 - segment2
    segment2.metadata["CENTER_NAME"] = "MARS"
    with pytest.raises(ValueError):
        _ = segment1 - segment2


def test_ephemeris_self_compare():
    test_file_path = SAMPLE_DIR / "real" / "GEO_20s.oem"
    oem = OrbitEphemerisMessage.open(test_file_path)
    compare = oem - oem

    assert not compare.is_empty
    segment = compare.segments[0]
    assert segment.start_time < segment.stop_time
    np.testing.assert_almost_equal(compare(segment.start_time).position_ric, 0)

    for state_compare in compare.steps(600):
        assert state_compare.range == 0 and state_compare.range_rate == 0
        assert state_compare.epoch in compare
        np.testing.assert_almost_equal(state_compare.position_ric, 0)
        np.testing.assert_almost_equal(state_compare.velocity_ric, 0)


def test_real_reference_ric():
    test_origin_path = SAMPLE_DIR / "real" / "CompareExample1.oem"
    test_target_path = SAMPLE_DIR / "real" / "CompareExample2.oem"
    origin = OrbitEphemerisMessage.open(test_origin_path)
    target = OrbitEphemerisMessage.open(test_target_path)
    compare = target - origin
    assert not compare.is_empty
    for state_compare in compare.steps(600):
        np.testing.assert_almost_equal(state_compare.range, 1.165554784013)
        np.testing.assert_almost_equal(
            state_compare.position_ric,
            np.array([-0.000101713843, -1.165554779575, 0.0]),
            decimal=6,
        )
        np.testing.assert_almost_equal(state_compare.velocity_ric, 0)
