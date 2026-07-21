"""Typed OMM sections and validation constraints."""

from oem.base import Constraint, ConstraintSpecification, HeaderField, KeyValueSection
from oem.tools import (
    format_epoch,
    parse_epoch,
    parse_integer,
    parse_str,
    parse_utc,
    require,
)

from .fields import (
    COVARIANCE_COMPONENTS,
    COVARIANCE_FIELDS,
    SPACECRAFT_PARAMETER_FIELDS,
    VERSION,
)


def _parse_float(value, metadata):
    """Parse an OMM number while accepting its optional unit annotation."""
    return float(value.partition("[")[0].strip())


def _parse_data_epoch(value, data):
    return parse_epoch(value, data.metadata)


class OmmKeyValueSection(KeyValueSection):
    """Base class for typed OMM sections."""

    _constraint_spec = ConstraintSpecification()

    def __init__(self, fields, version=VERSION):
        self._version = version
        self._parse_fields({key: str(value).strip() for key, value in fields.items()})
        self._constraint_spec.apply(self)

    def __eq__(self, other):
        return (
            type(self) is type(other)
            and self._fields.keys() == other._fields.keys()
            and all(self[key] == other[key] for key in self)
        )

    @property
    def version(self):
        return self._version


class ConstrainOmmVersion(Constraint):
    versions = ["*"]

    def func(self, header):
        require(header.version == VERSION, f"Unsupported OMM version: {header.version}")


class OmmHeader(OmmKeyValueSection):
    _field_spec = {
        "CCSDS_OMM_VERS": HeaderField(parse_str, str, required=True),
        "CLASSIFICATION": HeaderField(parse_str, str),
        "CREATION_DATE": HeaderField(parse_utc, format_epoch, required=True),
        "ORIGINATOR": HeaderField(parse_str, str, required=True),
        "MESSAGE_ID": HeaderField(parse_str, str),
    }
    _constraint_spec = ConstraintSpecification(ConstrainOmmVersion)

    @property
    def version(self):
        return self["CCSDS_OMM_VERS"]


class OmmMetadata(OmmKeyValueSection):
    _field_spec = {
        "OBJECT_NAME": HeaderField(parse_str, str, required=True),
        "OBJECT_ID": HeaderField(parse_str, str, required=True),
        "CENTER_NAME": HeaderField(parse_str, str, required=True),
        "REF_FRAME": HeaderField(parse_str, str, required=True),
        "REF_FRAME_EPOCH": HeaderField(parse_epoch, format_epoch),
        "TIME_SYSTEM": HeaderField(parse_str, str, required=True),
        "MEAN_ELEMENT_THEORY": HeaderField(parse_str, str, required=True),
    }


class ConstrainOmmData(Constraint):
    versions = [VERSION]

    def func(self, data):
        has_axis = "SEMI_MAJOR_AXIS" in data
        has_motion = "MEAN_MOTION" in data
        require(
            has_axis != has_motion,
            "Exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION is required",
        )
        require(
            0 <= data["ECCENTRICITY"] < 1,
            "ECCENTRICITY must be greater than or equal to zero and less than one",
        )
        if has_axis:
            require(data["SEMI_MAJOR_AXIS"] > 0, "SEMI_MAJOR_AXIS must be positive")
        if has_motion:
            require(data["MEAN_MOTION"] > 0, "MEAN_MOTION must be positive")

        covariance = [key for key in COVARIANCE_COMPONENTS if key in data]
        if covariance:
            require(
                len(covariance) == len(COVARIANCE_COMPONENTS),
                "All covariance matrix elements are required when any are provided",
            )
        if "COV_REF_FRAME" in data:
            require(covariance, "COV_REF_FRAME requires covariance matrix elements")

        theory = data.metadata["MEAN_ELEMENT_THEORY"].upper()
        sgp_theories = ("SGP", "SGP4", "SGP/SGP4", "SGP4-XP")
        if theory in sgp_theories:
            require(has_motion, "MEAN_MOTION is required for SGP-based OMMs")
            require(
                data.metadata["CENTER_NAME"].upper() == "EARTH",
                "CENTER_NAME must be EARTH for SGP-based OMMs",
            )
            require(
                data.metadata["REF_FRAME"].upper() == "TEME",
                "REF_FRAME must be TEME for SGP-based OMMs",
            )
            require(
                data.metadata["TIME_SYSTEM"].upper() == "UTC",
                "TIME_SYSTEM must be UTC for SGP-based OMMs",
            )
        if theory in sgp_theories:
            require(
                "NORAD_CAT_ID" in data, "NORAD_CAT_ID is required for SGP-based OMMs"
            )
        if theory in ("SGP4", "SGP/SGP4"):
            require("BSTAR" in data, "BSTAR is required for SGP4 OMMs")
        if theory == "SGP4-XP":
            require("BTERM" in data, "BTERM is required for SGP4-XP OMMs")
            require("AGOM" in data, "AGOM is required for SGP4-XP OMMs")
        if theory in ("SGP", "PPT3"):
            require(
                "MEAN_MOTION_DOT" in data,
                "MEAN_MOTION_DOT is required for SGP and PPT3 OMMs",
            )
            require(
                "MEAN_MOTION_DDOT" in data,
                "MEAN_MOTION_DDOT is required for SGP and PPT3 OMMs",
            )
        require(
            not ({"BSTAR", "BTERM"} <= set(data)),
            "BSTAR and BTERM cannot both be provided",
        )
        require(
            not ({"MEAN_MOTION_DDOT", "AGOM"} <= set(data)),
            "MEAN_MOTION_DDOT and AGOM cannot both be provided",
        )
        if "CLASSIFICATION_TYPE" in data:
            require(
                len(data["CLASSIFICATION_TYPE"]) == 1,
                "CLASSIFICATION_TYPE must be one character",
            )


class OmmData(OmmKeyValueSection):
    _field_spec = {
        "EPOCH": HeaderField(_parse_data_epoch, format_epoch, required=True),
        "SEMI_MAJOR_AXIS": HeaderField(_parse_float, str),
        "MEAN_MOTION": HeaderField(_parse_float, str),
        "ECCENTRICITY": HeaderField(_parse_float, str, required=True),
        "INCLINATION": HeaderField(_parse_float, str, required=True),
        "RA_OF_ASC_NODE": HeaderField(_parse_float, str, required=True),
        "ARG_OF_PERICENTER": HeaderField(_parse_float, str, required=True),
        "MEAN_ANOMALY": HeaderField(_parse_float, str, required=True),
        "GM": HeaderField(_parse_float, str),
        **{
            field: HeaderField(_parse_float, str)
            for field in SPACECRAFT_PARAMETER_FIELDS
        },
        "EPHEMERIS_TYPE": HeaderField(parse_integer, str),
        "CLASSIFICATION_TYPE": HeaderField(parse_str, str),
        "NORAD_CAT_ID": HeaderField(parse_integer, str),
        "ELEMENT_SET_NO": HeaderField(parse_integer, str),
        "REV_AT_EPOCH": HeaderField(parse_integer, str),
        "BSTAR": HeaderField(_parse_float, str),
        "BTERM": HeaderField(_parse_float, str),
        "MEAN_MOTION_DOT": HeaderField(_parse_float, str),
        "MEAN_MOTION_DDOT": HeaderField(_parse_float, str),
        "AGOM": HeaderField(_parse_float, str),
        **{
            field: HeaderField(
                parse_str if field == "COV_REF_FRAME" else _parse_float, str
            )
            for field in COVARIANCE_FIELDS
        },
    }
    _constraint_spec = ConstraintSpecification(ConstrainOmmData)

    def __init__(self, fields, metadata, version=VERSION):
        self.metadata = metadata
        super().__init__(fields, version=version)

    def __getitem__(self, key):
        if key.startswith("USER_DEFINED_"):
            return self._fields[key]
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key.startswith("USER_DEFINED_"):
            self._fields[key] = str(value)
        else:
            super().__setitem__(key, value)

    def _validate_fields(self, fields):
        invalid = [
            key
            for key in fields
            if key not in self._field_spec and not key.startswith("USER_DEFINED_")
        ]
        if invalid:
            raise KeyError(f"Invalid header key: {invalid[0]}")
        super()._validate_fields(
            {
                key: value
                for key, value in fields.items()
                if not key.startswith("USER_DEFINED_")
            }
        )
