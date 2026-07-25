import json
from urllib.parse import parse_qs, urlsplit

import pytest
from astropy.time import Time

from oem.horizons import horizons_to_oem

RESULT = """
Target body name: Mars (499)                      {source: mar099}
Center body name: Earth (399)                     {source: DE441}
$$SOE
2460676.500000000, A.D. 2025-Jan-01 00:00:00.0000, -5.131243251395218E+07,  7.395563972951464E+07,  3.936954332707308E+07,  7.779268790844085E+00, -3.973484497151238E-01,  2.839990146499576E-01,
2460676.541666667, A.D. 2025-Jan-01 01:00:00.0000, -5.128442968203197E+07,  7.395423264390281E+07,  3.937057542487966E+07,  7.777857596610779E+00, -3.843660900671573E-01,  2.893885105354175E-01,
$$EOE
"""


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_horizons_to_oem(monkeypatch):
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        assert timeout == 10
        return Response({"result": RESULT})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem(
        "499",
        "399",
        Time("2025-01-01T00:00:00", scale="utc"),
        Time("2025-01-01T01:00:00", scale="utc"),
        step_size="1h",
        timeout=10,
    )

    assert requested["COMMAND"] == ["'499'"]
    assert requested["CENTER"] == ["'500@399'"]
    assert requested["EPHEM_TYPE"] == ["VECTORS"]
    assert requested["TIME_TYPE"] == ["UT"]
    assert requested["OUT_UNITS"] == ["KM-S"]
    assert requested["REF_SYSTEM"] == ["ICRF"]
    assert oem.segments[0].metadata["OBJECT_NAME"] == "Mars"
    assert oem.segments[0].metadata["OBJECT_ID"] == "499"
    assert oem.segments[0].metadata["CENTER_NAME"] == "Earth"
    assert oem.segments[0].metadata["TIME_SYSTEM"] == "UTC"
    assert len(oem.states) == 2
    assert oem.states[0].position.tolist() == pytest.approx(
        [-51312432.51395218, 73955639.72951464, 39369543.32707308]
    )


def test_horizons_api_error(monkeypatch):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response({"error": "bad target"}),
    )

    with pytest.raises(ValueError, match="Horizons API error: bad target"):
        horizons_to_oem(
            "bad",
            "399",
            Time("2025-01-01", scale="tdb"),
            Time("2025-01-02", scale="tdb"),
        )


def test_horizons_tdb_output(monkeypatch):
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        return Response({"result": RESULT})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem(
        "499",
        "399",
        Time("2025-01-01", scale="tdb"),
        Time("2025-01-02", scale="tdb"),
        time_system="TDB",
    )

    assert requested["TIME_TYPE"] == ["TDB"]
    assert oem.segments[0].metadata["TIME_SYSTEM"] == "TDB"


def test_horizons_tt_output(monkeypatch):
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        return Response({"result": RESULT})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem(
        "499",
        "399",
        Time("2025-01-01", scale="tt"),
        Time("2025-01-02", scale="tt"),
        time_system="TT",
    )

    assert requested["TIME_TYPE"] == ["TT"]
    assert oem.segments[0].metadata["TIME_SYSTEM"] == "TT"


def test_horizons_requires_time_instances():
    with pytest.raises(TypeError, match="astropy Time"):
        horizons_to_oem("499", "399", "2025-01-01", "2025-01-02")


def test_horizons_rejects_unknown_time_system():
    with pytest.raises(ValueError, match="time_system must be 'UT', 'TT', or 'TDB'"):
        horizons_to_oem(
            "499",
            "399",
            Time("2025-01-01", scale="utc"),
            Time("2025-01-02", scale="utc"),
            time_system="TAI",
        )
