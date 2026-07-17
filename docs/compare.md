# Comparing Ephemerides

[Back to documentation index](index.md) | [Working with Data](data.md)

OEM objects currently support basic comparison operations if certain conditions are met. To compare two ephemerides, they must have overlapping segments with identical reference frames and central bodies. Position and velocity comparisons are calculated in the segment reference frame and no corrections are applied for rotating reference frames. Reference frame conversions are not currently supported.

To compare ephemerides, subtract two OEM objects. The resulting `StateCompare` object supports the `.segments` method and the `.steps` method of the regular OEM object.

The following example calculates direct position and velocity differences in 60-second intervals.

```python
diff = ephemeris1 - ephemeris2
for diff_state in diff.steps(60):
    print(diff_state.epoch, diff_state.position, diff_state.velocity)
```

Range and range-rate calculations are also supported.

```python
for diff_state in diff.steps(60):
    print(diff_state.epoch, diff_state.range, diff_state.range_rate)
```
