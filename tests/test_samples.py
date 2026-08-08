"""Test parsing sample OEMS."""

import glob
import gzip
import tempfile
from pathlib import Path

import pytest

from oem import OrbitEphemerisMessage
from oem.tools import is_kvn

SAMPLE_DIR = Path(__file__).parent / "samples"

pytestmark = pytest.mark.filterwarnings("ignore:Unsupported TIME_SYSTEM 'abcd'")


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


@pytest.mark.parametrize("number_format", ("scientific", "fixed_cm"))
@pytest.mark.parametrize("file_path", _get_test_files(validity="valid"))
def test_convert(file_path, number_format):
    with tempfile.TemporaryDirectory() as tmp_dir:
        converted_xml_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(
            file_path, converted_xml_path, "kvn", number_format=number_format
        )
        converted_xml = OrbitEphemerisMessage.open(converted_xml_path)

        converted_kvn_path = Path(tmp_dir) / "written.oem"
        OrbitEphemerisMessage.convert(
            converted_xml_path,
            converted_kvn_path,
            "xml",
            compression="gzip",
            number_format=number_format,
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


@pytest.mark.parametrize("prefix", ("", "\n\t<!-- leading comment -->\n"))
def test_open_declaration_free_xml(prefix, tmp_path):
    source = Path(_get_test_files(validity="valid")[0])
    xml_path = tmp_path / "declaration-free.xml"
    OrbitEphemerisMessage.open(source).save_as(xml_path, file_format="xml")
    xml_path.write_text(prefix + xml_path.read_text().split("\n", 1)[1])

    assert OrbitEphemerisMessage.open(xml_path) == OrbitEphemerisMessage.open(source)


def test_open_declaration_free_compressed_xml(tmp_path):
    source = Path(_get_test_files(validity="valid")[0])
    xml_path = tmp_path / "declaration-free.xml.gz"
    oem = OrbitEphemerisMessage.open(source)
    oem.save_as(xml_path, file_format="xml", compression="gzip")

    with gzip.open(xml_path, "rt") as compressed_file:
        contents = compressed_file.read().split("\n", 1)[1]
    with gzip.open(xml_path, "wt") as compressed_file:
        compressed_file.write(contents)

    assert OrbitEphemerisMessage.open(xml_path) == oem


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_save_as(file_format, tmp_path):
    oem = OrbitEphemerisMessage.open(_get_test_files(validity="valid")[0])
    output_path = tmp_path / f"output.{file_format}"
    oem.save_as(output_path, file_format=file_format)
    assert OrbitEphemerisMessage.open(output_path) == oem


def test_save_as_invalid_file_format_preserves_existing_file(tmp_path):
    oem = OrbitEphemerisMessage.open(_get_test_files(validity="valid")[0])
    output_path = tmp_path / "output.oem"
    output_path.write_text("existing output")

    with pytest.raises(ValueError, match="Unrecognized file type"):
        oem.save_as(output_path, file_format="unsupported")

    assert output_path.read_text() == "existing output"
