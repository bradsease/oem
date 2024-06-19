import warnings

import numpy as np

from oem.tools import epoch_span_contains, epoch_span_overlap, time_range

REFERENCE_FRAMES = {
    "inertial": ["EME2000", "GCRF", "ICRF", "MCI", "TEME", "TOD"],
    "rotating": ["GRC", "ITRF2000", "ITRF-93", "ITRF-97", "TDR"],
}


class EphemerisCompare(object):
    """Comparison of two OrbitEphemerisMessage.

    Only overlapping segments with identical reference frame and central bodies
    will be compared. All comparisons are calculated in the segment reference
    frame. Rotating reference frames are not supported for velocity-based or
    RIC comparisons.

    Attributes:
        is_empty (bool): Flag indicating overlap between compared ephemerides.
            Set to True if there is no overlap.
        segments (list): List of SegmentCompare for matching EphemerisSegment
            with overlapping spans.

    Examples:
        A comparison of two ephemerides is simply achieved through either a
        direct call to EphemerisCompare or the subtraction interface on
        the OrbitEphemerisMessage class. In general, the subtraction interface
        is preferred.

        >>> ephemeris1 = OrbitEphemerisMessage.open(file_path1)
        >>> ephemeris2 = OrbitEphemerisMessage.open(file_path2)
        >>> compare = ephemeris2 - ephemeris1

        The EphemerisCompare object supports most of the same basic interfaces
        as OrbitEphemerisMessage. To evaluate the at a particular epoch:

        >>> compare(epoch)

        To iterate through the compare at a fixed interval, use the `.steps`
        method:

        >>> for state_compare in compare.steps(60):
        ...     # Operate on StateCompare
        ...     pass

        For multi-segment ephemerides, EphemerisCompare is iterable:

        >>> for segment_compare in compare:
        ...     for state_compare in segment_compare:
        ...     pass
    """

    def __init__(self, origin, target):
        """Create an EphemerisCompare.

        Args:
            origin (OrbitEphemerisMessage): Ephemeris at the origin of the
                compare frame.
            target (OrbitEphemerisMessage): Ephemeris compared against origin.
        """
        segments = []
        for origin_segment in origin:
            for target_segment in target:
                segments.append(target_segment - origin_segment)
        self._segments = [entry for entry in segments if not entry.is_empty]

    def __call__(self, epoch):
        for segment in self:
            if epoch in segment:
                return segment(epoch)
        else:
            raise ValueError(f"Epoch {epoch} not contained in EphemerisCompare.")

    def __iter__(self):
        return iter(self._segments)

    def __contains__(self, epoch):
        return any(epoch in segment for segment in self._segments)

    def __repr__(self):
        return f"EphemerisCompare(segments: {len(self.segments)})"

    def steps(self, step_size):
        """Sample EphemerisCompare at equal time intervals.

        This method returns a generator producing state compares at equal time
        intervals spanning the useable duration of the parent EphemerisCompare.

        Args:
            step_size (float): Sample step size in seconds.

        Yields:
            state_compare: Sampled StateCompare.
        """
        for segment in self:
            for state in segment.steps(step_size):
                yield state

    @property
    def is_empty(self):
        return len(self._segments) == 0

    @property
    def segments(self):
        return self._segments


class SegmentCompare(object):
    """Comparison of two EphemerisSegment.

    Input segments must have identical reference frames and central bodies.
    All comparisons are calculated in the input segment reference frame.

    Rotating reference frames are not supported for velocity-based or
    RIC comparisons.

    Attributes:
        is_empty (bool): Flag indicating overlap between compared segments. Set
            to True if there is no overlap.
    """

    def __init__(self, origin, target):
        """Create a SegmentCompare.

        Args:
            origin (EphemerisSegment): Segment at the origin of the
                compare frame.
            target (EphemerisSegment): Segment to compare against the
                origin state.
        """
        if (
            origin.metadata["REF_FRAME"] == target.metadata["REF_FRAME"]
            and origin.metadata["CENTER_NAME"] == target.metadata["CENTER_NAME"]
        ):
            self._span = epoch_span_overlap(origin.span, target.span)
            self._origin = origin
            self._target = target
        else:
            raise ValueError("Incompatible states: frame or central body mismatch.")

    def __contains__(self, epoch):
        return self._span is not None and epoch_span_contains(self._span, epoch)

    def __call__(self, epoch):
        if epoch not in self:
            raise ValueError(f"Epoch {epoch} not contained in SegmentCompare.")
        return self._target(epoch) - self._origin(epoch)

    def __repr__(self):
        return f"SegmentCompare({str(self._span[0])}, {str(self._span[1])})"

    def steps(self, step_size):
        """Sample SegmentCompare at equal time intervals.

        This method returns a generator producing state compares at equal time
        intervals spanning the useable duration of the parent SegmentCompare.

        Args:
            step_size (float): Sample step size in seconds.

        Yields:
            state_compare: Sampled StateCompare.
        """
        for epoch in time_range(*self._span, step_size):
            yield self(epoch)

    @property
    def is_empty(self):
        return self._span is None

    @property
    def start_time(self):
        if self.is_empty:
            raise ValueError("This SegmentCompare contains no overlapping state")
        return self._span[0]

    @property
    def stop_time(self):
        if self.is_empty:
            raise ValueError("This SegmentCompare contains no overlapping state")
        return self._span[1]

    @property
    def span(self):
        return self._span


class StateCompare(object):
    """Comparison of two Cartesian states.

    Input states must have identical epochs, reference frames, and central
    bodies. All comparisons are calculated in the input state reference frame.

    Rotating reference frames are not supported for velocity-based or
    RIC comparisons.

    Attributes:
        epoch (Time): Epoch of the state compare.
        range (float): Absolute distance between the two states.
        range_rate (float): Absolute velocity between the two states.
        position (ndarray): Relative position vector in the input frame.
        velocity (ndarray): Relative velocity vector in the input frame.
        position_ric (ndarray): Relative position vector in the RIC frame.
        velocity_ric (ndarray): Relative velocity vector in the RIC frame.

    Examples:
        To compare two states, `origin` and `target`, either call the
        StateCompare initializer directly

        >>> compare = StateCompare(origin, target)

        or simply difference the two states

        >>> compare = origin - target
    """

    def __init__(self, origin, target):
        """Create a StateCompare.

        Args:
            origin (State): State at the origin of the compare frame.
            target (State): State to compare against the origin state.

        Raises:
            ValueError: Incompatible states: epoch, frame, or central
                body mismatch.
        """
        if (
            origin.epoch == target.epoch
            and origin.frame == target.frame
            and origin.center == target.center
        ):
            self._origin = origin
            self._target = target
            if self._origin.frame.upper() in REFERENCE_FRAMES["inertial"]:
                self._inertial = True
            elif self._origin.frame.upper() in REFERENCE_FRAMES["rotating"]:
                self._inertial = False
            else:
                warnings.warn(
                    f"Nonstandard frame: '{self._origin.frame}'. "
                    "Assuming intertial. Override with ._inertial=False",
                    UserWarning,
                )
                self._inertial = True
        else:
            raise ValueError(
                "Incompatible states: epoch, frame, or central body mismatch."
            )

    def __repr__(self):
        return f"StateCompare({str(self.epoch)})"

    def _require_inertial(self):
        if not self._inertial:
            raise NotImplementedError(
                "Velocity compares not supported for non-inertial frames. "
                "To override, set ._inertial=True."
            )

    def _to_ric(self, vector):
        self._require_inertial()
        cross_track = np.cross(self._origin.position, self._origin.velocity)
        in_track = np.cross(cross_track, self._origin.position)
        R = np.array(
            [
                self._origin.position / np.linalg.norm(self._origin.position),
                in_track / np.linalg.norm(in_track),
                cross_track / np.linalg.norm(cross_track),
            ]
        )
        return R.dot(vector)

    @property
    def epoch(self):
        return self._origin.epoch

    @property
    def range(self):
        return np.linalg.norm(self._target.position - self._origin.position)

    @property
    def range_rate(self):
        self._require_inertial()
        return np.linalg.norm(self._target.velocity - self._origin.velocity)

    @property
    def position(self):
        return self._target.position - self._origin.position

    @property
    def velocity(self):
        self._require_inertial()
        return self._target.velocity - self._origin.velocity

    @property
    def position_ric(self):
        return self._to_ric(self.position)

    @property
    def velocity_ric(self):
        w = self._to_ric(
            np.cross(self._origin.position, self._origin.velocity)
            / np.linalg.norm(self._origin.position) ** 2
        )
        return self._to_ric(self.velocity) - np.cross(w, self.position_ric)
