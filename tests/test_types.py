import pytest
from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.components import State

from .test_samples import _get_test_files

pytestmark = pytest.mark.filterwarnings("ignore:Unsupported TIME_SYSTEM 'abcd'")

SAMPLE_FILE = _get_test_files(version="v2_0", validity="valid")[1]
SAMPLE_FILE_ACCEL = _get_test_files(version="v2_0", validity="valid")[7]


@pytest.mark.parametrize("filename", _get_test_files(version="v2_0", validity="valid"))
def test_state(filename):
    oem = OrbitEphemerisMessage.open(filename)
    state = oem.states[0]

    assert state == state.copy()
    if state.has_accel:
        assert len(state.vector) == 9
    else:
        assert len(state.vector) == 6

    str(state)


def test_state_equality_includes_frame_center_and_acceleration():
    state = State(
        Time("2020-01-01T00:00:00"),
        "ICRF",
        "EARTH",
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    )

    assert state == state.copy()
    assert state != State(
        state.epoch,
        "GRC",
        state.center,
        state.position,
        state.velocity,
        state.acceleration,
    )
    assert state != State(
        state.epoch,
        state.frame,
        "MARS",
        state.position,
        state.velocity,
        state.acceleration,
    )
    assert state != State(
        state.epoch, state.frame, state.center, state.position, state.velocity
    )
    assert state != State(
        state.epoch,
        state.frame,
        state.center,
        state.position,
        state.velocity,
        [10, 8, 9],
    )


@pytest.mark.parametrize("filename", _get_test_files(version="v2_0", validity="valid"))
def test_covariance(filename):
    oem = OrbitEphemerisMessage.open(filename)
    if len(oem.covariances):
        covariance = oem.covariances[0]
        assert covariance == covariance.copy()
        str(covariance)
