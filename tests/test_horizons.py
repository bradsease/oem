import json
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from astropy.time import Time

from oem import OrbitEphemerisMessage
from oem.horizons import horizons_to_oem

RESULT = """
Target body name: Mars (499)                      {source: mar099}
Center body name: Earth (399)                     {source: DE441}
Center-site name: BODY CENTER
$$SOE
2460676.500000000, A.D. 2025-Jan-01 00:00:00.0000, -5.131243251395218E+07,  7.395563972951464E+07,  3.936954332707308E+07,  7.779268790844085E+00, -3.973484497151238E-01,  2.839990146499576E-01,
2460676.541666667, A.D. 2025-Jan-01 01:00:00.0000, -5.128442968203197E+07,  7.395423264390281E+07,  3.937057542487966E+07,  7.777857596610779E+00, -3.843660900671573E-01,  2.893885105354175E-01,
$$EOE
"""

SITE_RESULT = """
Target body name: Earth (399)                     {source: DE441}
Center body name: Earth (399)                     {source: DE441}
Center-site name: Mauna Kea
Center cylindric: 204.5278, 6006.35451, 2151.0229 {E-lon(deg),Dxy(km),Dz(km)}
$$SOE
2460676.500000000, A.D. 2025-Jan-01 00:00:00.0000, -3.459518124600110E+03,  4.913590062524923E+03, -2.142792817133121E+03, -3.583089731202376E-01, -2.518916691104831E-01,  8.792191793651878E-04,
2460676.541666667, A.D. 2025-Jan-01 01:00:00.0000, -4.616321926152586E+03,  3.848817853130823E+03, -2.139945565121212E+03, -2.806647808406881E-01, -3.362473864680433E-01,  6.934931481824522E-04,
$$EOE
"""
SITE_CENTER = (
    "Earth: Mauna Kea (cylindrical: 204.5278 deg, 6006.35451 km, 2151.0229 km)"
)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.mark.parametrize(
    "center, requested_center",
    [
        ("399", "500@399"),
        ("500@399", "500@399"),
        ("@399", "@399"),
        ("g@399", "g@399"),
        ("geo@399", "geo@399"),
        (" 500 @ 399 ", " 500 @ 399 "),
        (" GEO @399", " GEO @399"),
    ],
)
def test_horizons_to_oem(monkeypatch, center, requested_center):
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        assert timeout == 10
        return Response({"result": RESULT})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem(
        "499",
        center,
        Time("2025-01-01T00:00:00", scale="utc"),
        Time("2025-01-01T01:00:00", scale="utc"),
        step_size="1h",
        timeout=10,
    )

    assert requested["COMMAND"] == ["'499'"]
    assert requested["CENTER"] == [f"'{requested_center}'"]
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


@pytest.mark.parametrize("file_format", ["kvn", "xml"])
@pytest.mark.parametrize("result", [RESULT, SITE_RESULT], ids=["body", "site"])
def test_horizons_writes_oem_3(monkeypatch, tmp_path, file_format, result):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response({"result": result}),
    )
    message = horizons_to_oem("399", "399", Time("2025-01-01"), Time("2025-01-02"))
    assert message.version == "3.0"
    assert message.header["CCSDS_OEM_VERS"] == "3.0"
    assert message.segments[0].version == "3.0"
    assert message.segments[0].metadata.version == "3.0"
    assert all(state.version == "3.0" for state in message.states)

    path = tmp_path / f"horizons.{file_format}"
    message.save_as(path, file_format=file_format)
    if file_format == "kvn":
        assert path.read_text().startswith("CCSDS_OEM_VERS = 3.0\n")
    else:
        assert ElementTree.parse(path).getroot().attrib["version"] == "3.0"

    restored = OrbitEphemerisMessage.open(path)
    assert restored.version == "3.0"
    assert restored.header["CCSDS_OEM_VERS"] == "3.0"
    assert restored.segments[0].version == "3.0"
    assert restored.segments[0].metadata.version == "3.0"
    assert all(state.version == "3.0" for state in restored.states)
    assert (
        restored.segments[0].metadata["CENTER_NAME"]
        == message.segments[0].metadata["CENTER_NAME"]
    )


@pytest.mark.parametrize(
    "center",
    [
        "568@399",
        " 568 @ 399 ",
        "Mauna Kea@399",
        "399",  # The response, not the input syntax, identifies the origin.
    ],
)
def test_horizons_topocentric_origin(monkeypatch, center):
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        return Response({"result": SITE_RESULT})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem(
        "399",
        center,
        Time("2025-01-01", scale="utc"),
        Time("2025-01-01T01:00:00", scale="utc"),
    )

    expected_center = center if "@" in center else f"500@{center}"
    assert requested["CENTER"] == [f"'{expected_center}'"]
    assert requested["REF_PLANE"] == ["FRAME"]
    assert requested["VEC_CORR"] == ["NONE"]
    assert oem.segments[0].metadata["CENTER_NAME"] == SITE_CENTER
    assert oem.states[0].center == SITE_CENTER
    assert oem.states[0].frame == "ICRF"
    assert oem.states[0].position.tolist() == pytest.approx(
        [-3459.518124600110, 4913.590062524923, -2142.792817133121]
    )
    assert oem.states[0].velocity.tolist() == pytest.approx(
        [-0.3583089731202376, -0.2518916691104831, 0.0008792191793651878]
    )


@pytest.mark.parametrize("site", ["BODY CENTER", "GEOCENTRIC", " body center "])
def test_horizons_body_center_site_labels(monkeypatch, site):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response(
            {"result": RESULT.replace("BODY CENTER", site)}
        ),
    )
    oem = horizons_to_oem("499", "399", Time("2025-01-01"), Time("2025-01-02"))
    assert oem.segments[0].metadata["CENTER_NAME"] == "Earth"


@pytest.mark.parametrize(
    "center, body, site",
    [
        ("675@", "Earth (399)", "Palomar Mountain"),
        ("Mauna Kea@399", "Earth (399)", "Mauna Kea (25-m, VLBA)"),
        ("1@301", "Moon (301)", "Lunar site"),
        ("Viking-1@499", "Mars (499)", "Viking-1"),
        ("coord@399", "Earth (399)", "(user defined site below)"),
    ],
)
def test_horizons_site_identity_uses_response(monkeypatch, center, body, site):
    result = SITE_RESULT.replace(
        "Center body name: Earth (399)", f"Center body name: {body}"
    ).replace("Mauna Kea", site)
    requested = {}

    def urlopen(url, timeout):
        requested.update(parse_qs(urlsplit(url).query))
        return Response({"result": result})

    monkeypatch.setattr("oem.horizons.urlopen", urlopen)
    oem = horizons_to_oem("399", center, Time("2025-01-01"), Time("2025-01-02"))
    assert requested["CENTER"] == [f"'{center}'"]
    assert oem.segments[0].metadata["CENTER_NAME"] == SITE_CENTER.replace(
        "Earth", body.rsplit(" (", 1)[0]
    ).replace("Mauna Kea", site)


@pytest.mark.parametrize("file_format", ["kvn", "xml"])
@pytest.mark.parametrize("site", ["Mauna Kea", "USER DEFINED"])
def test_horizons_site_round_trip(monkeypatch, tmp_path, file_format, site):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response(
            {"result": SITE_RESULT.replace("Mauna Kea", site)}
        ),
    )
    oem = horizons_to_oem("399", "568@399", Time("2025-01-01"), Time("2025-01-02"))
    path = tmp_path / f"site.{file_format}"
    oem.save_as(path, file_format=file_format)
    restored = OrbitEphemerisMessage.open(path)
    assert restored.segments[0].metadata["CENTER_NAME"] == SITE_CENTER.replace(
        "Mauna Kea", site
    )
    for original, saved in zip(oem.states, restored.states):
        assert saved.center == original.center
        assert saved.frame == original.frame
        assert saved.position.tolist() == pytest.approx(original.position.tolist())
        assert saved.velocity.tolist() == pytest.approx(original.velocity.tolist())


@pytest.mark.parametrize("site", ["Mauna Kea", "USER DEFINED"])
def test_horizons_different_site_coordinates_are_incompatible(monkeypatch, site):
    result = SITE_RESULT.replace("Mauna Kea", site)

    def create_message(response):
        monkeypatch.setattr(
            "oem.horizons.urlopen",
            lambda *args, **kwargs: Response({"result": response}),
        )
        return horizons_to_oem("399", "568@399", Time("2025-01-01"), Time("2025-01-02"))

    first = create_message(result)
    second = create_message(result.replace("6006.35451", "6007.35451"))
    assert first.states[0].center != second.states[0].center
    with pytest.raises(ValueError, match="central body mismatch"):
        first.states[0] - second.states[0]


@pytest.mark.parametrize(
    "coordinates",
    [
        "204.527800, 6006.354510, 2151.022900",
        "2.045278e2, 6.00635451e3, 2.1510229e3",
    ],
)
def test_horizons_equivalent_site_coordinate_formatting(monkeypatch, coordinates):
    result = SITE_RESULT.replace("204.5278, 6006.35451, 2151.0229", coordinates)
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response({"result": result}),
    )
    oem = horizons_to_oem("399", "568@399", Time("2025-01-01"), Time("2025-01-02"))
    assert oem.states[0].center == SITE_CENTER


def test_horizons_site_is_incompatible_with_body_center(monkeypatch):
    messages = []
    for result in (RESULT, SITE_RESULT):
        monkeypatch.setattr(
            "oem.horizons.urlopen",
            lambda *args, **kwargs: Response({"result": result}),
        )
        messages.append(
            horizons_to_oem("399", "399", Time("2025-01-01"), Time("2025-01-02"))
        )
    with pytest.raises(ValueError, match="central body mismatch"):
        messages[0].segments[0] - messages[1].segments[0]


@pytest.mark.parametrize(
    "old, new",
    [
        ("Center body name: Earth (399)                     {source: DE441}", ""),
        ("Center body name: Earth (399)", "Center body name: "),
        ("Center-site name: Mauna Kea", ""),
        ("Center-site name: Mauna Kea", "Center-site name: "),
        (
            "Center cylindric: 204.5278, 6006.35451, 2151.0229",
            "Center cylindric: ",
        ),
        ("Center cylindric:", "Missing cylindric:"),
        ("204.5278, 6006.35451, 2151.0229", "204.5278, 6006.35451"),
        ("204.5278, 6006.35451, 2151.0229", "204.5278, 6006.35451, 2151.0229, 0"),
        ("6006.35451", "not a number"),
        ("6006.35451", "nan"),
        ("6006.35451", "inf"),
    ],
)
def test_horizons_rejects_unidentified_origins(monkeypatch, old, new):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response({"result": SITE_RESULT.replace(old, new)}),
    )
    with pytest.raises(ValueError, match="coordinate origin|site coordinates"):
        horizons_to_oem(
            "399",
            "568@399",
            Time("2025-01-01", scale="utc"),
            Time("2025-01-02", scale="utc"),
        )


@pytest.mark.parametrize(
    "center, error",
    [
        ("399", "bad target"),
        ("g: 155.5, 19.8, 4.2@399", "No site matches."),
    ],
)
def test_horizons_api_error(monkeypatch, center, error):
    monkeypatch.setattr(
        "oem.horizons.urlopen",
        lambda *args, **kwargs: Response({"error": error}),
    )

    with pytest.raises(ValueError, match=f"Horizons API error: {error}"):
        horizons_to_oem(
            "bad",
            center,
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
