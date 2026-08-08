import numpy as np
import pytest
from astropy import units as u
from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.components import Covariance, State


def _states(start="2026-01-01T00:00:00"):
    start = Time(start, scale="utc")
    epochs = (start, start + 60 * u.s)
    return [
        State(
            epochs[0],
            "EME2000",
            "Earth",
            [7000.0, 0.0, 0.0],
            [0.0, 7.5, 0.0],
        ),
        State(
            epochs[1],
            "EME2000",
            "Earth",
            [6985.0, 450.0, 0.0],
            [-0.48, 7.48, 0.0],
        ),
    ]


def _from_states(states, **fields):
    return OrbitEphemerisMessage.from_states(
        states,
        object_name="EXAMPLE SAT",
        object_id="2026-001A",
        originator="EXAMPLE",
        **fields,
    )


def test_from_states_infers_segment_fields():
    states = _states()

    oem = _from_states(
        iter(states),
        interpolation="LAGRANGE",
        interpolation_degree=1,
        useable_start_time=states[0].epoch,
        useable_stop_time=states[-1].epoch,
    )

    assert oem.version == "2.0"
    assert oem.header["ORIGINATOR"] == "EXAMPLE"
    assert len(oem.segments) == 1
    assert oem.states == states
    metadata = oem.segments[0].metadata
    assert metadata["CENTER_NAME"] == "Earth"
    assert metadata["REF_FRAME"] == "EME2000"
    assert metadata["TIME_SYSTEM"] == "UTC"
    assert metadata["START_TIME"] == states[0].epoch
    assert metadata["STOP_TIME"] == states[-1].epoch
    assert metadata["USEABLE_START_TIME"] == states[0].epoch
    assert metadata["USEABLE_STOP_TIME"] == states[-1].epoch
    assert metadata["INTERPOLATION_DEGREE"] == 1


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_from_states_round_trip_with_covariance(tmp_path, file_format):
    states = _states()
    covariance = Covariance(states[0].epoch, "EME2000", np.eye(6))
    oem = _from_states(states, covariances=[covariance])
    output = tmp_path / "constructed.oem"

    oem.save_as(output, file_format=file_format)
    written = OrbitEphemerisMessage.open(output)

    assert written == oem
    assert written.covariances == [covariance]


def test_from_states_includes_covariances_in_data_bounds():
    states = _states()
    covariance = Covariance(states[-1].epoch + 60 * u.s, "EME2000", np.eye(6))

    oem = _from_states(states, covariances=[covariance])
    metadata = oem.segments[0].metadata

    assert metadata["START_TIME"] == states[0].epoch
    assert metadata["STOP_TIME"] == covariance.epoch
    assert metadata["USEABLE_START_TIME"] == states[0].epoch
    assert metadata["USEABLE_STOP_TIME"] == states[-1].epoch


def test_from_segments_infers_version_and_creation_date():
    first = _from_states(_states()).segments[0]
    second = _from_states(_states("2026-01-02T00:00:00")).segments[0]

    oem = OrbitEphemerisMessage.from_segments(
        (segment for segment in (first, second)), originator="EXAMPLE"
    )

    assert oem.version == "2.0"
    assert oem.header["ORIGINATOR"] == "EXAMPLE"
    assert isinstance(oem.header["CREATION_DATE"], Time)
    assert oem.segments == [first, second]


def test_from_segments_converts_creation_date_to_utc():
    segment = _from_states(_states()).segments[0]
    creation_date = Time("2026-01-01T12:00:00", scale="tai")

    oem = OrbitEphemerisMessage.from_segments(
        [segment], originator="EXAMPLE", creation_date=creation_date
    )

    assert oem.header["CREATION_DATE"] == creation_date.utc


@pytest.mark.parametrize(
    "fields",
    [
        {"unexpected": "value"},
        {"usable_stop_time": Time("2026-01-01")},
        {"version": "2.0"},
    ],
)
def test_from_states_rejects_invalid_fields(fields):
    with pytest.raises(TypeError, match="Unknown OEM field"):
        _from_states(_states(), **fields)


def test_from_states_requires_astropy_time_epochs():
    states = _states()
    for state in states:
        state.epoch = state.epoch.datetime

    with pytest.raises(TypeError, match="must be Astropy Time objects"):
        _from_states(states)


def test_from_states_rejects_mixed_state_vector_widths():
    states = _states()
    states[-1].acceleration = np.zeros(3)

    with pytest.raises(ValueError, match="mix acceleration"):
        _from_states(states)


def test_from_segments_rejects_segment_metadata():
    segment = _from_states(_states()).segments[0]

    with pytest.raises(TypeError, match="Segment metadata is not accepted"):
        OrbitEphemerisMessage.from_segments(
            [segment], originator="EXAMPLE", object_name="EXAMPLE SAT"
        )
