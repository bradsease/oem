# Python Orbit Ephemeris Message tools
Python tools for working with Orbit Ephemeris Messages (OEMs).


## Development Status

[![GitHub Release](https://img.shields.io/github/v/release/bradsease/oem)](https://github.com/bradsease/oem/releases) [![GitHub](https://img.shields.io/github/license/bradsease/oem)](https://github.com/bradsease/oem/blob/main/LICENSE)

[![GitHub last commit](https://img.shields.io/github/last-commit/bradsease/oem)](https://github.com/bradsease/oem) [![Pipeline Status](https://github.com/bradsease/oem/actions/workflows/python-package.yml/badge.svg)](https://github.com/bradsease/oem/actions/workflows/python-package.yml) [![Coverage Status](https://coveralls.io/repos/github/bradsease/oem/badge.svg)](https://coveralls.io/github/bradsease/oem)


## Installation
The `oem` package is available through `pip`.
```
pip install oem
```

## Documentation
See the full [documentation here](https://bsease.gitbook.io/oem)


## Basic Usage
The `OrbitEphemerisMessage` class is the primary interface for OEM Files.
```python
from oem import OrbitEphemerisMessage

ephemeris = OrbitEphemerisMessage.open("input_file.oem")
```
Each OEM is made up of one or more segments of state and optional covariance data. The `OrbitEphemerisMessage` class provides iterables for both.
```python
for segment in ephemeris:
    for state in segment:
        print(state.epoch, state.position, state.velocity, state.acceleration)

    for covariance in segment.covariances:
        print(covariance.epoch, covariance.matrix)
```
All vectors and matrices are numpy arrays.

It is also possible to retrieve a complete list of states and covariances through the `.states` and `.covariances` properties. These attributes streamline interaction with single-segment ephemerides.
```python
for state in ephemeris.states:
    print(state.epoch, state.position, state.velocity)
for covariance in ephemeris.covariances:
    print(covariance.epoch, covariance.matrix)
```

To sample a state at an arbitrary epoch, simply call the ephemeris with an astropy Time object

```python
epoch = Time("2020-01-01T00:00:00", scale="utc")
sampled_state = ephemeris(epoch)
```

Note that this type of sampling is only supported if the time system of the target ephemeris is supported by astropy Time objects. The `.steps` method of both `OrbitEphemerisMessage` and `EphemerisSegment` objects enables iterable, equal-time sampling of ephemeris data. The following example samples an OEM at a 60-second interval.

```python
for state in oem.steps(60)
    pass
```

The above example works for both single- and multi-segment OEMs, however the step sizes may vary at the boundary of the segments. To get consistent step sizes with multiple segments, use the segment interface directly.

```python
for segment in oem:
    for state in segment.steps(60):
        pass
```

The `OrbitEphemerisMessage` facilitates writing of OEMs. To save an already-open OEM, use `.save_as`:
```python
ephemeris.save_as("output.oem", file_format="xml")
```
To convert an ephemeris from one type to another, use the `.convert` class method.
```python
OrbitEphemerisMessage.convert("input_file.oem", "output_file.oem", "kvn")
```


## Reference Standards

This implementation follows the CCSDS recommended standards for Orbit Data Messages.

[1] *Orbit Data Messages*, CCSDS 502.0-B-3, 2023. Available: https://ccsds.org/wp-content/uploads/gravity_forms/5-448e85c647331d9cbaf66c096458bdd5/2025/01//502x0b3e1.pdf

[2] *XML Specification for Navigation Data Messages*, CCSDS 505.0-B-3, 2023. Available: https://ccsds.org/wp-content/uploads/gravity_forms/5-448e85c647331d9cbaf66c096458bdd5/2025/01//505x0b3e2.pdf
