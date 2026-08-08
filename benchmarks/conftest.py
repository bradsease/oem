from pathlib import Path

import pytest

from oem import OrbitEphemerisMessage

SAMPLE_DIR = Path(__file__).parents[1] / "tests" / "samples" / "real"
REAL_OEM_FILES = ("LEO_60s.oem", "MEO_60s.oem", "GEO_60s.oem")


@pytest.fixture(scope="module", params=REAL_OEM_FILES)
def real_oem_path(request):
    """A representative real-world KVN OEM at a 60-second cadence."""
    return SAMPLE_DIR / request.param


@pytest.fixture(scope="module")
def real_oem(real_oem_path):
    """Parse each fixture once when parsing is outside the measured operation."""
    return OrbitEphemerisMessage.open(real_oem_path)


@pytest.fixture(scope="module")
def comparison_oems():
    """A compatible OEM pair with a known, non-zero relative position."""
    return (
        OrbitEphemerisMessage.open(SAMPLE_DIR / "CompareExample1.oem"),
        OrbitEphemerisMessage.open(SAMPLE_DIR / "CompareExample2.oem"),
    )
