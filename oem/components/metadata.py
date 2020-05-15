import re
from oem import patterns, CURRENT_VERSION
from oem.tools import parse_epoch, parse_integer, require, require_field
from oem.base import (
    KeyValueSection, HeaderField, ConstraintSpecification, Constraint)


class ConstrainMetaDataTime(Constraint):
    '''Apply constraints to metadata START_TIME and STOP_TIME'''

    versions = ["1.0", "2.0"]

    def func(self, metadata):
        require_field("START_TIME", metadata)
        require_field("STOP_TIME", metadata)
        require(
            metadata["START_TIME"] <= metadata["STOP_TIME"],
            "START_TIME is before STOP_TIME"
        )


class ConstrainMetadataUseableTime(Constraint):
    '''Apply constraints to USEABLE_START_TIME & USEABLE_STOP_TIME'''

    versions = ["1.0", "2.0"]

    def func(self, metadata):
        if "USEABLE_START_TIME" in metadata or "USEABLE_STOP_TIME" in metadata:
            require(
                "USEABLE_START_TIME" in metadata,
                "USEABLE_STOP_TIME provided without USEABLE_START_TIME"
            )
            require(
                "USEABLE_STOP_TIME" in metadata,
                "USEABLE_START_TIME provided without USEABLE_STOP_TIME"
            )
            require(
                metadata["USEABLE_START_TIME"]
                <= metadata["USEABLE_STOP_TIME"],
                "USEABLE_START_TIME after USEABLE_STOP_TIME"
            )
            require(
                metadata["USEABLE_START_TIME"] >= metadata["START_TIME"],
                "USEABLE_START_TIME before START_TIME"
            )
            require(
                metadata["USEABLE_STOP_TIME"] <= metadata["STOP_TIME"],
                "USEABLE_STOP_TIME after STOP_TIME"
            )


class ConstrainMetaDataInterpolation(Constraint):
    '''Apply constraints to metadata INTERPOLATION and INTERPOLATION_DEGREE'''

    versions = ["1.0", "2.0"]

    def func(self, metadata):
        if "INTERPOLATION" in metadata:
            require_field("INTERPOLATION_DEGREE", metadata)


class ConstrainMetaDataRefFrameEpoch(Constraint):
    '''Apply constraints to metadata REF_FRAME_EPOCH'''

    versions = ["1.0"]

    def func(self, metadata):
        require(
            "REF_FRAME_EPOCH" not in metadata,
            "Metadata keyword 'REF_FRAME_EPOCH' not supported in OEM v1.0"
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
        "OBJECT_NAME": HeaderField(str, required=True),
        "OBJECT_ID": HeaderField(str, required=True),
        "CENTER_NAME": HeaderField(str, required=True),
        "REF_FRAME": HeaderField(str, required=True),
        "TIME_SYSTEM": HeaderField(str, required=True),
        "START_TIME": HeaderField(parse_epoch, required=True),
        "STOP_TIME": HeaderField(parse_epoch, required=True),
        "REF_FRAME_EPOCH": HeaderField(parse_epoch),
        "USEABLE_START_TIME": HeaderField(parse_epoch),
        "USEABLE_STOP_TIME": HeaderField(parse_epoch),
        "INTERPOLATION": HeaderField(str),
        "INTERPOLATION_DEGREE": HeaderField(parse_integer)
    }
    _constraint_spec = ConstraintSpecification(
        ConstrainMetaDataTime,
        ConstrainMetadataUseableTime,
        ConstrainMetaDataInterpolation,
        ConstrainMetaDataRefFrameEpoch
    )

    def __init__(self, metadata, version=CURRENT_VERSION):
        self.version = version
        self._parse_fields(metadata)
        self._constraint_spec.apply(self)

    @classmethod
    def from_string(cls, segment, version):
        """Create MetaDataSection from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM metadata section.

        Returns:
            new_section (MetaDataSection): New MetaDataSection instance.
        """
        raw_entries = re.findall(patterns.KEY_VAL, segment)
        metadata = {
            entry[0].strip(): entry[1].strip()
            for entry in raw_entries
        }
        return cls(metadata, version=version)

    @property
    def useable_start_time(self):
        """Return epoch of start of useable state data range"""
        return (
            self._fields["USEABLE_START_TIME"]
            if "USEABLE_START_TIME" in self._fields
            else self._fields["START_TIME"]
        )

    @property
    def useable_stop_time(self):
        """Return epoch of end of useable state data range"""
        return (
            self._fields["USEABLE_STOP_TIME"]
            if "USEABLE_STOP_TIME" in self._fields
            else self._fields["STOP_TIME"]
        )
