"""Test parsing sample OEMS.
"""
import pytest
import tempfile
from pathlib import Path
from oem import OrbitEphemerisMessage
from oem.tools import is_kvn


THIS_DIR = Path(__file__).parent
SAMPLE_DIR = THIS_DIR / "samples"


def _get_test_files(version, validity):
    sample_dir = SAMPLE_DIR / version / validity
    return sorted([
        entry for entry in sample_dir.iterdir()
        if str(entry).endswith(".oem")
    ])


@pytest.mark.parametrize("file_path", _get_test_files("v1_0", "valid"))
def test_valid_v1_samples(file_path):
    """Verify parsing of valid v1.0 OEM samples

    This test requires external data.
    """
    oem = OrbitEphemerisMessage.open(file_path)

    for segment in oem:
        for state in segment.states:
            assert state.acceleration is None
        assert len(oem.states) > 0
        assert len(oem.covariances) == 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        written_oem_path = Path(tmp_dir) / "written.oem"
        fmt = "XML" if is_kvn(file_path) else "KVN"
        OrbitEphemerisMessage.convert(file_path, written_oem_path, fmt)
        written_oem = OrbitEphemerisMessage.open(written_oem_path)
        assert written_oem == oem


@pytest.mark.parametrize("file_path", _get_test_files("v1_0", "invalid"))
def test_invalid_v1_samples(file_path):
    """Verify parsing failure for invalid v1.0 OEM samples

    This test requires external data.
    """
    with pytest.raises(Exception):
        OrbitEphemerisMessage.open(file_path)


@pytest.mark.parametrize("file_path", _get_test_files("v2_0", "valid"))
def test_valid_v2_samples(file_path):
    """Verify parsing of valid v2.0 OEM samples

    This test requires external data.
    """
    oem = OrbitEphemerisMessage.open(file_path)
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

    with tempfile.TemporaryDirectory() as tmp_dir:
        written_oem_path = Path(tmp_dir) / "written.oem"
        fmt = "XML" if is_kvn(file_path) else "KVN"
        OrbitEphemerisMessage.convert(file_path, written_oem_path, fmt)
        written_oem = OrbitEphemerisMessage.open(written_oem_path)
        assert written_oem == oem


@pytest.mark.parametrize("file_path", _get_test_files("v2_0", "invalid"))
def test_invalid_v2_samples(file_path):
    """Verify parsing failure for invalid v2.0 OEM samples

    This test requires external data.
    """
    with pytest.raises(Exception):
        OrbitEphemerisMessage.open(file_path)


def test_convert():
    test_file = _get_test_files("v2_0", "valid")[0]
    with tempfile.TemporaryDirectory() as tmp_dir:
        converted_xml_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(
            test_file,
            converted_xml_path,
            "KVN"
        )
        converted_xml = OrbitEphemerisMessage.open(converted_xml_path)

        converted_kvn_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(
            converted_xml_path,
            converted_kvn_path,
            "XML"
        )
        converted_kvn = OrbitEphemerisMessage.open(converted_kvn_path)

        assert converted_xml == converted_kvn


def test_compare():
    test_files = _get_test_files("v2_0", "valid")
    oem1 = OrbitEphemerisMessage.open(test_files[0])
    oem2 = OrbitEphemerisMessage.open(test_files[1])
    assert oem1 == oem1
    assert oem2 == oem2
    assert oem1 != oem2
