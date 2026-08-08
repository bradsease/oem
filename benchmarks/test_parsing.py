from oem import OrbitEphemerisMessage


def test_open_kvn(benchmark, real_oem_path):
    """Measure file I/O, KVN parsing, time conversion, and OEM construction."""
    benchmark(OrbitEphemerisMessage.open, real_oem_path)
