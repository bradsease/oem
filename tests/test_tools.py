import pytest
from astropy.time import Time

from oem import tools
from oem.components.header import HeaderSection
from oem.components.metadata import MetaDataSection


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


def test_metadata_epoch_retains_nanosecond_precision():
    metadata = {
        "OBJECT_NAME": "OBJECT",
        "OBJECT_ID": "1998-067A",
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "ICRF",
        "TIME_SYSTEM": "UTC",
        "START_TIME": "2024-02-08T19:46:03.123456789",
        "STOP_TIME": "2024-02-08T19:46:04.123456789",
    }
    state_epoch = tools._bulk_parse_epochs((metadata["START_TIME"],), metadata)[0]

    parsed = MetaDataSection(metadata)["START_TIME"]

    assert parsed == state_epoch
    assert parsed == Time(metadata["START_TIME"], format="isot", scale="utc")
    assert tools.format_epoch(parsed) == "2024-02-08T19:46:03.123457"


def test_metadata_epoch_accepts_yday_with_trailing_z():
    metadata = {"TIME_SYSTEM": "UTC"}
    epoch = "2024-039T19:46:03.123456789Z"

    parsed = tools.parse_epoch(epoch, metadata)
    state_epoch = tools._bulk_parse_epochs((epoch,), metadata)[0]

    assert parsed == state_epoch
    assert parsed == Time("2024:039:19:46:03.123456789", format="yday", scale="utc")


def test_metadata_epoch_preserves_existing_calendar_syntax():
    parsed = tools.parse_epoch(" 2024-02-08T19:46:03Z ", {"TIME_SYSTEM": "UTC"})

    assert parsed == Time("2024-02-08T19:46:03", format="isot", scale="utc")


def test_creation_date_accepts_utc_leap_second():
    header = HeaderSection(
        {
            "CCSDS_OEM_VERS": "2.0",
            "CREATION_DATE": "2016-12-31T23:59:60Z",
            "ORIGINATOR": "ORIGINATOR",
        }
    )

    assert header["CREATION_DATE"].isot == "2016-12-31T23:59:60.000000"


def test_metadata_epoch_accepts_utc_leap_second():
    parsed = tools.parse_epoch("2016-12-31T23:59:60Z", {"TIME_SYSTEM": "UTC"})

    assert parsed.isot == "2016-12-31T23:59:60.000000"


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
