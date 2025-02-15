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
