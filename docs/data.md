# Working with Data

[Back to documentation index](index.md) | [Interacting with Files](file-io.md) | [Comparing Ephemerides](compare.md)

Each OEM is made up of one or more segments of state and optional covariance data. The `OrbitEphemerisMessage` class provides iterables for both.

```python
for segment in ephemeris:
    for state in segment:
        print(state.epoch, state.position, state.velocity)

        # Acceleration is not available in every OEM, but is supported
        # print(state.epoch, state.position, state.velocity, state.acceleration)

    for covariance in segment.covariances:
        print(covariance.epoch, covariance.matrix)
```

Epochs are represented as `astropy.time.Time` objects. Unsupported time systems use Astropy's `local` scale, which cannot be converted to a defined time scale. Positions, velocities, and accelerations are `numpy` arrays.

Address specific segments through the `.segments` attribute.

```python
segment = ephemeris.segments[0]
for state in segment:
    ...
```

Both the ephemeris and segment objects support interpolation of states. If a segment has fewer state vectors than its declared interpolation degree requires, sampling uses all available states at the highest supported degree. If the requested epoch is not within the usable date range specified in the OEM file headers, this action will raise an exception.

```python
from astropy.time import Time

epoch = Time("2024-03-09T00:00:00.000", format="isot", scale="utc")

# Sample OEM directly
state_at_epoch = ephemeris(epoch)

# Sample specific OEM segment
segment = ephemeris.segments[0]
state_at_epoch = segment(epoch)
```

For easy iterative sampling with fixed step sizes, use the `.steps` method. The sampled states will span from the usable start time to the usable end time of the ephemeris, stepping according to the provided `step_size` in seconds. Individual segments also support the `.steps` method.

```python
for state in ephemeris.steps(60):
    print(state.epoch, state.position, state.velocity)
```

It is also possible to retrieve a complete list of states and covariances through the `.states` and `.covariances` properties.

```python
for state in ephemeris.states:
    print(state.epoch, state.position, state.velocity)

for covariance in ephemeris.covariances:
    print(covariance.epoch, covariance.matrix)
```

To read OEM metadata, access the `.header` attribute. The header acts as a dictionary and supports basic getting and setting operations. Similarly, segments expose metadata through the `.metadata` attribute. Both headers and metadata support the standard `items` attribute.

```python
print(ephemeris.header["CCSDS_OEM_VERS"])
print(ephemeris.segments[0].metadata["CENTER_NAME"])
```
