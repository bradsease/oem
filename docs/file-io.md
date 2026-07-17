# Interacting with Files

[Back to documentation index](index.md) | [Working with Data](data.md)

The `OrbitEphemerisMessage` class is the primary interface for OEM files, regardless of the internal file format, KVN (Key-Value Notation, the most common) or XML. To open an OEM into the current context, use the `.open` class method.

```python
from oem import OrbitEphemerisMessage

ephemeris = OrbitEphemerisMessage.open("input_file.oem")
```

The `OrbitEphemerisMessage` facilitates writing of OEMs. To save an already-open OEM, use `.save_as` and optionally specify the internal data format. The default internal data format is `kvn`.

```python
ephemeris.save_as("output.oem", file_format="xml")
```

To convert an ephemeris directly from one format to another, use the `.convert` class method. For example, to convert an XML-formatted OEM to KVN format:

```python
OrbitEphemerisMessage.convert("input_file.oem", "output_file.oem", "kvn")
```

Ephemeris files compressed with gzip, bz2, and lzma are also natively supported for reading and writing. Compressed output is not currently supported by the `convert` method.

```python
ephemeris = OrbitEphemerisMessage.open("input_file.oem.gz")
ephemeris.save("new_file.oem.bz2", compression="bz2")
```
