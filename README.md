# Python Orbit Ephemeris Message tools
Python tools for working with Orbit Ephemeris Messages (OEMs).


## Development Status

[![GitHub Release](https://img.shields.io/github/v/release/bradsease/oem)](https://github.com/bradsease/oem/releases) [![GitHub](https://img.shields.io/github/license/bradsease/oem)](https://github.com/bradsease/oem/blob/master/LICENSE)

[![GitHub last commit](https://img.shields.io/github/last-commit/bradsease/oem)](https://github.com/bradsease/oem) [![Pipeline Status](https://gitlab.com/bradsease/oem/badges/master/pipeline.svg)](https://gitlab.com/bradsease/oem/pipelines) [![Coverage Status](https://coveralls.io/repos/github/bradsease/oem/badge.svg?branch=HEAD)](https://coveralls.io/github/bradsease/oem?branch=HEAD) [![Documentation Status](https://readthedocs.org/projects/oem/badge/?version=latest)](https://oem.readthedocs.io/en/latest/?badge=latest)


## Installation
The `oem` package is available through `pip`.
```
pip install oem
```

## Usage
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

The `OrbitEphemerisObject` also facilitates writing of OEMs. To save an already-open OEM, use `.save_as`:
```python
ephemeris.save_as("output.oem", file_format="xml")
```
To convert an ephemeris from one type to another, use the `.convert` class method.
```python
OrbitEphemerisMessage.convert("input_file.oem", "output_file.oem", "kvn")
```


## Reference Standards

This implementation follows the CCSDS recommended standards for Orbit Data Messages.

[1] *Orbit Data Messages*, CCSDS 502.0-B-2, 2012. Available: https://public.ccsds.org/Pubs/502x0b2c1.pdf

[2] *XML Specification for Navigation Data Messages*, CCSDS 505.0-B-1, 2010. Available: https://public.ccsds.org/Pubs/505x0b1.pdf
