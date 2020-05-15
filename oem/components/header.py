import re
from oem import patterns
from oem.tools import parse_epoch
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
        "CCSDS_OEM_VERS": HeaderField(str, required=True),
        "CREATION_DATE": HeaderField(parse_epoch, required=True),
        "ORIGINATOR": HeaderField(str, required=True)
    }

    def __init__(self, fields):
        self._parse_fields(fields)

    @classmethod
    def from_string(cls, segment):
        """Create Header Section from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM header section.

        Returns:
            new_section (HeaderSection): New HeaderSection instance.
        """
        raw_entries = re.findall(patterns.KEY_VAL, segment)
        fields = {entry[0].strip(): entry[1].strip() for entry in raw_entries}
        return cls(fields)

    @property
    def version(self):
        return self["CCSDS_OEM_VERS"]
