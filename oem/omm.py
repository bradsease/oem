"""CCSDS Orbit Mean-Elements Message (OMM) support."""

from astropy.time import Time
from defusedxml.ElementTree import parse as parse_xml
from lxml.etree import Element, ElementTree, SubElement

from oem.base import Constraint, ConstraintSpecification, HeaderField, KeyValueSection
from oem.components.types import State
from oem.tools import (
    _open,
    format_epoch,
    is_kvn,
    parse_epoch,
    parse_integer,
    parse_str,
    parse_utc,
    require,
)

VERSION = "3.0"
HEADER_FIELDS = (
    "CCSDS_OMM_VERS",
    "CLASSIFICATION",
    "CREATION_DATE",
    "ORIGINATOR",
    "MESSAGE_ID",
)
METADATA_FIELDS = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "REF_FRAME_EPOCH",
    "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY",
)
MEAN_ELEMENT_FIELDS = (
    "EPOCH",
    "SEMI_MAJOR_AXIS",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "GM",
)
SPACECRAFT_PARAMETER_FIELDS = (
    "MASS",
    "SOLAR_RAD_AREA",
    "SOLAR_RAD_COEFF",
    "DRAG_AREA",
    "DRAG_COEFF",
)
TLE_PARAMETER_FIELDS = (
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "NORAD_CAT_ID",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
    "BSTAR",
    "BTERM",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
    "AGOM",
)
COVARIANCE_FIELDS = (
    "COV_REF_FRAME",
    "CX_X",
    "CY_X",
    "CY_Y",
    "CZ_X",
    "CZ_Y",
    "CZ_Z",
    "CX_DOT_X",
    "CX_DOT_Y",
    "CX_DOT_Z",
    "CX_DOT_X_DOT",
    "CY_DOT_X",
    "CY_DOT_Y",
    "CY_DOT_Z",
    "CY_DOT_X_DOT",
    "CY_DOT_Y_DOT",
    "CZ_DOT_X",
    "CZ_DOT_Y",
    "CZ_DOT_Z",
    "CZ_DOT_X_DOT",
    "CZ_DOT_Y_DOT",
    "CZ_DOT_Z_DOT",
)
COVARIANCE_COMPONENTS = COVARIANCE_FIELDS[1:]
NUMERIC_DATA_FIELDS = (
    set(MEAN_ELEMENT_FIELDS)
    | set(SPACECRAFT_PARAMETER_FIELDS)
    | set(TLE_PARAMETER_FIELDS)
    | set(COVARIANCE_COMPONENTS)
) - {"EPOCH", "EPHEMERIS_TYPE", "NORAD_CAT_ID", "ELEMENT_SET_NO", "REV_AT_EPOCH"}


def _parse_float(value, metadata):
    """Parse an OMM number while accepting its optional unit annotation."""
    return float(value.partition("[")[0].strip())


def _parse_data_epoch(value, data):
    return parse_epoch(value, data.metadata)


def _local_name(element):
    return element.tag.rpartition("}")[-1]


def _xml_fields(parent):
    fields = {}
    for child in parent:
        key = _local_name(child)
        if key == "COMMENT":
            continue
        if key in fields:
            raise ValueError(f"Duplicate OMM XML field: {key}")
        fields[key] = (child.text or "").strip()
    return fields


def _add_fields(target, fields):
    duplicate = next((key for key in fields if key in target), None)
    if duplicate:
        raise ValueError(f"Duplicate OMM field: {duplicate}")
    target.update(fields)


def _parse_xml_user_defined(parent):
    fields = {}
    for child in parent:
        if _local_name(child) != "USER_DEFINED":
            raise ValueError("Invalid OMM XML user-defined parameter")
        parameter = child.attrib.get("parameter", "")
        if not parameter:
            raise ValueError("OMM XML user-defined parameter is missing its name")
        _add_fields(fields, {f"USER_DEFINED_{parameter}": (child.text or "").strip()})
    return fields


def _parse_kvn(file_obj):
    sections = {"header": {}, "metadata": {}, "data": {}}
    phase = "header"
    for number, raw_line in enumerate(file_obj, start=1):
        line = raw_line.strip()
        if not line or line.startswith("COMMENT"):
            continue
        if line.endswith("_START") or line.endswith("_STOP"):
            raise ValueError(f"Invalid OMM delimiter on line {number}: {line}")
        if "=" not in line:
            raise ValueError(f"Invalid OMM entry on line {number}")
        key, value = (entry.strip() for entry in line.split("=", 1))
        if not key or not value:
            raise ValueError(f"Invalid OMM entry on line {number}")
        if key in HEADER_FIELDS:
            if phase != "header":
                raise ValueError(f"Header field after OMM data on line {number}")
            target = sections["header"]
        elif key in METADATA_FIELDS:
            if phase == "data":
                raise ValueError(f"Metadata field after OMM data on line {number}")
            phase = "metadata"
            target = sections["metadata"]
        else:
            phase = "data"
            target = sections["data"]
        _add_fields(target, {key: value})
    return sections["header"], sections["metadata"], sections["data"]


def _parse_xml(file_obj):
    root = parse_xml(file_obj).getroot()
    if _local_name(root) != "omm":
        raise ValueError("XML document is not an OMM")
    header_element = next(
        (child for child in root if _local_name(child) == "header"), None
    )
    body_element = next((child for child in root if _local_name(child) == "body"), None)
    if header_element is None or body_element is None:
        raise ValueError("OMM XML must contain header and body elements")
    segments = [child for child in body_element if _local_name(child) == "segment"]
    if len(segments) != 1:
        raise ValueError("OMM XML must contain exactly one segment")
    metadata_element = next(
        (child for child in segments[0] if _local_name(child) == "metadata"), None
    )
    data_element = next(
        (child for child in segments[0] if _local_name(child) == "data"), None
    )
    if metadata_element is None or data_element is None:
        raise ValueError("OMM XML segment must contain metadata and data")

    header = _xml_fields(header_element)
    _add_fields(header, {"CCSDS_OMM_VERS": root.attrib.get("version", "")})
    data = {}
    expected_sections = {
        "meanElements",
        "spacecraftParameters",
        "tleParameters",
        "covarianceMatrix",
        "userDefinedParameters",
    }
    for child in data_element:
        name = _local_name(child)
        if name == "COMMENT":
            continue
        if name not in expected_sections:
            raise ValueError(f"Invalid OMM XML data section: {name}")
        fields = (
            _parse_xml_user_defined(child)
            if name == "userDefinedParameters"
            else _xml_fields(child)
        )
        _add_fields(data, fields)
    return header, _xml_fields(metadata_element), data


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


class OrbitMeanElementsMessage(object):
    """Python representation of a CCSDS OMM version 3.0.

    An OMM comprises one header, one metadata block, and one data block. The
    data block contains the five logical OMM data groups defined by CCSDS.
    """

    def __init__(self, header, metadata, data):
        self.header = OmmHeader(header)
        self.metadata = OmmMetadata(metadata, version=self.header.version)
        self.data = OmmData(data, self.metadata, version=self.header.version)

    def __eq__(self, other):
        return (
            isinstance(other, OrbitMeanElementsMessage)
            and self.header == other.header
            and self.metadata == other.metadata
            and self.data == other.data
        )

    def __repr__(self):
        return f"OrbitMeanElementsMessage(v{self.version})"

    def __call__(self, epoch):
        return self.at(epoch)

    @classmethod
    def open(cls, file_path):
        """Open a KVN or XML OMM file."""
        with _open(file_path, "rt") as omm_file:
            parts = _parse_kvn(omm_file) if is_kvn(file_path) else _parse_xml(omm_file)
        return cls(*parts)

    @classmethod
    def convert(cls, in_file_path, out_file_path, file_format, **save_args):
        """Convert an OMM between KVN and XML formats."""
        cls.open(in_file_path).save_as(out_file_path, file_format, **save_args)

    def at(self, epoch):
        """Propagate an SGP4 OMM at a scalar Astropy :class:`~astropy.time.Time`."""
        if not isinstance(epoch, Time) or not epoch.isscalar:
            raise TypeError("epoch must be a scalar astropy.time.Time")
        if self.metadata["MEAN_ELEMENT_THEORY"].upper() not in ("SGP4", "SGP/SGP4"):
            raise ValueError("SGP4 propagation requires an SGP4 mean element theory")
        try:
            from sgp4.api import SGP4_ERRORS, Satrec
            from sgp4.omm import initialize
        except ImportError as error:
            raise ImportError("SGP4 propagation requires the 'sgp4' package") from error

        fields = self.data._fields.copy()
        for key in NUMERIC_DATA_FIELDS & fields.keys():
            fields[key] = str(self.data[key])
        fields["OBJECT_ID"] = self.metadata["OBJECT_ID"]
        fields.setdefault("EPHEMERIS_TYPE", "0")
        fields.setdefault("CLASSIFICATION_TYPE", "U")
        fields.setdefault("ELEMENT_SET_NO", "0")
        fields.setdefault("REV_AT_EPOCH", "0")
        fields.setdefault("MEAN_MOTION_DOT", "0")
        fields.setdefault("MEAN_MOTION_DDOT", "0")
        fields["EPOCH"] = format_epoch(self.epoch)
        satellite = Satrec()
        initialize(satellite, fields)
        error, position, velocity = satellite.sgp4(epoch.utc.jd1, epoch.utc.jd2)
        if error:
            detail = SGP4_ERRORS.get(error, "unknown error")
            raise ValueError(f"SGP4 propagation failed: {detail}")
        return State(
            epoch,
            "TEME",
            self.metadata["CENTER_NAME"],
            position,
            velocity,
            version=self.version,
        )

    def save_as(self, file_path, file_format="kvn", compression=None):
        """Write this OMM as KVN or XML."""
        with _open(file_path, "wb", compression) as output_file:
            if file_format == "kvn":
                output_file.write(self._to_kvn().encode("utf-8"))
            elif file_format == "xml":
                self._to_xml().write(
                    output_file,
                    pretty_print=True,
                    encoding="utf-8",
                    xml_declaration=True,
                )
            else:
                raise ValueError(f"Unrecognized file type: {file_format!r}")

    def copy(self):
        """Create an independent copy of this OMM."""
        return OrbitMeanElementsMessage(
            self.header._fields.copy(),
            self.metadata._fields.copy(),
            self.data._fields.copy(),
        )

    def _to_kvn(self):
        lines = self._format_fields(self.header, HEADER_FIELDS)
        lines.append("")
        lines.extend(self._format_fields(self.metadata, METADATA_FIELDS))
        lines.append("")
        lines.extend(self._format_fields(self.data, MEAN_ELEMENT_FIELDS))
        lines.extend(self._format_fields(self.data, SPACECRAFT_PARAMETER_FIELDS))
        lines.extend(self._format_fields(self.data, TLE_PARAMETER_FIELDS))
        lines.extend(self._format_fields(self.data, COVARIANCE_FIELDS))
        lines.extend(
            f"{key} = {value}"
            for key, value in self.data._fields.items()
            if key.startswith("USER_DEFINED_")
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_fields(section, order):
        return [f"{key} = {section._fields[key]}" for key in order if key in section]

    def _to_xml(self):
        root = Element("omm", id="CCSDS_OMM_VERS", version=self.version)
        self._xml_section(
            root, "header", self.header, HEADER_FIELDS, omit=("CCSDS_OMM_VERS",)
        )
        body = SubElement(root, "body")
        segment = SubElement(body, "segment")
        self._xml_section(segment, "metadata", self.metadata, METADATA_FIELDS)
        data = SubElement(segment, "data")
        self._xml_section(data, "meanElements", self.data, MEAN_ELEMENT_FIELDS)
        if any(key in self.data for key in SPACECRAFT_PARAMETER_FIELDS):
            self._xml_section(
                data, "spacecraftParameters", self.data, SPACECRAFT_PARAMETER_FIELDS
            )
        if any(key in self.data for key in TLE_PARAMETER_FIELDS):
            self._xml_section(data, "tleParameters", self.data, TLE_PARAMETER_FIELDS)
        if any(key in self.data for key in COVARIANCE_FIELDS):
            self._xml_section(data, "covarianceMatrix", self.data, COVARIANCE_FIELDS)
        user_defined = [
            key for key in self.data._fields if key.startswith("USER_DEFINED_")
        ]
        if user_defined:
            section = SubElement(data, "userDefinedParameters")
            for key in user_defined:
                parameter = key[len("USER_DEFINED_") :]
                SubElement(section, "USER_DEFINED", parameter=parameter).text = (
                    self.data._fields[key]
                )
        return ElementTree(root)

    @staticmethod
    def _xml_section(parent, name, section, fields, omit=()):
        element = SubElement(parent, name)
        for key in fields:
            if key in section and key not in omit:
                SubElement(element, key).text = section._fields[key]
        return element

    @property
    def epoch(self):
        """The mean-element epoch as an Astropy ``Time``."""
        return self.data["EPOCH"]

    @property
    def version(self):
        """The CCSDS OMM version."""
        return self.header.version
