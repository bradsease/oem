import pytest
from oem import tools


def test_parse_integer():
    tools.parse_integer(1)
    tools.parse_integer(1.0)
    with pytest.raises(ValueError):
        tools.parse_integer(1.1)
