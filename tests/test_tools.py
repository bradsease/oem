from datetime import datetime

import pytest
from astropy.time import Time

from oem import tools


def test_parse_integer():
    tools.parse_integer(1, None)
    tools.parse_integer(1.0, None)
    with pytest.raises(ValueError):
        tools.parse_integer(1.1, None)


def test_format_epoch():
    assert (
        tools.format_epoch(datetime.fromisoformat("2024-02-08T19:46:03.597928"))
        == "2024-02-08T19:46:03.597928"
    )
    assert (
        tools.format_epoch(Time("2024-02-08T19:46:03.597928", precision=6))
        == "2024-02-08T19:46:03.597928"
    )


def test_parse_epoch_unsupported_time_system_warns():
    metadata = {"TIME_SYSTEM": "ABCD"}

    with pytest.warns(UserWarning, match="Unsupported TIME_SYSTEM 'abcd'"):
        parsed_epoch = tools.parse_epoch("2024-02-08T19:46:03.597928", metadata)

    assert isinstance(parsed_epoch, datetime)


def test_bulk_parse_epochs_unsupported_time_system_warns():
    metadata = {"TIME_SYSTEM": "ABCD"}
    epochs = ("2024-02-08T19:46:03.597928", "2024-02-08T19:46:04.597928")

    with pytest.warns(UserWarning, match="Unsupported TIME_SYSTEM 'abcd'"):
        parsed_epochs = tools._bulk_parse_epochs(epochs, metadata)

    assert len(parsed_epochs) == len(epochs)
