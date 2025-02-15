import pytest
from .test_samples import _get_test_files
from oem import OrbitEphemerisMessage


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


@pytest.mark.parametrize("filename", _get_test_files(version="v2_0", validity="valid"))
def test_covariance(filename):
    oem = OrbitEphemerisMessage.open(filename)
    if len(oem.covariances):
        covariance = oem.covariances[0]
        assert covariance == covariance.copy()
        str(covariance)
