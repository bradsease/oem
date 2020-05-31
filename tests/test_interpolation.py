import pytest
import numpy as np
import datetime as dt
from astropy.time import Time, TimeDelta

from oem.components import State
from oem.interp import (
    LagrangeStateInterpolator, HermiteStateInterpolator, EphemerisInterpolator)


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
        Time(start_epoch + dt.timedelta(seconds=t_step*idx))
        for idx in range(count)
    ]
    positions = [poly([t_step*idx]*3) for idx in range(count)]
    velocities = [poly.deriv()([t_step*idx]*3) for idx in range(count)]
    if accel:
        accelerations = [
            poly.deriv().deriv()([t_step*idx]*3)
            for idx in range(count)
        ]
    else:
        accelerations = [None]*count
    return [
        State(epoch, position, velocity, acceleration)
        for epoch, position, velocity, acceleration
        in zip(epochs, positions, velocities, accelerations)
    ]


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize(
    "Interpolator, samples",
    ((LagrangeStateInterpolator, 8), (HermiteStateInterpolator, 4))
)
def test_interpolators(Interpolator, samples, has_accel):
    position = np.poly1d([.1, .1, .1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 60

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = Interpolator(states)

    for elapsed in np.arange(0, (samples-1)*time_step, 1):
        test_epoch = states[0].epoch + TimeDelta(elapsed, format="sec")
        predict = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict.position, position(elapsed))
        np.testing.assert_almost_equal(predict.velocity, velocity(elapsed))
        if has_accel:
            np.testing.assert_almost_equal(
                predict.acceleration, acceleration(elapsed)
            )


@pytest.mark.parametrize("has_accel", (True, False))
@pytest.mark.parametrize("method, order", (("LAGRANGE", 8), ("HERMITE", 9)))
def test_ephemeris_interpolator(method, order, has_accel):
    position = np.poly1d([.1, .1, .1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    time_step = 30
    samples = 25

    states = _make_test_states(position, time_step, samples, accel=has_accel)
    interpolator = EphemerisInterpolator(states, method, order)

    for elapsed in np.arange(0, (samples-1)*time_step, 5):
        test_epoch = states[0].epoch + TimeDelta(elapsed, format="sec")
        predict = interpolator(test_epoch)
        np.testing.assert_almost_equal(predict.position, position(elapsed), 6)
        np.testing.assert_almost_equal(predict.velocity, velocity(elapsed), 6)
        if has_accel:
            np.testing.assert_almost_equal(
                predict.acceleration, acceleration(elapsed), 6
            )
