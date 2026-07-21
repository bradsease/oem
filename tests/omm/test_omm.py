from pathlib import Path

import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time
from sgp4.api import Satrec
from sgp4.omm import initialize

from oem.omm import COVARIANCE_COMPONENTS, OrbitMeanElementsMessage
from oem.tools import format_epoch

SAMPLE_CASE_DIR = Path(__file__).parent / "samples"
SAMPLE_DIR = SAMPLE_CASE_DIR / "v3_0" / "valid"
V2_SAMPLE_DIR = SAMPLE_CASE_DIR / "v2_0" / "valid"
GLO_OPS_SAMPLE_DIR = SAMPLE_CASE_DIR / "real"


def _sample_cases(validity):
    return sorted(SAMPLE_CASE_DIR.glob(f"v*_0/{validity}/*"))


def _glo_ops_files():
    return sorted(GLO_OPS_SAMPLE_DIR.glob("*/*.*"))


@pytest.fixture
def omm():
    return OrbitMeanElementsMessage.open(SAMPLE_DIR / "sample.omm")


@pytest.fixture
def omm_v2():
    return OrbitMeanElementsMessage.open(V2_SAMPLE_DIR / "sample.omm")


def _parts(omm):
    return (
        omm.header._fields.copy(),
        omm.metadata._fields.copy(),
        omm.data._fields.copy(),
    )


def test_open_kvn(omm):
    assert omm.version == "3.0"
    assert omm.header["CLASSIFICATION"] == "CUI"
    assert omm.header["MESSAGE_ID"] == "ISS-TEST"
    assert omm.metadata["OBJECT_ID"] == "1998-067A"
    assert omm.data["MEAN_MOTION"] == 15.50103472
    assert omm.data["MASS"] == 419725.0
    assert omm.data["NORAD_CAT_ID"] == 25544
    assert omm.data["USER_DEFINED_SOURCE"] == "test fixture"
    assert omm.epoch == Time("2019-12-09T16:38:29.363424", scale="utc")


def test_open_xml_matches_kvn(omm):
    assert OrbitMeanElementsMessage.open(SAMPLE_DIR / "sample.xml") == omm


def test_open_v2_kvn(omm_v2):
    assert omm_v2.version == "2.0"
    assert omm_v2.header["ORIGINATOR"] == "TEST"
    assert omm_v2.metadata["MEAN_ELEMENT_THEORY"] == "SGP/SGP4"
    assert omm_v2.data["BSTAR"] == 3.8792e-05


def test_open_v2_xml_matches_kvn(omm_v2):
    assert OrbitMeanElementsMessage.open(V2_SAMPLE_DIR / "sample.xml") == omm_v2


@pytest.mark.parametrize("file_path", _sample_cases("valid"))
def test_valid_sample_cases(file_path):
    omm = OrbitMeanElementsMessage.open(file_path)
    assert omm.version == file_path.parents[1].name[1:].replace("_", ".")


@pytest.mark.parametrize("file_path", _sample_cases("invalid"))
def test_invalid_sample_cases(file_path):
    with pytest.raises((KeyError, ValueError)):
        OrbitMeanElementsMessage.open(file_path)


@pytest.mark.parametrize("file_path", _glo_ops_files())
def test_glo_ops_real_samples(file_path):
    omm = OrbitMeanElementsMessage.open(file_path)
    assert omm.version == "2.0"
    assert omm.header["CREATION_DATE"] == ""
    assert omm.header["ORIGINATOR"] == ""
    assert omm.data["NORAD_CAT_ID"] == int(file_path.stem)


def test_glo_ops_real_samples_contain_matching_kvn_and_xml_messages():
    kvn_ids = {file_path.stem for file_path in (GLO_OPS_SAMPLE_DIR / "kvn").glob("*")}
    xml_ids = {file_path.stem for file_path in (GLO_OPS_SAMPLE_DIR / "xml").glob("*")}
    assert len(kvn_ids) == 28
    assert kvn_ids == xml_ids


def test_copy_is_equal_and_independent(omm):
    copied = omm.copy()
    assert copied == omm
    copied.data["USER_DEFINED_SOURCE"] = "copy"
    assert copied is not omm
    assert copied != omm
    assert omm.data["USER_DEFINED_SOURCE"] == "test fixture"


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_save_and_open(omm, tmp_path, file_format):
    output_path = tmp_path / f"output.{file_format}"
    omm.save_as(output_path, file_format=file_format)
    assert OrbitMeanElementsMessage.open(output_path) == omm


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_v2_save_and_open(omm_v2, tmp_path, file_format):
    output_path = tmp_path / f"output.{file_format}"
    omm_v2.save_as(output_path, file_format=file_format)
    assert OrbitMeanElementsMessage.open(output_path) == omm_v2
    output = output_path.read_text()
    for field in ("CLASSIFICATION", "MESSAGE_ID", "BTERM", "AGOM"):
        assert f"{field} = " not in output
        assert f"<{field}>" not in output


def test_kvn_output_uses_no_section_delimiters(omm, tmp_path):
    output_path = tmp_path / "output.omm"
    omm.save_as(output_path)
    output = output_path.read_text()
    assert "META_START" not in output
    assert "COVARIANCE_START" not in output


def test_convert_and_compress(omm, tmp_path):
    source = tmp_path / "source.omm"
    output = tmp_path / "output.xml.gz"
    omm.save_as(source)
    OrbitMeanElementsMessage.convert(source, output, "xml", compression="gzip")
    assert OrbitMeanElementsMessage.open(output) == omm


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_complete_covariance_round_trip(omm, tmp_path, file_format):
    omm.data["COV_REF_FRAME"] = "TEME"
    for index, key in enumerate(COVARIANCE_COMPONENTS, start=1):
        omm.data[key] = str(index)
    output = tmp_path / f"covariance.{file_format}"
    omm.save_as(output, file_format=file_format)
    assert OrbitMeanElementsMessage.open(output) == omm


def test_rejects_incomplete_covariance(omm):
    header, metadata, data = _parts(omm)
    data["CX_X"] = "1.0"
    with pytest.raises(ValueError, match="All covariance"):
        OrbitMeanElementsMessage(header, metadata, data)


def test_optional_tle_fields_are_not_required(omm):
    header, metadata, data = _parts(omm)
    for key in (
        "EPHEMERIS_TYPE",
        "CLASSIFICATION_TYPE",
        "ELEMENT_SET_NO",
        "REV_AT_EPOCH",
    ):
        data.pop(key)
    assert (
        OrbitMeanElementsMessage(header, metadata, data).data["NORAD_CAT_ID"] == 25544
    )


def test_sgp4_xp_uses_bterm_and_agom(omm):
    header, metadata, data = _parts(omm)
    metadata["MEAN_ELEMENT_THEORY"] = "SGP4-XP"
    data.pop("BSTAR")
    data.pop("MEAN_MOTION_DDOT")
    data["BTERM"] = "0.01"
    data["AGOM"] = "0.001"
    xp_omm = OrbitMeanElementsMessage(header, metadata, data)
    assert xp_omm.data["BTERM"] == 0.01
    assert xp_omm.data["AGOM"] == 0.001


def test_at_matches_sgp4(omm):
    epoch = omm.epoch + 600 * u.s
    fields = omm.data._fields.copy()
    fields["OBJECT_ID"] = omm.metadata["OBJECT_ID"]
    fields["MEAN_MOTION"] = str(omm.data["MEAN_MOTION"])
    fields["MASS"] = str(omm.data["MASS"])
    fields["EPOCH"] = format_epoch(omm.epoch)
    satellite = Satrec()
    initialize(satellite, fields)
    error, position, velocity = satellite.sgp4(epoch.utc.jd1, epoch.utc.jd2)

    state = omm.at(epoch)

    assert error == 0
    assert state.epoch == epoch
    assert state.frame == "TEME"
    assert state.center == "EARTH"
    np.testing.assert_allclose(state.position, position)
    np.testing.assert_allclose(state.velocity, velocity)


@pytest.mark.parametrize(
    "section, changes, message",
    (
        ("header", {"CCSDS_OMM_VERS": "1.0"}, "Unsupported OMM version"),
        (
            "data",
            {"SEMI_MAJOR_AXIS": "6800"},
            "Exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION",
        ),
        (
            "data",
            {"MEAN_MOTION": None},
            "Exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION",
        ),
    ),
)
def test_validation(omm, section, changes, message):
    header, metadata, data = _parts(omm)
    target = {"header": header, "metadata": metadata, "data": data}[section]
    for key, value in changes.items():
        if value is None:
            target.pop(key)
        else:
            target[key] = value
    with pytest.raises(ValueError, match=message):
        OrbitMeanElementsMessage(header, metadata, data)


@pytest.mark.parametrize("field", ("CREATION_DATE", "ORIGINATOR"))
def test_required_header_fields_must_be_present(omm, field):
    header, metadata, data = _parts(omm)
    header.pop(field)
    with pytest.raises(KeyError, match=field):
        OrbitMeanElementsMessage(header, metadata, data)


@pytest.mark.parametrize(
    "section, changes, message",
    (
        ("header", {"CCSDS_OMM_VERS": "1.0"}, "Unsupported OMM version"),
        ("header", {"CLASSIFICATION": "CUI"}, "CLASSIFICATION.*v2.0"),
        ("header", {"MESSAGE_ID": "ISS-TEST"}, "MESSAGE_ID.*v2.0"),
        ("data", {"BTERM": "0.01"}, "BTERM.*v2.0"),
        ("data", {"AGOM": "0.001"}, "AGOM.*v2.0"),
        ("metadata", {"MEAN_ELEMENT_THEORY": "SGP4-XP"}, "SGP4-XP.*v2.0"),
        (
            "data",
            {"SEMI_MAJOR_AXIS": "6800"},
            "Exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION",
        ),
    ),
)
def test_v2_validation(omm_v2, section, changes, message):
    header, metadata, data = _parts(omm_v2)
    target = {"header": header, "metadata": metadata, "data": data}[section]
    target.update(changes)
    with pytest.raises(ValueError, match=message):
        OrbitMeanElementsMessage(header, metadata, data)


@pytest.mark.parametrize("field", ("MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"))
def test_v2_sgp_requires_mean_motion_derivatives(omm_v2, field):
    header, metadata, data = _parts(omm_v2)
    metadata["MEAN_ELEMENT_THEORY"] = "SGP"
    data.pop(field)
    with pytest.raises(ValueError, match=f"{field} is required for SGP"):
        OrbitMeanElementsMessage(header, metadata, data)


def test_at_requires_scalar_time(omm):
    with pytest.raises(TypeError, match="scalar"):
        omm.at(Time(["2019-12-09T16:38:29"], scale="utc"))
