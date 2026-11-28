# JPL Horizons Support

`oem.horizons.horizons_to_oem` requests Cartesian state vectors from the
[JPL Horizons API](https://ssd-api.jpl.nasa.gov/doc/horizons.html) and returns
an OEM 3.0. Saved KVN files declare `CCSDS_OEM_VERS = 3.0`; saved XML files
declare `version="3.0"`.

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
body ID such as `"399"`, or a body-center specification such as `"500@399"`,
`"@399"`, `"g@399"`, or `"geo@399"`. These forms all select Earth's center.
Bare IDs always select bodies, not observatories: `"568"` is sent as `"500@568"`,
not as the Mauna Kea site.

Topocentric sites such as `"568@399"` (Mauna Kea) are also accepted. The
converter determines the actual origin from the returned `Center body name`
and `Center-site name`, rather than the input syntax. Responses with
`BODY CENTER` or `GEOCENTRIC` use the body name as the OEM `CENTER_NAME`.
Other sites use this convention:

```text
CENTER_NAME = Earth: Mauna Kea (cylindrical: 204.5278 deg, 6006.35451 km, 2151.0229 km)
REF_FRAME = ICRF
```

The coordinates come from Horizons' `Center cylindric` field: east longitude
in degrees, distance from the body's rotation axis in kilometers, and signed
height above its equatorial plane in kilometers. The coordinates are included
for all sites, including `USER DEFINED` sites, so different locations with the
same display name are not treated as the same origin. Numeric formatting is
normalized without intentionally reducing the returned coordinate precision.
Use an explicit station code when selecting a particular installation:
Horizons can resolve a site-name search to a different installation than
expected (for example, `"Mauna Kea@399"` need not select station `568`).
Complete `@` specifications are passed through to Horizons; its validation
still applies. This helper does not add separate `SITE_COORD` or `COORD_TYPE`
parameters.

OEM 3.0 (CCSDS 502.0-B-3, Table 5-3) permits reference frame centers other
than natural bodies. The site naming above is this converter's documented
convention, not a standardized CCSDS station identifier. Downstream consumers
must understand this convention to interpret or transform a site origin.
As required by annex B2, communicate to recipients that a site origin is not
a gravitational center: conventional orbit propagation or extrapolation is
not advisable, and interpolation must not use classical orbit-propagation
forces such as gravitational constants or drag.
The vectors remain geometric, site-relative Cartesian states aligned with
ICRF; they are not translated to the body center or rotated into local
horizon axes. The site origin is preserved when saving and reopening KVN or
XML OEMs.

Missing body/site identification or missing, malformed, or nonfinite site
coordinates raise `ValueError`; the converter does not guess the origin.

`step_size` is a Horizons output step-size string such as `"1h"` or `"1d"`.
