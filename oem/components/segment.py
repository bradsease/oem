from itertools import chain

from lxml.etree import SubElement

from oem import CURRENT_VERSION
from oem.base import Constraint, ConstraintSpecification
from oem.compare import SegmentCompare
from oem.components.metadata import MetaDataSection
from oem.components.types import Covariance, State
from oem.interp import EphemerisInterpolator
from oem.parsers import COV_XML_KEYS
from oem.tools import (
    _bulk_parse_epochs,
    epoch_span_contains,
    format_epoch,
    format_float,
    require,
    time_range,
)


class ConstrainEphemerisSegmentCovariance(Constraint):
    """Apply constraints to ephemeris segment covariance sections"""

    versions = ["1.0"]

    def func(self, ephemeris_segment):
        require(
            ephemeris_segment._covariance_data is None,
            "Covariance data block not supported in OEM v1.0",
        )


class ConstrainEphemerisSegmentStateVectors(Constraint):
    """Apply constraints to ephemeris segment state vectors"""

    versions = ["1.0"]

    def func(self, ephemeris_segment):
        require(
            not ephemeris_segment.has_accel,
            "Acceleration is not supported in v1.0 OEMs",
        )


def _process_states(metadata, raw_data_rows):
    if len(raw_data_rows) == 0:
        raise ValueError("Empty data section.")

    raw_data_columns = tuple(zip(*raw_data_rows))

    epochs = raw_data_columns[0]
    sorted = all(epochs[idx] < epochs[idx + 1] for idx in range(len(epochs) - 1))
    require(sorted, "States in data section are not ordered by epoch")

    epochs = tuple(_bulk_parse_epochs(raw_data_columns[0], metadata))
    return (epochs, *raw_data_columns[1:])


def _process_covariances(metadata, raw_data_rows):
    if len(raw_data_rows) == 0:
        raise ValueError("Empty covariance section.")
    raw_data_columns = tuple(zip(*raw_data_rows))
    epochs = tuple(_bulk_parse_epochs(raw_data_columns[0], metadata))
    frames = raw_data_columns[1]
    return (epochs, frames, *raw_data_columns[2:])


class EphemerisSegment(object):
    """OEM ephemeris segment.

    Container for a single OEM ephemeris segment.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainEphemerisSegmentCovariance,
        ConstrainEphemerisSegmentStateVectors,
    )

    def __init__(
        self, metadata, state_data, covariance_data=None, version=CURRENT_VERSION
    ):
        self.version = version
        self.metadata = metadata
        self._state_data = state_data
        self._covariance_data = covariance_data
        self._constraint_spec.apply(self)
        self._interpolator = None

    def __call__(self, epoch):
        if epoch not in self:
            raise ValueError(f"Epoch {epoch} not contained in segment.")
        if not self._interpolator:
            self._init_interpolator()
        position, velocity, acceleration = self._interpolator(epoch)
        return State(
            epoch,
            self.metadata["REF_FRAME"],
            self.metadata["CENTER_NAME"],
            position,
            velocity,
            acceleration=acceleration,
            version=self.version,
        )

    def __contains__(self, epoch):
        return epoch_span_contains(self.span, epoch)

    def __iter__(self):
        return self.states

    def __eq__(self, other):
        return (
            self.version == other.version
            and self.metadata == other.metadata
            and self._state_data == other._state_data
            and self._covariance_data == other._covariance_data
        )

    def __sub__(self, other):
        return SegmentCompare(other, self)

    def __repr__(self):
        start = str(self.useable_start_time)
        stop = str(self.useable_stop_time)
        return f"EphemerisSegment({start}, {stop})"

    @classmethod
    def _from_raw_data(cls, segment, version):
        metadata = MetaDataSection._from_raw_data(segment["header"], version)

        try:
            state_data = _process_states(metadata, segment["data"])
        except Exception:
            raise ValueError("Malformed data section.")

        if segment.get("cov"):
            try:
                cov_data = _process_covariances(metadata, segment["cov"])
            except Exception:
                raise ValueError("Malformed covariance section.")
        else:
            cov_data = None

        return cls(metadata, state_data, cov_data, version=version)

    def _to_string(self):
        lines = self.metadata._to_string() + "\n"
        for epoch, *state in zip(*self._state_data):
            lines += f"{format_epoch(epoch)} "
            lines += " ".join(format_float(entry) for entry in state) + "\n"
        lines += "\n"

        if self._covariance_data:
            lines += "COVARIANCE_START\n"
            for epoch, frame, *cov in zip(*self._covariance_data):
                lines += f"EPOCH = {format_epoch(epoch)}\n"
                if frame != self.metadata["REF_FRAME"]:
                    lines += f"COV_REF_FRAME = {frame}\n"
                lines += f"{format_float(cov[0])}\n"
                lines += " ".join(format_float(c) for c in cov[1:3]) + "\n"
                lines += " ".join(format_float(c) for c in cov[3:6]) + "\n"
                lines += " ".join(format_float(c) for c in cov[6:10]) + "\n"
                lines += " ".join(format_float(c) for c in cov[10:15]) + "\n"
                lines += " ".join(format_float(c) for c in cov[15:]) + "\n"
            lines += "COVARIANCE_STOP\n"
            lines += "\n"

        return lines

    def _to_xml(self, parent):
        self.metadata._to_xml(SubElement(parent, "metadata"))
        data = SubElement(parent, "data")
        fields = ("X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT")
        for epoch, *state in zip(*self._state_data):
            vector = SubElement(data, "stateVector")
            SubElement(vector, "EPOCH").text = format_epoch(epoch)
            for idx, field in enumerate(fields):
                SubElement(vector, field).text = format_float(state[idx])
            if len(state) == 9:
                for idx, field in enumerate(("X_DDOT", "Y_DDOT", "Z_DDOT")):
                    SubElement(vector, field).text = format_float(state[idx + 6])

        if self._covariance_data:
            for epoch, frame, *cov in zip(*self._covariance_data):
                covdata = SubElement(data, "covarianceMatrix")
                SubElement(covdata, "EPOCH").text = format_epoch(epoch)
                if frame != self.metadata["REF_FRAME"]:
                    SubElement(covdata, "COV_REF_FRAME").text = frame
                for idx, key in enumerate(COV_XML_KEYS):
                    SubElement(covdata, key).text = format_float(cov[idx])

    def _init_interpolator(self):
        if "INTERPOLATION" in self.metadata:
            method = self.metadata["INTERPOLATION"]
            order = self.metadata["INTERPOLATION_DEGREE"]
        else:
            method = "LAGRANGE"
            order = 5
        self._interpolator = EphemerisInterpolator(self._state_data, method, order)

    def copy(self):
        """Create an independent copy of this instance."""
        return EphemerisSegment(
            self.metadata.copy(),
            self._state_data,
            self._covariance_data if self.has_covariance else None,
            version=self.version,
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
        for epoch in time_range(
            self.useable_start_time, self.useable_stop_time, step_size
        ):
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
        if not self._interpolator:
            self._init_interpolator()

        epochs = time_range(self.useable_start_time, self.useable_stop_time, step_size)

        if in_place:
            states = (
                (
                    epoch,
                    *chain.from_iterable(
                        self._interpolator(epoch)[: 2 + self.has_accel]
                    ),
                )
                for epoch in epochs
            )
            self._state_data = tuple(zip(*states))
        else:
            segment = self.copy().resample(step_size, in_place=True)

        return segment if not in_place else self

    @property
    def states(self):
        """Return list of States in this segment."""
        return (
            State._from_raw_data(entry, self.version, self.metadata)
            for entry in zip(*self._state_data)
        )

    @property
    def covariances(self):
        """Return list of Covariances in this segment."""
        if self._covariance_data:
            return (
                Covariance._from_raw_data(entry, self.version)
                for entry in zip(*self._covariance_data)
            )
        else:
            return ()

    @property
    def has_accel(self):
        """Evaluate if segment contains acceleration data."""
        return len(self._state_data) == 10

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

    @property
    def span(self):
        return (self.useable_start_time, self.useable_stop_time)
