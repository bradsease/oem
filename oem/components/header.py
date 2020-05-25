import re

from lxml.etree import SubElement

from oem import patterns
from oem.tools import parse_utc, parse_str, format_epoch
from oem.base import KeyValueSection, HeaderField


class HeaderSection(KeyValueSection):
    """OEM header section.

    Container for a single OEM header section.

    Examples:
        This class behaves similar to a dict allowing membership checks,
        iteration over keys, and value set/get.

        >>> "CCSDS_OEM_VERS" in header:
        True

        >>> keys = [key for key in header]

        >>> metadata["ORIGINATOR"] = 'ORIG_NAME'

        >>> metadata["ORIGINATOR"]
        'ORIG_NAME'
    """

    _field_spec = {
        "CCSDS_OEM_VERS": HeaderField(parse_str, str, required=True),
        "CREATION_DATE": HeaderField(parse_utc, format_epoch, required=True),
        "ORIGINATOR": HeaderField(parse_str, str, required=True)
    }

    def __init__(self, fields):
        self._parse_fields(fields)

    def __eq__(self, other):
        return (
            self._fields.keys() == other._fields.keys() and
            all(self[key] == other[key] for key in self)
        )

    @classmethod
    def _from_string(cls, segment):
        """Create Header Section from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM header section.

        Returns:
            new_section (HeaderSection): New HeaderSection instance.
        """
        raw_entries = re.findall(patterns.KEY_VAL, segment)
        fields = {entry[0].strip(): entry[1].strip() for entry in raw_entries}
        return cls(fields)

    @classmethod
    def _from_xml(cls, segment):
        header_segment = list(segment)[0]
        fields = {
            entry.tag: entry.text
            for entry in header_segment
            if entry.tag != "COMMENT"
        }
        fields["CCSDS_OEM_VERS"] = segment.attrib["version"]
        return cls(fields)

    def _to_string(self):
        lines = f"CCSDS_OEM_VERS = {self.version}\n"
        lines += "\n".join([
            entry
            for entry in self._format_fields()
            if "CCSDS_OEM_VERS" not in entry
        ])
        return lines + "\n"

    def _to_xml(self, parent):
        for key, value in self._fields.items():
            if key != "CCSDS_OEM_VERS":
                SubElement(parent, key).text = value

    @property
    def version(self):
        return self["CCSDS_OEM_VERS"]
