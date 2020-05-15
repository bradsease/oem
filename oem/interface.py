import re
from oem import components, patterns
from oem.base import Constraint, ConstraintSpecification
from oem.tools import require


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


class OrbitalEphemerisMessage(object):
    """Python representation of an Orbital Ephemeris Message.

    This class provides the primary interface between the OEM module and an
    OEM file.

    Attributes:
        header (HeaderSection): Object containing the OEM header section.

    Examples:
        The `OrbitalEphemerisMessage` class can load directly from a file:

        >>> ephemeris = OrbitalEphemerisMessage.from_ascii_oem(file_path)

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
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainOemTimeSystem,
        ConstrainOemStates
    )

    def __init__(self, header, segments):
        '''Create an Orbital Ephemeris Message.

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

    @classmethod
    def from_ascii_oem(cls, file_path):
        with open(file_path, "r") as ephem_file:
            contents = ephem_file.read()
        contents = re.sub(patterns.COMMENT_LINE, "", contents)
        match = re.match(patterns.CCSDS_EPHEMERIS, contents, re.MULTILINE)
        if match:
            header = components.HeaderSection.from_string(match.group(1))
            version = header["CCSDS_OEM_VERS"]
            segments = [
                components.EphemerisSegment.from_strings(raw_segment, version)
                for raw_segment
                in re.findall(patterns.DATA_BLOCK, contents, re.MULTILINE)
            ]
        else:
            raise ValueError("Failed to parse ephemeris file.")
        return cls(header, segments)

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
