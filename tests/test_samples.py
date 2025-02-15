"""Test parsing sample OEMS.
"""

import glob
import tempfile
from pathlib import Path

import pytest

from oem import OrbitEphemerisMessage
from oem.tools import is_kvn

SAMPLE_DIR = Path(__file__).parent / "samples"


def _get_test_files(version="*", validity="*"):
    samples = SAMPLE_DIR / version / validity / "*.oem*"
    return sorted([entry for entry in glob.glob(str(samples))])


@pytest.mark.parametrize("file_path", _get_test_files(validity="valid"))
def test_valid_samples(file_path):
    oem = OrbitEphemerisMessage.open(file_path)
    assert oem.span[0] <= oem.span[1]

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
        fmt = "xml" if is_kvn(file_path) else "kvn"
        OrbitEphemerisMessage.convert(file_path, written_oem_path, fmt)
        written_oem = OrbitEphemerisMessage.open(written_oem_path)
        assert written_oem == oem


@pytest.mark.parametrize("file_path", _get_test_files(validity="invalid"))
def test_invalid_samples(file_path):
    with pytest.raises(Exception):
        OrbitEphemerisMessage.open(file_path)


@pytest.mark.parametrize("file_path", _get_test_files(validity="valid"))
def test_convert(file_path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        converted_xml_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(file_path, converted_xml_path, "kvn")
        converted_xml = OrbitEphemerisMessage.open(converted_xml_path)

        converted_kvn_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(
            converted_xml_path, converted_kvn_path, "xml", compression="gzip"
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


@pytest.mark.parametrize("file_path", _get_test_files(validity="valid"))
def test_copy(file_path):
    oem1 = OrbitEphemerisMessage.open(file_path)
    oem2 = oem1.copy()
    assert oem1 is not oem2 and oem1 == oem2


@pytest.mark.parametrize("compression", ("gzip", "bz2", "lzma"))
def test_compression(compression):
    file_path = _get_test_files(validity="valid")[0]
    oem = OrbitEphemerisMessage.open(file_path)
    with tempfile.TemporaryDirectory() as tmp_dir:
        written_oem_path = Path(tmp_dir) / "written.oem"
        oem.save_as(written_oem_path, compression=compression)
        oem_readback = OrbitEphemerisMessage.open(written_oem_path)
        assert oem == oem_readback
