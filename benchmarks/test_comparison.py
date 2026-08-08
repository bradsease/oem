def test_construct_comparison(benchmark, comparison_oems):
    """Measure compatible-segment matching and overlap construction."""
    origin, target = comparison_oems
    benchmark(lambda: target - origin)


def test_sample_comparison(benchmark, comparison_oems):
    """Measure comparison sampling plus RIC vector calculations."""
    origin, target = comparison_oems
    comparison = target - origin

    def sample_all():
        return tuple(
            (state.position_ric, state.velocity_ric) for state in comparison.steps(600)
        )

    benchmark(sample_all)
