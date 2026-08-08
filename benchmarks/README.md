# Benchmark Suite

This directory contains repeatable `pytest-benchmark` measurements for the
library's public OEM workflows. The real-world fixtures under
`tests/samples/real` are used to cover LEO, MEO, and GEO inputs without adding
synthetic performance-only data.

Install the development dependencies, including the benchmark plugin:

```console
uv venv
uv pip install -e ".[test,tle]"
```

Run the suite without mixing it into correctness test output:

```console
uv run pytest benchmarks --benchmark-only
```

Store a baseline before an optimization and compare a later run against it:

```console
uv run pytest benchmarks --benchmark-only --benchmark-save baseline
uv run pytest benchmarks --benchmark-only --benchmark-compare baseline
```

Benchmark results are sensitive to the Python version, dependency versions,
host CPU, and filesystem cache. Compare runs made in the same environment and
focus on a benchmark's relative change rather than its absolute timing.

## Coverage

| Module | Operation measured | Included work |
| --- | --- | --- |
| `test_parsing.py` | `OrbitEphemerisMessage.open` | File I/O, KVN parsing, time conversion, validation, and object construction. |
| `test_sampling.py` | First, cached, and cross-window samples | Interpolator initialization, a cached local interpolation, and a full source-cadence scan that replaces local windows. |
| `test_traversal.py` | Source-state and stepped traversal | `State` object materialization and interpolated iteration at a 10-minute cadence. |
| `test_serialization.py` | `save_as` in KVN and XML | OEM formatting, serialization, and output write I/O. |
| `test_comparison.py` | Comparison construction and sampling | Compatible-segment matching, overlap detection, interpolation, and RIC calculations. |

Fixtures are parsed outside the measurement except in the parsing and
first-sample benchmarks, which deliberately include that work. Serialization
writes to pytest-managed temporary paths, so the benchmark does not alter
repository files.
