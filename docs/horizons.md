# JPL Horizons Support

`oem.horizons.horizons_to_oem` requests Cartesian state vectors from the
[JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html) and returns
an OEM.

The returned ephemeris uses ICRF, UTC by default, kilometers, and kilometers
per second. Set `time_system="TT"` or `time_system="TDB"` to request TT or TDB
output instead.

```python
from astropy.time import Time

from oem.horizons import horizons_to_oem

oem = horizons_to_oem(
    target="499",  # Mars
    center="399",  # Earth
    start_epoch=Time("2025-01-01T00:00:00", scale="utc"),
    stop_epoch=Time("2025-01-08T00:00:00", scale="utc"),
    step_size="1h",
)
```

`target` uses [Horizons target-selection syntax](https://ssd.jpl.nasa.gov/horizons/manual.html#select).
For example, use `"1;"` for the small body Ceres. `center` accepts a central
body ID such as `"399"`, or a complete Horizons center specification such as
`"500@399"`. `step_size` is a Horizons output step-size string such as `"1h"`
or `"1d"`.
