def test_state_materialization(benchmark, real_oem):
    """Measure construction of State objects from the stored source vectors."""
    benchmark(lambda: tuple(real_oem.states))


def test_interpolated_steps(benchmark, real_oem):
    """Measure generator traversal with interpolation at a 10-minute cadence."""
    benchmark(lambda: tuple(real_oem.steps(600)))
