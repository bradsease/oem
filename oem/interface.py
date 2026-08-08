import datetime as dt

from astropy.time import Time
from lxml.etree import Element, ElementTree, SubElement

from oem import CURRENT_VERSION, components
from oem.base import Constraint, ConstraintSpecification
from oem.compare import EphemerisCompare
from oem.parsers import parse_kvn_oem, parse_xml_oem
from oem.tools import (
    _open,
    format_epoch,
    format_float_decimal,
    format_float_scientific,
    is_kvn,
    require,
)

NUMBER_FORMATERS = {
    "scientific": format_float_scientific,
    "fixed_cm": format_float_decimal,
}

EPOCH_FORMATERS = {
    "iso": format_epoch,
}


def _normalize_fields(fields):
    normalized = {}
    for key, value in fields.items():
        field = key.upper()
        if field in normalized:
            raise TypeError(f"OEM field provided more than once: {field!r}")
        normalized[field] = value
    return normalized


def _format_fields(fields, field_spec):
    return {
        key: value if isinstance(value, str) else field_spec[key].formatter(value)
        for key, value in fields.items()
    }


def _is_aware_datetime(value):
    return isinstance(value, dt.datetime) and value.utcoffset() is not None


def _split_fields(fields):
    header = {}
    metadata = {}
    for key, value in _normalize_fields(fields).items():
        if key in components.HeaderSection._field_spec:
            header[key] = value
        elif key in components.MetaDataSection._field_spec:
            metadata[key] = value
        else:
            raise TypeError(f"Unknown OEM field: {key!r}")
    return header, metadata


class ConstrainOemTimeSystem(Constraint):
    """Apply constraints to OEM TIME_SYSTEM."""

    versions = ["*"]

    def func(self, oem):
        time_system = None
        for segment in oem:
            if time_system is None:
                time_system = segment.metadata["TIME_SYSTEM"]
            else:
                require(
                    segment.metadata["TIME_SYSTEM"] == time_system,
                    "TIME_SYSTEM not fixed in OEM",
                )


class ConstrainOemObject(Constraint):
    """Apply constraint to OEM OBJECT_NAME and OBJECT_ID."""

    versions = ["*"]

    def func(self, oem):
        object_name = oem._segments[0].metadata["OBJECT_NAME"]
        object_id = oem._segments[0].metadata["OBJECT_ID"]
        for segment in oem:
            require(
                segment.metadata["OBJECT_NAME"] == object_name,
                "OBJECT_NAME not fixed in OEM",
            )
            require(
                segment.metadata["OBJECT_ID"] == object_id, "OBJECT_ID not fixed in OEM"
            )


class ConstrainOemStates(Constraint):
    """Apply constraints to OEM data sections"""

    versions = ["*"]

    def func(self, oem):
        if oem.version == "1.0":
            self.v1_0(oem)
        else:
            self.v2_0(oem)

    def v1_0(self, oem):
        require(
            all(
                (
                    oem._segments[idx].metadata["STOP_TIME"]
                    <= oem._segments[idx + 1].metadata["START_TIME"]
                )
                for idx in range(len(oem._segments) - 1)
            ),
            "Data section state epochs overlap",
        )

    def v2_0(self, oem):
        require(
            all(
                (
                    oem._segments[idx].useable_stop_time
                    <= oem._segments[idx + 1].useable_start_time
                )
                for idx in range(len(oem._segments) - 1)
            ),
            "Data section state epochs overlap",
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
        ConstrainOemTimeSystem, ConstrainOemObject, ConstrainOemStates
    )

    def __init__(self, header, segments):
        """Create an Orbit Ephemeris Message.

        Args:
            header (HeaderSection): Object containing the OEM header section.
            segments (list): List of OEM EphemerisSegments.
        """
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
            self.version == other.version
            and self.header == other.header
            and len(self._segments) == len(other._segments)
            and all(
                this_segment == other_segment
                for this_segment, other_segment in zip(self._segments, other._segments)
            )
        )

    def __sub__(self, other):
        return EphemerisCompare(other, self)

    def __repr__(self):
        return f"OrbitEphemerisMessage(v{self.version})"

    @classmethod
    def _from_kvn_oem(cls, file_path):
        with _open(file_path, "rt") as ephem_file:
            return cls._from_raw_data(parse_kvn_oem(ephem_file))

    @classmethod
    def _from_xml_oem(cls, file_path):
        with _open(file_path, "rt") as ephem_file:
            return cls._from_raw_data(parse_xml_oem(ephem_file))

    @classmethod
    def _from_raw_data(cls, data):
        raw_header, raw_segments = data
        header = components.HeaderSection._from_raw_data(raw_header)
        segments = [
            components.EphemerisSegment._from_raw_data(raw_segment, header.version)
            for raw_segment in raw_segments
        ]
        return cls(header, segments)

    @classmethod
    def from_states(cls, states, *, covariances=None, **fields):
        """Create a single-segment OEM from state and covariance objects.

        Header and metadata fields may be supplied as case-insensitive keyword
        arguments using either CCSDS names or their snake-case equivalents.
        The center, reference frame, time system, and data bounds are inferred
        from the data when omitted.

        Args:
            states (iterable): Ordered iterable of State objects.
            covariances (iterable, optional): Iterable of Covariance objects.
            **fields: OEM header and segment metadata fields.

        Returns:
            OrbitEphemerisMessage: New single-segment OEM instance.
        """
        states = tuple(states)
        if not states:
            raise ValueError("Cannot create an OEM without states")
        if not all(isinstance(state, components.State) for state in states):
            raise TypeError("states must contain only State objects")
        if any(_is_aware_datetime(state.epoch) for state in states):
            raise ValueError("State epochs cannot be timezone-aware datetime objects")
        if any(isinstance(state.epoch, Time) for state in states) and not all(
            isinstance(state.epoch, Time) for state in states
        ):
            raise ValueError("State epochs must all use the same type")
        if not all(
            states[index].epoch < states[index + 1].epoch
            for index in range(len(states) - 1)
        ):
            raise ValueError("States must be ordered by increasing epoch")

        first = states[0]
        if any(state.frame != first.frame for state in states):
            raise ValueError("All states in a segment must use the same frame")
        if any(state.center != first.center for state in states):
            raise ValueError("All states in a segment must use the same center")
        if any(state.has_accel != first.has_accel for state in states):
            raise ValueError("States cannot mix acceleration data within a segment")

        covariances = tuple(covariances) if covariances is not None else ()
        if not all(
            isinstance(covariance, components.Covariance) for covariance in covariances
        ):
            raise TypeError("covariances must contain only Covariance objects")
        for covariance in covariances:
            if _is_aware_datetime(covariance.epoch):
                raise ValueError(
                    "Covariance epochs cannot be timezone-aware datetime objects"
                )
            if covariance.matrix.shape != (6, 6):
                raise ValueError("Covariance matrices must have shape (6, 6)")
            if not (covariance.matrix == covariance.matrix.T).all():
                raise ValueError("Covariance matrices must be symmetric")
        if not all(
            covariances[index].epoch < covariances[index + 1].epoch
            for index in range(len(covariances) - 1)
        ):
            raise ValueError("Covariances must be ordered by increasing epoch")

        header_fields, metadata_fields = _split_fields(fields)
        provided_metadata = set(metadata_fields)
        version = str(header_fields.get("CCSDS_OEM_VERS", CURRENT_VERSION))

        astropy_epochs = all(isinstance(state.epoch, Time) for state in states)
        if "TIME_SYSTEM" not in metadata_fields:
            if not astropy_epochs:
                raise ValueError(
                    "time_system is required when state epochs are not Astropy Time objects"
                )
            scales = {state.epoch.scale.upper() for state in states}
            if len(scales) != 1:
                raise ValueError(
                    "All states in a segment must use the same time system"
                )
            metadata_fields["TIME_SYSTEM"] = scales.pop()

        if astropy_epochs and any(
            not isinstance(covariance.epoch, Time) for covariance in covariances
        ):
            raise ValueError(
                "Covariance epochs must be Astropy Time objects when state epochs are"
                " Astropy Time objects"
            )
        if not astropy_epochs and any(
            isinstance(covariance.epoch, Time) for covariance in covariances
        ):
            raise ValueError("Covariance and state epochs must use the same type")

        time_system = str(metadata_fields["TIME_SYSTEM"]).lower()
        if not astropy_epochs and time_system in Time.SCALES:
            state_epochs = tuple(
                Time(state.epoch, format="datetime", scale=time_system, precision=6)
                for state in states
            )
            covariance_epochs = tuple(
                Time(
                    covariance.epoch,
                    format="datetime",
                    scale=time_system,
                    precision=6,
                )
                for covariance in covariances
            )
        else:
            state_epochs = tuple(state.epoch for state in states)
            covariance_epochs = tuple(covariance.epoch for covariance in covariances)

        data_epochs = list(state_epochs)
        data_epochs.extend(covariance_epochs)
        start_time = min(data_epochs)
        stop_time = max(data_epochs)
        metadata_fields.setdefault("CENTER_NAME", first.center)
        metadata_fields.setdefault("REF_FRAME", first.frame)
        metadata_fields.setdefault("START_TIME", format_epoch(start_time))
        metadata_fields.setdefault("STOP_TIME", format_epoch(stop_time))
        if start_time < state_epochs[0] or stop_time > state_epochs[-1]:
            metadata_fields.setdefault(
                "USEABLE_START_TIME", format_epoch(state_epochs[0])
            )
            metadata_fields.setdefault(
                "USEABLE_STOP_TIME", format_epoch(state_epochs[-1])
            )

        if time_system in Time.SCALES:
            for key in (
                "START_TIME",
                "STOP_TIME",
                "USEABLE_START_TIME",
                "USEABLE_STOP_TIME",
                "REF_FRAME_EPOCH",
            ):
                if key in metadata_fields and isinstance(metadata_fields[key], Time):
                    metadata_fields[key] = getattr(metadata_fields[key], time_system)
                elif key in metadata_fields and _is_aware_datetime(
                    metadata_fields[key]
                ):
                    if time_system != "utc":
                        raise ValueError(
                            "Timezone-aware metadata epochs require the UTC time system"
                        )
                    metadata_fields[key] = (
                        metadata_fields[key]
                        .astimezone(dt.timezone.utc)
                        .replace(tzinfo=None)
                    )
        metadata_fields = _format_fields(
            metadata_fields, components.MetaDataSection._field_spec
        )
        metadata = components.MetaDataSection(metadata_fields, version=version)

        if (
            "CENTER_NAME" in provided_metadata
            and metadata["CENTER_NAME"] != first.center
        ):
            raise ValueError("center_name conflicts with the state center")
        if "REF_FRAME" in provided_metadata and metadata["REF_FRAME"] != first.frame:
            raise ValueError("ref_frame conflicts with the state frame")
        if astropy_epochs and any(
            state.epoch.scale.upper() != metadata["TIME_SYSTEM"].upper()
            for state in states
        ):
            raise ValueError("time_system conflicts with the state epochs")
        if astropy_epochs and any(
            covariance.epoch.scale.upper() != metadata["TIME_SYSTEM"].upper()
            for covariance in covariances
        ):
            raise ValueError("time_system conflicts with the covariance epochs")
        if "START_TIME" in provided_metadata and format_epoch(
            metadata["START_TIME"]
        ) != format_epoch(start_time):
            raise ValueError("start_time conflicts with the first data epoch")
        if "STOP_TIME" in provided_metadata and format_epoch(
            metadata["STOP_TIME"]
        ) != format_epoch(stop_time):
            raise ValueError("stop_time conflicts with the last data epoch")
        if (
            "USEABLE_START_TIME" in provided_metadata
            and metadata["USEABLE_START_TIME"] < state_epochs[0]
        ):
            raise ValueError("useable_start_time cannot precede the first state epoch")
        if (
            "USEABLE_STOP_TIME" in provided_metadata
            and metadata["USEABLE_STOP_TIME"] > state_epochs[-1]
        ):
            raise ValueError("useable_stop_time cannot follow the last state epoch")

        state_rows = (
            (epoch, *state.vector) for epoch, state in zip(state_epochs, states)
        )
        state_data = tuple(zip(*state_rows))

        covariance_rows = (
            (
                epoch,
                covariance.frame,
                *(
                    covariance.matrix[row, column]
                    for row in range(6)
                    for column in range(row + 1)
                ),
            )
            for epoch, covariance in zip(covariance_epochs, covariances)
        )
        covariance_data = tuple(zip(*covariance_rows)) if covariances else None

        segment = components.EphemerisSegment(
            metadata, state_data, covariance_data, version=version
        )
        return cls.from_segments([segment], **header_fields)

    @classmethod
    def from_segments(cls, segments, **fields):
        """Create an OEM from existing ephemeris segments.

        Header fields may be supplied as case-insensitive keyword arguments
        using either CCSDS names or their snake-case equivalents. The creation
        date defaults to the current time and the version is inferred from the
        segments.

        Args:
            segments (iterable): Iterable of EphemerisSegment objects.
            **fields: OEM header fields.

        Returns:
            OrbitEphemerisMessage: New OEM instance.
        """
        segments = list(segments)
        if not segments:
            raise ValueError("Cannot create an OEM without segments")
        if not all(
            isinstance(segment, components.EphemerisSegment) for segment in segments
        ):
            raise TypeError("segments must contain only EphemerisSegment objects")

        header_fields, metadata_fields = _split_fields(fields)
        if metadata_fields:
            field = next(iter(metadata_fields))
            raise TypeError(
                f"Segment metadata is not accepted by from_segments: {field!r}"
            )

        versions = {segment.version for segment in segments}
        if len(versions) != 1:
            raise ValueError("All segments in an OEM must use the same version")
        version = versions.pop()
        if "CCSDS_OEM_VERS" in header_fields:
            if str(header_fields["CCSDS_OEM_VERS"]) != version:
                raise ValueError("version conflicts with the segment version")
        else:
            header_fields["CCSDS_OEM_VERS"] = version

        header_fields.setdefault("CREATION_DATE", Time.now())
        if isinstance(header_fields["CREATION_DATE"], Time):
            header_fields["CREATION_DATE"] = header_fields["CREATION_DATE"].utc
        elif _is_aware_datetime(header_fields["CREATION_DATE"]):
            header_fields["CREATION_DATE"] = (
                header_fields["CREATION_DATE"]
                .astimezone(dt.timezone.utc)
                .replace(tzinfo=None)
            )
        header_fields = _format_fields(
            header_fields, components.HeaderSection._field_spec
        )
        return cls(components.HeaderSection(header_fields), segments)

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
    def convert(cls, in_file_path, out_file_path, file_format, **save_args):
        """Convert an OEM to a particular file format.

        This method will succeed and produce an output file even if the input
        file is already in the desired format. Comments are not preserved.

        Args:
            in_file_path (str or Path): Path to original ephemeris.
            out_file_path (str or Path): Desired path for converted ephemeris.
            file_format (str): Desired output format. Options are
                'kvn' and 'xml'.
            **save_args: Additional arguments to pass to the save_as method. See
                `save_as` for details.
        """
        cls.open(in_file_path).save_as(
            out_file_path, file_format=file_format, **save_args
        )

    def copy(self):
        """Create an independent copy of this instance."""
        return OrbitEphemerisMessage(
            self.header.copy(), [segment.copy() for segment in self]
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

    def save_as(
        self,
        file_path,
        file_format="kvn",
        compression=None,
        epoch_format="iso",
        number_format="scientific",
    ):
        """Write OEM to file.

        Args:
            file_path (str or Path): Desired path for output ephemeris.
            file_format (str, optional): Type of file to output. Options are
                'kvn' and 'xml'. Default is 'kvn'.
            compression (str, optional): File compression type to use. Options are
                'gzip', 'bz2', and 'lzma'. Default is None.
            epoch_format (str, optional): Format for epoch output. Options are
                'iso'. Default is 'iso'.
            number_format (str, optional): Format for number output. Options are
                'scientific' and 'fixed_cm'. Fixed (cm) representation uses centimeter
                precision.  Note that the fixed-point option will produce out-of-spec
                values (more than 16 digits) beyond 1e12 km. Default is 'scientific'.
        """
        if epoch_format not in EPOCH_FORMATERS:
            raise ValueError(
                f"Unrecognized epoch format: '{epoch_format}'. "
                f"Options are {list(EPOCH_FORMATERS.keys())}"
            )
        if number_format not in NUMBER_FORMATERS:
            raise ValueError(
                f"Unrecognized number format: '{number_format}'. "
                f"Options are {list(NUMBER_FORMATERS.keys())}"
            )
        epoch_formatter = EPOCH_FORMATERS[epoch_format]
        number_formatter = NUMBER_FORMATERS[number_format]

        with _open(file_path, "wb", compression) as output_file:
            if file_format == "kvn":
                output_file.write(
                    bytes(self._to_kvn_oem(epoch_formatter, number_formatter), "utf-8")
                )
            elif file_format == "xml":
                self._to_xml_oem(epoch_formatter, number_formatter).write(
                    output_file,
                    pretty_print=True,
                    encoding="utf-8",
                    xml_declaration=True,
                )
            else:
                raise ValueError(f"Unrecognized file type: '{file_format}'")

    def _to_kvn_oem(self, epoch_formatter, number_formatter):
        lines = self.header._to_string() + "\n"
        lines += "".join(
            entry._to_string(epoch_formatter, number_formatter)
            for entry in self._segments
        )
        return lines

    def _to_xml_oem(self, epoch_formatter, number_formatter):
        oem = Element("oem", id="CCSDS_OEM_VERS", version=self.version)
        self.header._to_xml(SubElement(oem, "header"))
        body = SubElement(oem, "body")
        for entry in self._segments:
            entry._to_xml(
                SubElement(body, "segment"), epoch_formatter, number_formatter
            )
        return ElementTree(oem)

    @property
    def states(self):
        """Return a list of states in all segments."""
        return [state for segment in self for state in segment.states]

    @property
    def covariances(self):
        """Return a list of covariances in all segments."""
        return [covariance for segment in self for covariance in segment.covariances]

    @property
    def segments(self):
        return self._segments

    @property
    def span(self):
        return (
            min(segment.useable_start_time for segment in self),
            max(segment.useable_stop_time for segment in self),
        )
