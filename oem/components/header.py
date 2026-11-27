from typing import Any, Dict

from lxml.etree import SubElement

from oem.base import HeaderField, KeyValueSection
from oem.tools import format_epoch, parse_str, parse_utc


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
        "ORIGINATOR": HeaderField(parse_str, str, required=True),
        "CLASSIFICATION": HeaderField(parse_str, str),
        "MESSAGE_ID": HeaderField(parse_str, str),
    }

    def __init__(self, fields: Dict[str, str]) -> None:
        self._parse_fields(fields)

    def _validate_fields(self, fields: Dict[str, str]) -> None:
        super()._validate_fields(fields)
        if fields["CCSDS_OEM_VERS"] != "3.0":
            for key in ("CLASSIFICATION", "MESSAGE_ID"):
                if key in fields:
                    raise KeyError(f"Invalid header key: {key}")

    def __setitem__(self, key: str, value: str) -> None:
        if key in ("CLASSIFICATION", "MESSAGE_ID") and self.version != "3.0":
            raise ValueError(f"Invalid key: '{key}'")
        super().__setitem__(key, value)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, HeaderSection)
            and self._fields.keys() == other._fields.keys()
            and all(self[key] == other[key] for key in self)
        )

    def __repr__(self) -> str:
        return f"HeaderSection(v{self.version})"

    @classmethod
    def _from_raw_data(cls, segment: Dict[str, str]) -> "HeaderSection":
        return cls(segment)

    def _to_string(self) -> str:
        lines = f"CCSDS_OEM_VERS = {self.version}\n"
        lines += "\n".join(
            [entry for entry in self._format_fields() if "CCSDS_OEM_VERS" not in entry]
        )
        return lines + "\n"

    def _to_xml(self, parent: Any) -> None:
        for key, value in self._fields.items():
            if key != "CCSDS_OEM_VERS":
                SubElement(parent, key).text = value

    def copy(self) -> "HeaderSection":
        """Create an independent copy of this instance."""
        return HeaderSection(self._fields.copy())

    @property
    def version(self) -> str:
        return self["CCSDS_OEM_VERS"]
