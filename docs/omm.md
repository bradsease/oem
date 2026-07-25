# Orbit Mean-Elements Messages

[Back to documentation index](index.md) | [Interacting with Files](file-io.md) | [TLE Support](tle-support.md)

The `oem.omm` module reads, writes, and converts CCSDS Orbit Mean-Elements
Messages (OMMs). OMM versions 2.0 and 3.0 are supported in KVN and XML formats.

## Opening an OMM

Use `OrbitMeanElementsMessage.open` to read either a KVN or XML OMM. The format
is detected from the XML declaration; files without one are treated as KVN.

```python
from oem.omm import OrbitMeanElementsMessage

omm = OrbitMeanElementsMessage.open("input_file.omm")

print(omm.version)
print(omm.metadata["OBJECT_NAME"])
print(omm.data["ECCENTRICITY"])
print(omm.epoch)
```

The header, metadata, and data sections are available as `omm.header`,
`omm.metadata`, and `omm.data`. Numeric data fields are returned as numbers and
epoch fields are returned as Astropy `Time` values.

## Saving and Converting

Save an OMM as KVN, the default format, or XML:

```python
omm.save_as("output.omm")
omm.save_as("output.xml", file_format="xml")
```

To convert directly between KVN and XML without keeping the message in the
current context, use `convert`:

```python
OrbitMeanElementsMessage.convert(
    "input.omm",
    "output.xml",
    file_format="xml",
)
```

## Propagating an OMM

Install the optional `tle` extra to propagate an SGP4-compatible OMM:

```bash
pip install oem[tle]
```

Use `at` for a single propagated state:

```python
from astropy.time import Time

state = omm.at(Time("2024-03-10T00:00:00", scale="utc"), frame="TEME")
print(state.position)
print(state.velocity)
```

For a series of states, convert the OMM to an OEM:

```python
from astropy import units as u

start = omm.epoch
stop = start + 1 * u.day
oem = omm.to_oem(start, stop, step=60, frame="ICRF")
```

Propagation currently requires an OMM using the `SGP4` or `SGP/SGP4` mean
element theory.
