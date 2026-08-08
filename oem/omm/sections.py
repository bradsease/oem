"""Typed OMM sections and validation constraints."""

import re
from typing import Dict, Mapping, Union, cast

from astropy.time import Time

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
    MEAN_ELEMENT_FIELDS,
    SPACECRAFT_PARAMETER_FIELDS,
    SUPPORTED_VERSIONS,
    TLE_PARAMETER_FIELDS,
    VERSION,
    _KVN_UNITS,
)


def _parse_float(value: str, metadata: object) -> float:
    return float(value)


_DATA_FIELDS = set(
    MEAN_ELEMENT_FIELDS
    + SPACECRAFT_PARAMETER_FIELDS
    + TLE_PARAMETER_FIELDS
    + COVARIANCE_FIELDS
)
_UNIT_ANNOTATION = re.compile(r"(\S+)\s+\[([^\[\]]+)\]")


def _discard_unit_annotation(key: str, value: str) -> str:
    if "[" not in value and "]" not in value:
        return value
    if key not in _DATA_FIELDS:
        return value
    match = _UNIT_ANNOTATION.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid unit annotation for OMM field '{key}'")
    if key not in _KVN_UNITS:
        raise ValueError(f"Unit annotation is not allowed for OMM field '{key}'")
    numeric, unit = match.groups()
    expected = _KVN_UNITS[key]
    if unit != expected:
        raise ValueError(
            f"Invalid unit annotation for OMM field '{key}': "
            f"expected [{expected}], got [{unit}]"
        )
    return numeric


def _parse_data_epoch(value: str, data: KeyValueSection) -> Time:
    return parse_epoch(value, cast("OmmData", data).metadata)


class OmmKeyValueSection(KeyValueSection):
    """Base class for typed OMM sections."""

    _constraint_spec = ConstraintSpecification()

    def __init__(self, fields: Mapping[str, object], version: str = VERSION) -> None:
        self._version = version
        self._parse_fields({key: str(value).strip() for key, value in fields.items()})
        self._constraint_spec.apply(self)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, OmmKeyValueSection)
            and type(self) is type(other)
            and self._fields.keys() == other._fields.keys()
            and all(self[key] == other[key] for key in self)
        )

    @property
    def version(self) -> str:
        return self._version


class ConstrainOmmVersion(Constraint):
    versions = ["*"]

    def func(self, header: "OmmHeader") -> None:
        require(
            header.version in SUPPORTED_VERSIONS,
            f"Unsupported OMM version: {header.version}",
        )


class ConstrainOmmV2Header(Constraint):
    versions = ["2.0"]

    def func(self, header: "OmmHeader") -> None:
        for field in ("CLASSIFICATION", "MESSAGE_ID"):
            require(
                field not in header,
                f"Header keyword '{field}' not supported in OMM v2.0",
            )


class OmmHeader(OmmKeyValueSection):
    _field_spec = {
        "CCSDS_OMM_VERS": HeaderField(parse_str, str, required=True),
        "CLASSIFICATION": HeaderField(parse_str, str),
        "CREATION_DATE": HeaderField(parse_utc, format_epoch, required=True),
        "ORIGINATOR": HeaderField(parse_str, str, required=True),
        "MESSAGE_ID": HeaderField(parse_str, str),
    }
    _constraint_spec = ConstraintSpecification(
        ConstrainOmmVersion, ConstrainOmmV2Header
    )

    def __getitem__(self, key: str) -> Union[str, Time]:
        if key == "CREATION_DATE" and not self._fields[key]:
            return ""
        return super().__getitem__(key)

    @property
    def version(self) -> str:
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
    versions = SUPPORTED_VERSIONS

    def func(self, data: "OmmData") -> None:
        has_axis = "SEMI_MAJOR_AXIS" in data
        has_motion = "MEAN_MOTION" in data
        require(
            has_axis != has_motion,
            "Exactly one of SEMI_MAJOR_AXIS or MEAN_MOTION is required",
        )
        require(
            0 <= cast(float, data["ECCENTRICITY"]) < 1,
            "ECCENTRICITY must be greater than or equal to zero and less than one",
        )
        if has_axis:
            require(
                cast(float, data["SEMI_MAJOR_AXIS"]) > 0,
                "SEMI_MAJOR_AXIS must be positive",
            )
        if has_motion:
            require(
                cast(float, data["MEAN_MOTION"]) > 0,
                "MEAN_MOTION must be positive",
            )

        covariance = [key for key in COVARIANCE_COMPONENTS if key in data]
        if covariance:
            require(
                len(covariance) == len(COVARIANCE_COMPONENTS),
                "All covariance matrix elements are required when any are provided",
            )
        if "COV_REF_FRAME" in data:
            require(
                bool(covariance), "COV_REF_FRAME requires covariance matrix elements"
            )

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

        if "CLASSIFICATION_TYPE" in data:
            require(
                len(cast(str, data["CLASSIFICATION_TYPE"])) == 1,
                "CLASSIFICATION_TYPE must be one character",
            )


class ConstrainOmmV2Data(Constraint):
    versions = ["2.0"]

    def func(self, data: "OmmData") -> None:
        for field in ("BTERM", "AGOM"):
            require(
                field not in data,
                f"Data keyword '{field}' not supported in OMM v2.0",
            )
        require(
            data.metadata["MEAN_ELEMENT_THEORY"].upper() != "SGP4-XP",
            "SGP4-XP is not supported in OMM v2.0",
        )
        if data.metadata["MEAN_ELEMENT_THEORY"].upper() == "SGP":
            require(
                "MEAN_MOTION_DOT" in data,
                "MEAN_MOTION_DOT is required for SGP OMMs",
            )
            require(
                "MEAN_MOTION_DDOT" in data,
                "MEAN_MOTION_DDOT is required for SGP OMMs",
            )


class ConstrainOmmV3Data(Constraint):
    versions = [VERSION]

    def func(self, data: "OmmData") -> None:
        theory = data.metadata["MEAN_ELEMENT_THEORY"].upper()
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
    _constraint_spec = ConstraintSpecification(
        ConstrainOmmData, ConstrainOmmV2Data, ConstrainOmmV3Data
    )

    def __init__(
        self,
        fields: Mapping[str, object],
        metadata: OmmMetadata,
        version: str = VERSION,
    ) -> None:
        self.metadata = metadata
        super().__init__(
            {
                key: _discard_unit_annotation(key, str(value).strip())
                for key, value in fields.items()
            },
            version=version,
        )

    def __getitem__(self, key: str) -> Union[str, int, float, Time]:
        if key.startswith("USER_DEFINED_"):
            return self._fields[key]
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Union[str, int, float, Time]) -> None:
        if key.startswith("USER_DEFINED_"):
            self._fields[key] = str(value)
        else:
            text = str(value).strip()
            super().__setitem__(key, _discard_unit_annotation(key, text))

    def _validate_fields(self, fields: Dict[str, str]) -> None:
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
