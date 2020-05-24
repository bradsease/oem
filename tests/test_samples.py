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
        if is_kvn(file_path):
            oem.save_as(written_oem_path, file_format="XML")
        else:
            oem.save_as(written_oem_path, file_format="KVN")
        written_oem = OrbitEphemerisMessage.open(written_oem_path)
        assert written_oem.version == oem.version


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
        if is_kvn(file_path):
            oem.save_as(written_oem_path, file_format="XML")
        else:
            oem.save_as(written_oem_path, file_format="KVN")
        written_oem = OrbitEphemerisMessage.open(written_oem_path)
        assert written_oem.version == oem.version


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

        assert converted_xml.version == converted_kvn.version
