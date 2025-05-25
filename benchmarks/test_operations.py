import pytest

from oem import OrbitEphemerisMessage
from tests.test_samples import SAMPLE_DIR


@pytest.mark.parametrize(
    "file_path",
    [
        SAMPLE_DIR / "real" / "LEO_60s.oem",
        SAMPLE_DIR / "real" / "MEO_60s.oem",
        SAMPLE_DIR / "real" / "GEO_60s.oem",
    ],
)
def test_stepping(benchmark, file_path):
    oem = OrbitEphemerisMessage.open(file_path)

    def fcn():
        for _ in oem.steps(1000):
            pass

    benchmark(fcn)
