import re

from lxml.etree import ElementTree, Element, SubElement, parse

from oem import components, patterns
from oem.base import Constraint, ConstraintSpecification
from oem.tools import require, is_kvn


class ConstrainOemTimeSystem(Constraint):
    """Apply constraints to OEM TIME_SYSTEM."""

    versions = ["1.0", "2.0"]

    def func(self, oem):
        time_system = None
        for segment in oem:
            if time_system is None:
                time_system = segment.metadata["TIME_SYSTEM"]
            else:
                require(
                    segment.metadata["TIME_SYSTEM"] == time_system,
                    "TIME_SYSTEM not fixed in OEM"
                )


class ConstrainOemStates(Constraint):
    '''Apply constraints to OEM data sections'''

    versions = ["1.0", "2.0"]

    def func(self, oem):
        if oem.version == "1.0":
            self.v1_0(oem)
        else:
            self.v2_0(oem)

    def v1_0(self, oem):
        require(
            all(
                (oem._segments[idx].metadata["STOP_TIME"]
                 <= oem._segments[idx+1].metadata["START_TIME"])
                for idx in range(len(oem._segments)-1)
            ),
            "Data section state epochs overlap"
        )

    def v2_0(self, oem):
        require(
            all(
                (oem._segments[idx].useable_stop_time
                 <= oem._segments[idx+1].useable_start_time)
                for idx in range(len(oem._segments)-1)
            ),
            "Data section state epochs overlap"
        )


class OrbitEphemerisMessage(object):
    """Python representation of an Orbit Ephemeris Message.

    This class provides the primary interface between the OEM module and an
    OEM file.

    Attributes:
        header (HeaderSection): Object containing the OEM header section.

    Examples:
        The `OrbitEphemerisMessage` class can load directly from a file:

        >>> ephemeris = OrbitEphemerisMessage.open(file_path)

        An OEM is made up of one or more data segments available through an
        iterator:

        >>> for segment in ephemeris:
        ...     for state in segment:
        ...         # Iterate through states
        ...         pass
        ...     for covariance in segment.covariances:
        ...         # Iterate through covariances
        ...         pass

        It is also possible to iterate through the states and covariances in
        all segments with the `.states` and `.covariances` properties.

        To determine if a particular epoch is contained in the useable time
        range of any of the segments in an ephemeris, use `in`:

        >>> epoch in ephemeris
        True

        The `save_as` method enables saving of copies of an OEM in both KVN and
        XML formats.

        >>> oem.save_as("new.oem", file_format="xml")

        To convert directly between KVN and XML formats, use the `convert`
        class method. For example, to convert a KVN OEM to XML:

        >>> oem.convert("input.oem", "output.oem", "xml")
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainOemTimeSystem,
        ConstrainOemStates
    )

    def __init__(self, header, segments):
        '''Create an Orbit Ephemeris Message.

        Args:
            header (HeaderSection): Object containing the OEM header section.
            segments (list): List of OEM EphemerisSegments.
        '''
        self.header = header
        self.version = self.header["CCSDS_OEM_VERS"]
        self._segments = segments
        self._constraint_spec.apply(self)

    def __iter__(self):
        return iter(self._segments)

    def __contains__(self, epoch):
        return any(epoch in segment for segment in self._segments)

    def __eq__(self, other):
        return (
            self.version == other.version and
            self.header == other.header and
            len(self._segments) == len(other._segments) and
            all(
                this_segment == other_segment
                for this_segment, other_segment
                in zip(self._segments, other._segments)
            )
        )

    @classmethod
    def from_kvn_oem(cls, file_path):
        with open(file_path, "r") as ephem_file:
            contents = ephem_file.read()
        contents = re.sub(patterns.COMMENT_LINE, "", contents)
        match = re.match(patterns.CCSDS_EPHEMERIS, contents, re.MULTILINE)
        if match:
            header = components.HeaderSection._from_string(match.group(1))
            version = header["CCSDS_OEM_VERS"]
            segments = [
                components.EphemerisSegment._from_strings(raw_segment, version)
                for raw_segment
                in re.findall(patterns.DATA_BLOCK, contents, re.MULTILINE)
            ]
        else:
            raise ValueError("Failed to parse ephemeris file.")
        return cls(header, segments)

    @classmethod
    def from_xml_oem(cls, file_path):
        parts = parse(str(file_path)).getroot()
        header = components.HeaderSection._from_xml(parts)
        segments = [
            components.EphemerisSegment._from_xml(part, header.version)
            for part in parts[1]
        ]
        return cls(header, segments)

    @classmethod
    def open(cls, file_path):
        """Open an Orbit Ephemeris Message file.

        This method supports both KVN and XML formats.

        Args:
            file_path (str or Path): Path of file to read.

        Returns:
            oem: OrbitEphemerisMessage instance.
        """
        if is_kvn(file_path):
            oem = cls.from_kvn_oem(file_path)
        else:
            oem = cls.from_xml_oem(file_path)
        return oem

    @classmethod
    def convert(cls, in_file_path, out_file_path, file_format):
        """Convert an OEM to a particular file format.

        This method will succeed and produce an output file even if the input
        file is already in the desired format. Comments are not preserved.

        Args:
            in_file_path (str or Path): Path to original ephemeris.
            out_file_path (str or Path): Desired path for converted ephemeris.
            file_format (str): Desired output format. Options are
                'kvn' and 'xml'.
        """
        cls.open(in_file_path).save_as(out_file_path, file_format=file_format)

    def save_as(self, file_path, file_format="kvn"):
        """Write OEM to file.

        Args:
            file_path (str or Path): Desired path for output ephemeris.
            file_format (str, optional): Type of file to output. Options are
                'kvn' and 'xml'. Default is 'kvn'.
        """
        if file_format == "kvn":
            with open(file_path, "w") as output_file:
                output_file.write(self._to_kvn_oem())
        elif file_format == "xml":
            self._to_xml_oem().write(
                str(file_path),
                pretty_print=True,
                encoding="utf-8",
                xml_declaration=True
            )
        else:
            raise ValueError(f"Unrecognized file type: '{file_format}'")

    def _to_kvn_oem(self):
        lines = self.header._to_string() + "\n"
        lines += "".join(entry._to_string() for entry in self._segments)
        return lines

    def _to_xml_oem(self):
        oem = Element("oem", id="CCSDS_OEM_VERS", version=self.version)
        self.header._to_xml(SubElement(oem, "header"))
        body = SubElement(oem, "body")
        for entry in self._segments:
            entry._to_xml(SubElement(body, "segment"))
        return ElementTree(oem)

    @property
    def states(self):
        '''Return a list of states in all segments.'''
        return [
            state
            for segment in self
            for state in segment.states
        ]

    @property
    def covariances(self):
        '''Return a list of covariances in all segments.'''
        return [
            covariance
            for segment in self
            for covariance in segment.covariances
        ]
