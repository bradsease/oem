# TLE Support

[Back to documentation index](index.md) | [Working with Data](data.md)

When `oem` is installed with the `tle` extra, it provides basic support for creating OEM files from TLEs. Internally, the TLE is propagated using the `sgp4` package.

```python
from oem.tle import tle_to_oem
from astropy.time import Time

tle = [
    "ISS (ZARYA)",
    "1 25544U 98067A   24069.80428241  .00013510  00000+0  24615-3 0  9990",
    "2 25544  51.6414  87.9469 0006205 347.9554   1.1547 15.4977143144313",
]
start_epoch = Time("2024-03-09T00:00:00.000", format="isot", scale="utc")
stop_epoch = Time("2024-03-10T00:00:00.000", format="isot", scale="utc")
step = 60
frame = "ICRF"  # ICRF or TEME

ephemeris = tle_to_oem(tle, start_epoch, stop_epoch, step, frame=frame)
ephemeris.save_as("iss.oem")
```
