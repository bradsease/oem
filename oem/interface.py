import re

from lxml.etree import ElementTree, Element, SubElement
from defusedxml.ElementTree import parse

from oem import components, patterns
from oem.base import Constraint, ConstraintSpecification
from oem.tools import require, is_kvn, regex_block_iter


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


class ConstrainOemObject(Constraint):
    """Apply constraint to OEM OBJECT_NAME and OBJECT_ID."""

    versions = ["1.0", "2.0"]

    def func(self, oem):
        object_name = oem._segments[0].metadata["OBJECT_NAME"]
        object_id = oem._segments[0].metadata["OBJECT_ID"]
        for segment in oem:
            require(
                segment.metadata["OBJECT_NAME"] == object_name,
                "OBJECT_NAME not fixed in OEM"
            )
            require(
                segment.metadata["OBJECT_ID"] == object_id,
                "OBJECT_ID not fixed in OEM"
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

        To sample a state at an arbitrary epoch, simply call the ephemeris with
        an astropy Time object

        >>> epoch = Time("2020-01-01T00:00:00", scale="utc")
        >>> ephemeris(epoch)
        State(2020-01-01T00:00:00.000)

        Note that this type of sampling is only supported if the time system of
        the target ephemeris is supported by astropy Time objects.

        The `save_as` method enables saving of copies of an OEM in both KVN and
        XML formats.

        >>> oem.save_as("new.oem", file_format="xml")

        To convert directly between KVN and XML formats, use the `convert`
        class method. For example, to convert a KVN OEM to XML:

        >>> oem.convert("input.oem", "output.oem", "xml")
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainOemTimeSystem,
        ConstrainOemObject,
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

    def __call__(self, epoch):
        for segment in self:
            if epoch in segment:
                return segment(epoch)
        else:
            raise ValueError(f"Epoch {epoch} not contained in this ephemeris.")

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

    def __repr__(self):
        return f"OrbitEphemerisMessage(v{self.version})"

    @classmethod
    def _from_kvn_oem(cls, file_path):
        with open(file_path, "r") as ephem_file:
            contents = ephem_file.read()
        contents = re.sub(patterns.COMMENT_LINE, "", contents)
        match = re.match(patterns.HEADER_SEGMENT, contents, re.MULTILINE)
        if match:
            header = components.HeaderSection._from_string(match.group(0))
            version = header["CCSDS_OEM_VERS"]
            start_idx = match.span()[1]
            segments = [
                components.EphemerisSegment._from_strings(raw_segment, version)
                for raw_segment
                in regex_block_iter(patterns.DATA_BLOCK, contents[start_idx:])
            ]

        else:
            raise ValueError("Failed to parse ephemeris header.")
        return cls(header, segments)

    @classmethod
    def _from_xml_oem(cls, file_path):
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
            OrbitEphemerisMessage: New OEM instance.
        """
        if is_kvn(file_path):
            oem = cls._from_kvn_oem(file_path)
        else:
            oem = cls._from_xml_oem(file_path)
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

    def copy(self):
        """Create an independent copy of this instance."""
        return OrbitEphemerisMessage(
            self.header.copy(),
            [segment.copy() for segment in self]
        )

    def steps(self, step_size):
        """Sample Ephemeris at equal time intervals.

        This method returns a generator producing states at equal time
        intervals spanning the useable duration of all segments in the
        parent OEM.

        Args:
            step_size (float): Sample step size in seconds.

        Yields:
            State: Sample state.

        Examples:
            Sample states at 60-second intervals:

            >>> for state in oem.steps(60):
            ...     pass

            Note that spacing between steps will only be constant within
            segments; when crossing from one segment to another the spacing
            will vary. To avoid this behavior with multi-segment OEMs, use the
            segment interface directly:

            >>> for segment in oem:
            ...    for state in segment.steps(60):
            ...        pass
        """
        for segment in self:
            for state in segment.steps(step_size):
                yield state

    def resample(self, step_size, in_place=False):
        """Resample ephemeris data.

        Replaces the existing ephemeris state data in this OEM with new states
        sampled at the desired sampling interval. The new sampling applies to
        all segments contained in this OEM.

        Args:
            step_size (float): Sample step size in seconds.
            in_place (bool, optional): Toggle in-place resampling. Default
                is False.

        Returns:
            OrbitEphemerisMessage: Resampled OEM. Output is an indepedent
                instance if in_place is True.

        Examples:
            Open an ephemeris file, convert it to a 60-second sampling interval
            and save the result to a new file:

            >>> oem = OrbitEphemerisMessage.open("input.oem")
            >>> oem.resample(60, in_place=True)
            >>> oem.save_as("output.oem")

            To do the same thing without in-place operations:

            >>> oem = OrbitEphemerisMessage.open("input.oem")
            >>> new_oem = oem.resample(60)
            >>> new_oem.save_as("output.oem")
        """
        if in_place:
            for segment in self:
                segment.resample(step_size, in_place=True)
        else:
            oem = self.copy().resample(step_size, in_place=True)
        return oem if not in_place else self

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
