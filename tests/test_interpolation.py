import datetime as dt
from pathlib import Path

import numpy as np
import pytest
from astropy.time import Time, TimeDelta

from oem import OrbitEphemerisMessage
from oem.interp import (
    EphemerisInterpolator,
    HermiteStateInterpolator,
    LagrangeStateInterpolator,
)

THIS_DIR = Path(__file__).parent
SAMPLE_DIR = THIS_DIR / "samples"


def _make_test_states(poly, t_step, count, accel=True):
    """Create state samples for testing.

    Args:
        poly (poly1d): Polynomial describing position history.
        t_step (float): State time step in seconds.
        count (int): Number of points to sample.
        accel (bool, optional): If True, output States will have accelerations.

    Returns:
        states (list): List of State with position, velocity, and acceleration
            following poly, poly.deriv, and poly.deriv.deriv, respectively.
            Epochs are DateTimes starting at the current time and stepping
            by t_step.
    """
    start_epoch = dt.datetime.now()
    epochs = [
        Time(start_epoch + dt.timedelta(seconds=t_step * idx)) for idx in range(count)
    ]
    positions = [poly([t_step * idx] * 3) for idx in range(count)]
    velocities = [poly.deriv()([t_step * idx] * 3) for idx in range(count)]
    if accel:
        accelerations = [
            poly.deriv().deriv()([t_step * idx] * 3) for idx in range(count)
        ]
        return (epochs, *zip(*positions), *zip(*velocities), *zip(*accelerations))
    else:
        return (epochs, *zip(*positions), *zip(*velocities))


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize(
    "Interpolator, samples",
    ((LagrangeStateInterpolator, 8), (HermiteStateInterpolator, 4)),
)
def test_interpolators(Interpolator, samples, has_accel):
    position = np.poly1d([0.1, 0.1, 0.1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 60

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = Interpolator(states)

    for elapsed in np.arange(0, (samples - 1) * time_step, 1):
        test_epoch = states[0][0] + TimeDelta(elapsed, format="sec")
        predict_pos, predict_vel, predict_accel = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict_pos, position(elapsed))
        np.testing.assert_almost_equal(predict_vel, velocity(elapsed))
        if has_accel:
            np.testing.assert_almost_equal(predict_accel, acceleration(elapsed))


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize("method, order", (("LAGRANGE", 8), ("HERMITE", 9)))
def test_ephemeris_interpolator(method, order, has_accel):
    position = np.poly1d([0.1, 0.1, 0.1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 30
    samples = 25

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = EphemerisInterpolator(states, method, order)

    for elapsed in np.arange(0, (samples - 1) * time_step, 5):
        test_epoch = states[0][0] + TimeDelta(elapsed, format="sec")
        predict_pos, predict_vel, predict_accel = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict_pos, position(elapsed), 6)
        np.testing.assert_almost_equal(predict_vel, velocity(elapsed), 6)
        if has_accel:
            np.testing.assert_almost_equal(predict_accel, acceleration(elapsed), 6)


@pytest.mark.parametrize(
    "coarse_file, fine_file",
    (
        ("GEO_60s.oem", "GEO_20s.oem"),
        ("MEO_60s.oem", "MEO_20s.oem"),
        ("LEO_60s.oem", "LEO_10s.oem"),
    ),
)
def test_ephemeris_accuracy(coarse_file, fine_file):
    fine_sample = SAMPLE_DIR / "real" / fine_file
    coarse_sample = SAMPLE_DIR / "real" / coarse_file
    fine_oem = OrbitEphemerisMessage.open(fine_sample)
    coarse_oem = OrbitEphemerisMessage.open(coarse_sample)

    for state in fine_oem.states:
        predict = coarse_oem(state.epoch)
        np.testing.assert_almost_equal(predict.position, state.position, 6)
        np.testing.assert_almost_equal(predict.velocity, state.velocity, 6)
        if state.has_accel:
            np.testing.assert_almost_equal(predict.acceleration, state.acceleration, 6)


@pytest.mark.parametrize("input_file", ("GEO_20s.oem", "MEO_20s.oem", "LEO_10s.oem"))
def test_ephemeris_stepping(input_file):
    sample_file = SAMPLE_DIR / "real" / input_file
    oem = OrbitEphemerisMessage.open(sample_file)

    for state in oem.steps(601):
        assert state.epoch in oem

    for segment in oem:
        for state in segment.steps(601):
            assert state.epoch in oem

    out_of_bounds_epoch = oem.span[0] - TimeDelta(1)
    with pytest.raises(ValueError):
        oem(out_of_bounds_epoch)
    for segment in oem:
        with pytest.raises(ValueError):
            segment(out_of_bounds_epoch)


@pytest.mark.parametrize("input_file", ("GEO_20s.oem", "MEO_20s.oem", "LEO_10s.oem"))
def test_ephemeris_resample(input_file):
    sample_file = SAMPLE_DIR / "real" / input_file
    step_size = 600
    oem = OrbitEphemerisMessage.open(sample_file)
    new_oem = oem.resample(step_size)

    for idx in range(1, len(new_oem.states)):
        assert np.isclose(
            (new_oem.states[idx].epoch - new_oem.states[idx - 1].epoch).sec, step_size
        )
