from lxml.etree import SubElement

from oem import CURRENT_VERSION
from oem.base import Constraint, ConstraintSpecification, HeaderField, KeyValueSection
from oem.tools import (
    format_epoch,
    parse_epoch,
    parse_integer,
    parse_str,
    require,
    require_field,
)


class ConstrainMetaDataTime(Constraint):
    """Apply constraints to metadata START_TIME and STOP_TIME"""

    versions = ["*"]

    def func(self, metadata):
        require_field("START_TIME", metadata)
        require_field("STOP_TIME", metadata)
        require(
            metadata["START_TIME"] <= metadata["STOP_TIME"],
            "START_TIME is before STOP_TIME",
        )


class ConstrainMetadataUseableTime(Constraint):
    """Apply constraints to USEABLE_START_TIME & USEABLE_STOP_TIME"""

    versions = ["*"]

    def func(self, metadata):
        if "USEABLE_START_TIME" in metadata or "USEABLE_STOP_TIME" in metadata:
            require(
                "USEABLE_START_TIME" in metadata,
                "USEABLE_STOP_TIME provided without USEABLE_START_TIME",
            )
            require(
                "USEABLE_STOP_TIME" in metadata,
                "USEABLE_START_TIME provided without USEABLE_STOP_TIME",
            )
            require(
                metadata["USEABLE_START_TIME"] <= metadata["USEABLE_STOP_TIME"],
                "USEABLE_START_TIME after USEABLE_STOP_TIME",
            )
            require(
                metadata["USEABLE_START_TIME"] >= metadata["START_TIME"],
                "USEABLE_START_TIME before START_TIME",
            )
            require(
                metadata["USEABLE_STOP_TIME"] <= metadata["STOP_TIME"],
                "USEABLE_STOP_TIME after STOP_TIME",
            )


class ConstrainMetaDataInterpolation(Constraint):
    """Apply constraints to metadata INTERPOLATION and INTERPOLATION_DEGREE"""

    versions = ["*"]

    def func(self, metadata):
        if "INTERPOLATION" in metadata:
            require_field("INTERPOLATION_DEGREE", metadata)
            require(
                float(metadata["INTERPOLATION_DEGREE"]).is_integer(),
                "Interpolation degree is not an integer",
            )


class ConstrainMetaDataRefFrameEpoch(Constraint):
    """Apply constraints to metadata REF_FRAME_EPOCH"""

    versions = ["1.0"]

    def func(self, metadata):
        require(
            "REF_FRAME_EPOCH" not in metadata,
            "Metadata keyword 'REF_FRAME_EPOCH' not supported in OEM v1.0",
        )


class ConstrainMetaDataMessageId(Constraint):
    """Apply constraints to metadata MESSAGE_ID"""

    versions = ["1.0", "2.0"]

    def func(self, metadata):
        require(
            "MESSAGE_ID" not in metadata,
            "Metadata keyword 'MESSAGE_ID' not supported in OEM v1.0 and v2.0",
        )


class MetaDataSection(KeyValueSection):
    """OEM metadata section.

    Container for a single OEM metadata section.

    Examples:
        This class behaves similar to a dict allowing membership checks,
        iteration over keys, and value set/get.

        >>> "OBJECT_NAME" in metadata:
        True

        >>> keys = [key for key in metadata]

        >>> metadata["CENTER_NAME"] = 'Mars'

        >>> metadata["CENTER_NAME"]
        'Mars'
    """

    _field_spec = {
        "OBJECT_NAME": HeaderField(parse_str, str, required=True),
        "OBJECT_ID": HeaderField(parse_str, str, required=True),
        "CENTER_NAME": HeaderField(parse_str, str, required=True),
        "REF_FRAME": HeaderField(parse_str, str, required=True),
        "TIME_SYSTEM": HeaderField(parse_str, str, required=True),
        "START_TIME": HeaderField(parse_epoch, format_epoch, required=True),
        "STOP_TIME": HeaderField(parse_epoch, format_epoch, required=True),
        "REF_FRAME_EPOCH": HeaderField(parse_epoch, format_epoch),
        "USEABLE_START_TIME": HeaderField(parse_epoch, format_epoch),
        "USEABLE_STOP_TIME": HeaderField(parse_epoch, format_epoch),
        "INTERPOLATION": HeaderField(parse_str, str),
        "INTERPOLATION_DEGREE": HeaderField(parse_integer, str),
        "MESSAGE_ID": HeaderField(parse_str, str),
    }
    _constraint_spec = ConstraintSpecification(
        ConstrainMetaDataTime,
        ConstrainMetadataUseableTime,
        ConstrainMetaDataInterpolation,
        ConstrainMetaDataRefFrameEpoch,
        ConstrainMetaDataMessageId,
    )

    def __init__(self, metadata, version=CURRENT_VERSION):
        self.version = version
        self._parse_fields(metadata)
        self._constraint_spec.apply(self)

    def __eq__(self, other):
        return (
            self.version == other.version
            and self._fields.keys() == other._fields.keys()
            and all(self[key] == other[key] for key in self)
        )

    def __repr__(self):
        start = str(self.useable_start_time)
        stop = str(self.useable_stop_time)
        return f"MetaDataSection({start}, {stop})"

    @classmethod
    def _from_raw_data(cls, segment, version):
        return cls(segment, version=version)

    def _to_string(self):
        lines = "META_START\n"
        lines += "\n".join(self._format_fields()) + "\n"
        lines += "META_STOP\n"
        return lines

    def _to_xml(self, parent):
        for key, value in self._fields.items():
            SubElement(parent, key).text = value

    def copy(self):
        """Create an independent copy of this instance."""
        return MetaDataSection(self._fields.copy(), version=self.version)

    @property
    def useable_start_time(self):
        """Return epoch of start of useable state data range"""
        return (
            self["USEABLE_START_TIME"]
            if "USEABLE_START_TIME" in self
            else self["START_TIME"]
        )

    @property
    def useable_stop_time(self):
        """Return epoch of end of useable state data range"""
        return (
            self["USEABLE_STOP_TIME"]
            if "USEABLE_STOP_TIME" in self
            else self["STOP_TIME"]
        )
