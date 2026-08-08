from astropy.time import TimeDelta

from oem import OrbitEphemerisMessage


def test_initial_sample(benchmark, real_oem_path):
    """Measure parsing plus first interpolation, including interpolator setup."""

    def sample():
        oem = OrbitEphemerisMessage.open(real_oem_path)
        start, stop = oem.span
        return oem(start + (stop - start) / 2)

    benchmark(sample)


def test_cached_interpolation(benchmark, real_oem):
    """Measure repeated samples that reuse the current local interpolator."""
    epoch = real_oem.span[0] + TimeDelta(1, format="sec")
    real_oem(epoch)

    benchmark(real_oem, epoch)


def test_interpolation_across_windows(benchmark, real_oem):
    """Measure a full source cadence scan, including local-window replacement."""
    epochs = tuple(state.epoch for state in real_oem.states)

    def sample_all():
        return tuple(real_oem(epoch) for epoch in epochs)

    benchmark(sample_all)
