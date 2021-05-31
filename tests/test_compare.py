import pytest

from astropy.time import Time
from pathlib import Path
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
        StateCompare(state, state).range_rate
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
