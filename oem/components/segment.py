from lxml.etree import SubElement

from oem import CURRENT_VERSION
from oem.base import ConstraintSpecification, Constraint
from oem.tools import require, time_range
from oem.components.metadata import MetaDataSection
from oem.components.data import DataSection
from oem.components.covariance import CovarianceSection
from oem.interp import EphemerisInterpolator


class ConstrainEphemerisSegmentCovariance(Constraint):
    '''Apply constraints to ephemeris segment covariance sections'''

    versions = ["1.0"]

    def func(self, ephemeris_segment):
        require(
            ephemeris_segment._covariance_data is None,
            "Covariance data block not supported in OEM v1.0"
        )


class ConstrainEphemerisSegmentCovarianceEpochs(Constraint):
    '''Apply constraints to ephemeris segment covariance sections'''

    versions = ["1.0", "2.0"]

    def func(self, ephemeris_segment):
        for covariance in ephemeris_segment.covariances:
            require(
                (
                    covariance.epoch >=
                    ephemeris_segment.metadata["START_TIME"]
                    and
                    covariance.epoch <=
                    ephemeris_segment.metadata["STOP_TIME"]
                ),
                f"Covariance epoch not within range: {covariance.epoch}"
            )


class ConstrainEphemerisSegmentStateEpochs(Constraint):
    '''Apply constraints to ephemeris segment state sections'''

    versions = ["1.0", "2.0"]

    def func(self, ephemeris_segment):
        for state in ephemeris_segment.states:
            require(
                (
                    state.epoch >=
                    ephemeris_segment.metadata["START_TIME"]
                    and
                    state.epoch <=
                    ephemeris_segment.metadata["STOP_TIME"]
                ),
                f"State epoch not within usable range: {state.epoch}"
            )


class EphemerisSegment(object):
    """OEM ephemeris segment.

    Container for a single OEM ephemeris segment.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainEphemerisSegmentStateEpochs,
        ConstrainEphemerisSegmentCovariance,
        ConstrainEphemerisSegmentCovarianceEpochs
    )

    def __init__(self, metadata, state_data, covariance_data=None,
                 version=CURRENT_VERSION):
        self.version = version
        self.metadata = metadata
        self._state_data = state_data
        self._covariance_data = covariance_data
        self._constraint_spec.apply(self)
        self._interpolator = None

    def __call__(self, epoch):
        if not self._interpolator:
            self._init_interpolator()
        return self._interpolator(epoch)

    def __contains__(self, epoch):
        return (
            epoch >= self.useable_start_time and
            epoch <= self.useable_stop_time
        )

    def __iter__(self):
        return iter(self.states)

    def __eq__(self, other):
        return (
            self.version == other.version and
            self.metadata == other.metadata and
            self._state_data == other._state_data and
            self._covariance_data == other._covariance_data
        )

    def __repr__(self):
        start = str(self.useable_start_time)
        stop = str(self.useable_stop_time)
        return f"EphemerisSegment({start}, {stop})"

    @classmethod
    def _from_strings(cls, components, version):
        metadata = MetaDataSection._from_string(components[0], version)
        state_data = DataSection._from_string(components[1], version, metadata)
        if components[2] is None:
            covariance_data = None
        else:
            covariance_data = CovarianceSection._from_string(
                components[2], version, metadata)
        return cls(metadata, state_data, covariance_data, version=version)

    @classmethod
    def _from_xml(cls, segment, version):
        metadata = MetaDataSection._from_xml(segment[0], version)
        state_data = DataSection._from_xml(
            [
                entry for entry in segment[1]
                if entry.tag.rpartition('}')[-1] == "stateVector"
            ],
            version,
            metadata
        )

        raw_covariances = [
            entry for entry in segment[1]
            if entry.tag.rpartition('}')[-1] == "covarianceMatrix"
        ]
        if raw_covariances:
            covariance_data = CovarianceSection._from_xml(
                raw_covariances,
                version,
                metadata
            )
        else:
            covariance_data = None

        return cls(metadata, state_data, covariance_data, version=version)

    def _to_string(self):
        lines = self.metadata._to_string() + "\n"
        lines += self._state_data._to_string() + "\n"
        if self._covariance_data:
            lines += self._covariance_data._to_string() + "\n"
        return lines

    def _to_xml(self, parent):
        self.metadata._to_xml(SubElement(parent, "metadata"))
        data = SubElement(parent, "data")
        self._state_data._to_xml(data)
        if self._covariance_data:
            self._covariance_data._to_xml(data)

    def _init_interpolator(self):
        if "INTERPOLATION" in self.metadata:
            method = self.metadata["INTERPOLATION"]
            order = self.metadata["INTERPOLATION_DEGREE"]
        else:
            method = "LAGRANGE"
            order = 5
        self._interpolator = EphemerisInterpolator(
            self.states,
            method,
            order
        )

    def copy(self):
        """Create an independent copy of this instance."""
        return EphemerisSegment(
            self.metadata.copy(),
            self._state_data.copy(),
            self._covariance_data.copy() if self.has_covariance else None,
            version=self.version
        )

    def steps(self, step_size):
        """Sample Segment at equal time intervals.

        This method returns a generator producing states at equal time
        intervals spanning the useable duration of the parent EphemerisSegment.

        Args:
            step_size (float): Sample step size in seconds.

        Yields:
            State: Sampled state.

        Examples:
            Sample states in each segment of an OEM at 60-second intervals:

            >>> for segment in oem:
            ...    for state in segment.steps(60):
            ...        pass
        """
        for epoch in time_range(self.useable_start_time,
                                self.useable_stop_time,
                                step_size):
            yield self(epoch)

    def resample(self, step_size, in_place=False):
        """Resample ephemeris data.

        Replaces the existing ephemeris state data in this EphemerisSegment
        with a new list of states sampled at the desired sampling interval.

        Args:
            step_size (float): Sample step size in seconds.
            in_place (bool, optional): Toggle in-place resampling. Default
                is False.

        Returns:
            EphemerisSegment: Resampled EphemerisSegment. Output is
                an indepdent instance if in_place is True.
        """
        if in_place:
            self._state_data = DataSection(
                [state for state in self.steps(step_size)],
                version=self._state_data.version
            )
        else:
            segment = self.copy().resample(step_size, in_place=True)
        return segment if not in_place else self

    @property
    def states(self):
        """Return list of States in this segment."""
        return self._state_data.states

    @property
    def covariances(self):
        """Return list of Covariances in this segment."""
        if self._covariance_data:
            return self._covariance_data.covariances
        else:
            return []

    @property
    def has_accel(self):
        """Evaluate if segment contains acceleration data."""
        return self._state_data.has_accel

    @property
    def has_covariance(self):
        """Evaluate if segment contains covariance data."""
        return True if self._covariance_data else False

    @property
    def useable_start_time(self):
        """Return epoch of start of useable state data range"""
        return self.metadata.useable_start_time

    @property
    def useable_stop_time(self):
        """Return epoch of end of useable state data range"""
        return self.metadata.useable_stop_time
