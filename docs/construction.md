# Constructing Ephemerides

[Back to documentation index](index.md) | [Working with Data](data.md) | [Interacting with Files](file-io.md)

Use `OrbitEphemerisMessage.from_states` to construct a single-segment OEM from
an ordered iterable of `State` objects. The constructor infers the segment's
center, reference frame, time system, and data bounds. When covariance data
extends beyond the state data, the usable bounds are set to the state span.
State and covariance epochs must be Astropy `Time` objects.

```python
from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.components import State

states = [
    State(
        Time("2026-01-01T00:00:00", scale="utc"),
        frame="EME2000",
        center="Earth",
        position=[7000.0, 0.0, 0.0],
        velocity=[0.0, 7.5, 0.0],
    ),
    State(
        Time("2026-01-01T00:01:00", scale="utc"),
        frame="EME2000",
        center="Earth",
        position=[6985.0, 450.0, 0.0],
        velocity=[-0.48, 7.48, 0.0],
    ),
]

ephemeris = OrbitEphemerisMessage.from_states(
    states,
    object_name="EXAMPLE SAT",
    object_id="2026-001A",
    originator="EXAMPLE",
    interpolation="LAGRANGE",
    interpolation_degree=1,
)

ephemeris.save_as("example.oem")
```

Header and metadata keywords are case-insensitive. They may use the CCSDS name
or a lowercase, snake-case equivalent. For example, `object_name` and
`OBJECT_NAME` both set the `OBJECT_NAME` metadata field. Keyword names must map
directly to CCSDS fields, so the standard `useable_start_time` and
`useable_stop_time` spellings are required.

Covariances can be supplied with the states:

```python
import numpy as np

from oem.components import Covariance

covariances = [
    Covariance(states[0].epoch, "EME2000", np.eye(6)),
]

ephemeris = OrbitEphemerisMessage.from_states(
    states,
    covariances=covariances,
    object_name="EXAMPLE SAT",
    object_id="2026-001A",
    originator="EXAMPLE",
)
```

## Multiple Segments

Use `OrbitEphemerisMessage.from_segments` to combine existing
`EphemerisSegment` objects. All segments must describe the same object and use
the same OEM version and time system. The constructor infers the version and
uses the current time as the creation date.

```python
ephemeris = OrbitEphemerisMessage.from_segments(
    [coast_segment, post_maneuver_segment],
    originator="EXAMPLE",
)
```

An explicit creation date or version can be provided when needed:

```python
ephemeris = OrbitEphemerisMessage.from_segments(
    segments,
    originator="EXAMPLE",
    creation_date=Time("2026-01-01T12:00:00", scale="utc"),
    ccsds_oem_vers="2.0",
)
```

Unknown fields and values that violate the existing OEM component constraints
raise an exception.
