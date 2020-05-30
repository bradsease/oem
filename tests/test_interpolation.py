import pytest
import numpy as np
import datetime as dt
from astropy.time import Time, TimeDelta

from oem.components import State
from oem.interp import LagrangeStateInterpolator, HermiteStateInterpolator


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
    "Interpolator", (LagrangeStateInterpolator, HermiteStateInterpolator)
)
def test_interpolators(Interpolator, has_accel):
    position = np.poly1d([1, 1, 1])
    velocity = position.deriv()
    acceleration = velocity.deriv()
    count = 7
    time_step = 60

    states = _make_test_states(position, time_step, count, accel=has_accel)
    interpolator = Interpolator(states)

    for elapsed in np.arange(0, count*time_step, 1):
        test_epoch = states[0].epoch + TimeDelta(elapsed, format="sec")
        predicted = interpolator(test_epoch)
        assert np.allclose(predicted.position, position(elapsed))
        assert np.allclose(predicted.velocity, velocity(elapsed))
        if has_accel:
            assert np.allclose(predicted.acceleration, acceleration(elapsed))
