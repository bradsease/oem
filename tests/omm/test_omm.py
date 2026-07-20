from pathlib import Path

import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time
from sgp4.api import Satrec
from sgp4.omm import initialize

from oem.omm import COVARIANCE_COMPONENTS, OrbitMeanElementsMessage
from oem.tools import format_epoch

SAMPLE_DIR = Path(__file__).parent / "v3_0"
CELESTRAK_SAMPLE_DIR = Path(__file__).parent / "v2_0"


@pytest.fixture
def omm():
    return OrbitMeanElementsMessage.open(SAMPLE_DIR / "sample.omm")


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


@pytest.mark.parametrize(
    "file_name", ("celestrak-glo-ops.omm", "celestrak-glo-ops.xml")
)
def test_celestrak_v2_examples_are_rejected(file_name):
    with pytest.raises(ValueError):
        OrbitMeanElementsMessage.open(CELESTRAK_SAMPLE_DIR / file_name)


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
        ("header", {"CCSDS_OMM_VERS": "2.0"}, "Unsupported OMM version"),
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


def test_at_requires_scalar_time(omm):
    with pytest.raises(TypeError, match="scalar"):
        omm.at(Time(["2019-12-09T16:38:29"], scale="utc"))
