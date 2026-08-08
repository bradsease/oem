"""OMM message representation and serialization."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, Sequence, Union

from astropy.time import Time
from lxml.etree import Element, ElementTree, SubElement

from oem.components.types import State
from oem.tools import _open, format_epoch, is_kvn

from .fields import (
    COVARIANCE_FIELDS,
    HEADER_FIELDS,
    MEAN_ELEMENT_FIELDS,
    METADATA_FIELDS,
    NUMERIC_DATA_FIELDS,
    SPACECRAFT_PARAMETER_FIELDS,
    TLE_PARAMETER_FIELDS,
)
from .parsers import _parse_kvn, _parse_xml
from .sections import OmmData, OmmHeader, OmmKeyValueSection, OmmMetadata

if TYPE_CHECKING:
    from oem.interface import OrbitEphemerisMessage
    from sgp4.api import Satrec


class OrbitMeanElementsMessage(object):
    """Python representation of a CCSDS OMM version 2.0 or 3.0.

    An OMM comprises one header, one metadata block, and one data block. The
    data block contains the five logical OMM data groups defined by CCSDS.
    """

    def __init__(
        self,
        header: Mapping[str, object],
        metadata: Mapping[str, object],
        data: Mapping[str, object],
    ) -> None:
        self.header = OmmHeader(header)
        self.metadata = OmmMetadata(metadata, version=self.header.version)
        self.data = OmmData(data, self.metadata, version=self.header.version)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, OrbitMeanElementsMessage)
            and self.header == other.header
            and self.metadata == other.metadata
            and self.data == other.data
        )

    def __repr__(self) -> str:
        return f"OrbitMeanElementsMessage(v{self.version})"

    def __call__(self, epoch: Time) -> State:
        return self.at(epoch)

    @classmethod
    def open(cls, file_path: Union[str, Path]) -> "OrbitMeanElementsMessage":
        """Open a KVN or XML OMM file."""
        with _open(file_path, "rt") as omm_file:
            parts = _parse_kvn(omm_file) if is_kvn(file_path) else _parse_xml(omm_file)
        return cls(*parts)

    @classmethod
    def convert(
        cls,
        in_file_path: Union[str, Path],
        out_file_path: Union[str, Path],
        file_format: str,
        **save_args: Any,
    ) -> None:
        """Convert an OMM between KVN and XML formats."""
        cls.open(in_file_path).save_as(out_file_path, file_format, **save_args)

    def at(self, epoch: Time, frame: str = "ICRF") -> State:
        """Propagate an SGP4 OMM at a scalar Astropy :class:`~astropy.time.Time`.

        For better performance, convert to an OEM with :meth:`to_oem` before
        repeatedly sampling the same OMM.

        Args:
            epoch (Time): Propagation epoch.
            frame (str, optional): Desired output frame. Currently supported
                options are "TEME" and "ICRF". Default is "ICRF".
        """
        if not isinstance(epoch, Time) or not epoch.isscalar:
            raise TypeError("epoch must be a scalar astropy.time.Time")
        satellite = self._satrec()
        from oem.tle import _sample_tle_at_epoch_array

        position, velocity = _sample_tle_at_epoch_array(satellite, [epoch], frame)
        return State(
            epoch,
            frame,
            self.metadata["CENTER_NAME"],
            position[0],
            velocity[0],
            version=self.version,
        )

    def to_oem(
        self, start_epoch: Time, stop_epoch: Time, step: float, frame: str = "ICRF"
    ) -> "OrbitEphemerisMessage":
        """Create an OEM by propagating this OMM with SGP4.

        Args:
            start_epoch (Time): Output OEM start time.
            stop_epoch (Time): Output OEM stop time.
            step (float): Output OEM step time in seconds.
            frame (str, optional): Desired output frame. Currently supported
                options are "ICRF" and "TEME". Default is "ICRF".

        Returns:
            OrbitEphemerisMessage: Converted OEM instance.
        """
        from oem.tle import satrec_to_oem

        return satrec_to_oem(
            self._satrec(),
            start_epoch,
            stop_epoch,
            step,
            frame,
            self.metadata["OBJECT_NAME"],
            self.metadata["OBJECT_ID"],
        )

    def _satrec(self) -> "Satrec":
        if self.metadata["MEAN_ELEMENT_THEORY"].upper() not in ("SGP4", "SGP/SGP4"):
            raise ValueError("SGP4 propagation requires an SGP4 mean element theory")
        try:
            from sgp4.api import Satrec
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
        return satellite

    def save_as(
        self,
        file_path: Union[str, Path],
        file_format: str = "kvn",
        compression: Optional[str] = None,
    ) -> None:
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

    def copy(self) -> "OrbitMeanElementsMessage":
        """Create an independent copy of this OMM."""
        return OrbitMeanElementsMessage(
            self.header._fields.copy(),
            self.metadata._fields.copy(),
            self.data._fields.copy(),
        )

    def _to_kvn(self) -> str:
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
    def _format_fields(section: OmmKeyValueSection, order: Sequence[str]) -> List[str]:
        return [f"{key} = {section._fields[key]}" for key in order if key in section]

    def _to_xml(self) -> ElementTree:
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
    def _xml_section(
        parent: Any,
        name: str,
        section: OmmKeyValueSection,
        fields: Sequence[str],
        omit: Sequence[str] = (),
    ) -> Any:
        element = SubElement(parent, name)
        for key in fields:
            if key in section and key not in omit:
                SubElement(element, key).text = section._fields[key]
        return element

    @property
    def epoch(self) -> Time:
        """The mean-element epoch as an Astropy ``Time``."""
        return self.data["EPOCH"]

    @property
    def version(self) -> str:
        """The CCSDS OMM version."""
        return self.header.version
