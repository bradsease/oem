"""Test parsing sample OEMS.
"""
import pytest
from pathlib import Path
from oem import OrbitalEphemerisMessage


THIS_DIR = Path(__file__).parent
SAMPLE_DIR = THIS_DIR / "samples"


def _get_test_files(version, data_format, validity):
    sample_dir = SAMPLE_DIR / version / data_format / validity
    return sorted([
        entry for entry in sample_dir.iterdir()
        if str(entry).endswith(".oem")
    ])


@pytest.mark.parametrize("file_path", _get_test_files("v1_0", "KVN", "valid"))
def test_valid_v1_kvn_samples(file_path):
    """Verify parsing of valid v1.0 KVN OEM samples

    This test requires external data.
    """
    oem = OrbitalEphemerisMessage.from_ascii_oem(file_path)

    for segment in oem:
        for state in segment.states:
            assert state.acceleration is None
        assert len(oem.states) > 0
        assert len(oem.covariances) == 0


@pytest.mark.parametrize(
    "file_path",
    _get_test_files("v1_0", "KVN", "invalid")
)
def test_invalid_v1_kvn_samples(file_path):
    """Verify parsing failure for invalid v1.0 KVN OEM samples

    This test requires external data.
    """
    with pytest.raises(Exception):
        OrbitalEphemerisMessage.from_ascii_oem(file_path)


@pytest.mark.parametrize("file_path", _get_test_files("v2_0", "KVN", "valid"))
def test_valid_v2_kvn_samples(file_path):
    """Verify parsing of valid v2.0 KVN OEM samples

    This test requires external data.
    """
    oem = OrbitalEphemerisMessage.from_ascii_oem(file_path)
    assert oem.version == "2.0"

    for segment in oem:
        if not segment.has_accel:
            for state in segment.states:
                assert state.acceleration is None
        for covariance in segment.covariances:
            assert covariance.matrix.shape == (6, 6)

        assert segment.useable_start_time in segment
        assert segment.useable_stop_time in segment
        assert len(oem.states) > 0
        assert len(oem.covariances) >= 0

    assert "CCSDS_OEM_VERS" in oem.header


@pytest.mark.parametrize(
    "file_path",
    _get_test_files("v2_0", "KVN", "invalid")
)
def test_invalid_v2_kvn_samples(file_path):
    """Verify parsing failure for invalid v2.0 KVN OEM samples

    This test requires external data.
    """
    with pytest.raises(Exception):
        OrbitalEphemerisMessage.from_ascii_oem(file_path)
