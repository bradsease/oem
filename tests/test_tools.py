import pytest
from astropy.time import Time, TimeDelta

from oem import tools


@pytest.mark.parametrize(
    ("contents", "expected"),
    (
        ("<oem />", False),
        ("\n\t<!-- leading comment -->\n<omm />", False),
        ("CCSDS_OEM_VERS = 2.0\n", True),
    ),
)
def test_is_kvn_detects_first_non_whitespace_character(tmp_path, contents, expected):
    message_path = tmp_path / "message"
    message_path.write_text(contents)
    assert tools.is_kvn(message_path) is expected


def test_parse_integer():
    tools.parse_integer(1, None)
    tools.parse_integer(1.0, None)
    with pytest.raises(ValueError):
        tools.parse_integer(1.1, None)


def test_format_epoch():
    assert (
        tools.format_epoch(Time("2024-02-08T19:46:03.597928", precision=6))
        == "2024-02-08T19:46:03.597928"
    )


def test_parse_epoch_unsupported_time_system_warns():
    metadata = {"TIME_SYSTEM": "ABCD"}

    with pytest.warns(UserWarning, match="Unsupported TIME_SYSTEM 'abcd'"):
        parsed_epoch = tools.parse_epoch("2024-02-08T19:46:03.597928", metadata)

    assert isinstance(parsed_epoch, Time)
    assert parsed_epoch.scale == "local"


def test_bulk_parse_epochs_unsupported_time_system_warns():
    metadata = {"TIME_SYSTEM": "ABCD"}
    epochs = ("2024-02-08T19:46:03.597928", "2024-02-08T19:46:04.597928")

    with pytest.warns(UserWarning, match="Unsupported TIME_SYSTEM 'abcd'"):
        parsed_epochs = tools._bulk_parse_epochs(epochs, metadata)

    assert isinstance(parsed_epochs, Time)
    assert parsed_epochs.scale == "local"
    assert len(parsed_epochs) == len(epochs)


@pytest.mark.parametrize(
    "duration, step, expected_elapsed",
    (
        (10, 2, (0, 2, 4, 6, 8, 10)),
        (0.3, 0.1, (0, 0.1, 0.2, 0.3)),
    ),
)
def test_time_range_includes_exact_step_stop(duration, step, expected_elapsed):
    start = Time("2024-02-08T19:46:03", scale="utc")
    stop = start + TimeDelta(duration, format="sec")

    epochs = list(tools.time_range(start, stop, step))

    assert epochs == [
        start + TimeDelta(elapsed, format="sec") for elapsed in expected_elapsed[:-1]
    ] + [stop]


def test_time_range_appends_non_divisible_stop():
    start = Time("2024-02-08T19:46:03", scale="utc")
    stop = start + TimeDelta(10, format="sec")

    epochs = list(tools.time_range(start, stop, 4))

    assert epochs == [
        start,
        start + TimeDelta(4, format="sec"),
        start + TimeDelta(8, format="sec"),
        stop,
    ]


def test_time_range_zero_duration_yields_one_epoch():
    epoch = Time("2024-02-08T19:46:03", scale="utc")

    assert list(tools.time_range(epoch, epoch, 10)) == [epoch]
