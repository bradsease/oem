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

    def __repr__(self):
        return f"HeaderSection(v{self.version})"

    @classmethod
    def _from_string(cls, segment):
        raw_entries = re.findall(patterns.KEY_VAL, segment)
        fields = {entry[0].strip(): entry[1].strip() for entry in raw_entries}
        return cls(fields)

    @classmethod
    def _from_xml(cls, segment):
        header_segment = list(segment)[0]
        fields = {
            entry.tag.rpartition('}')[-1]: entry.text
            for entry in header_segment
            if entry.tag.rpartition('}')[-1] != "COMMENT"
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

    def copy(self):
        """Create an independent copy of this instance."""
        return HeaderSection(self._fields.copy())

    @property
    def version(self):
        return self["CCSDS_OEM_VERS"]
