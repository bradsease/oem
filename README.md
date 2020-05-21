# Python Orbital Ephemeris Message tools
Python tools for working with Orbital Ephemeris Messages (OEMs).


## Development Status

[![GitHub Release](https://img.shields.io/github/v/release/bradsease/oem)](https://github.com/bradsease/oem/releases) [![GitHub](https://img.shields.io/github/license/bradsease/oem)](https://github.com/bradsease/oem/blob/master/LICENSE)

[![GitHub last commit](https://img.shields.io/github/last-commit/bradsease/oem)](https://github.com/bradsease/oem) [![Pipeline Status](https://gitlab.com/bradsease/oem/badges/master/pipeline.svg)](https://gitlab.com/bradsease/oem/pipelines) [![Coverage Status](https://coveralls.io/repos/github/bradsease/oem/badge.svg?branch=HEAD)](https://coveralls.io/github/bradsease/oem?branch=HEAD) [![Documentation Status](https://readthedocs.org/projects/oem/badge/?version=latest)](https://oem.readthedocs.io/en/latest/?badge=latest)


## Installation
The `oem` package is available through `pip`.
```
pip install oem
```

## Usage
The `OrbitalEphemerisMessage` class is the primary interface for OEM Files.
```python
from oem import OrbitalEphemerisMessage

ephemeris = OrbitalEphemerisMessage.from_ascii_oem(file_path)
```
Each OEM is made up of one or more segments of state and optional covariance data. The `OrbitalEphemerisMessage` class provides iterables for both.
```python
for segment in ephemeris:
    for state in segment:
        print(state.epoch, state.position, state.velocity)

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


## Reference Standards

This implementation follows the CCSDS recommended standards for Orbit Data Messages.

[1] *Orbit Data Messages*, CCSDS 502.0-B-2, 2012. Available: https://public.ccsds.org/Pubs/502x0b2c1.pdf

[2] *XML Specification for Navigation Data Messages*, CCSDS 505.0-B-1, 2010. Available: https://public.ccsds.org/Pubs/505x0b1.pdf
