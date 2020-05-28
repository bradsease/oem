import numpy as np
import datetime as dt
from astropy.time import Time

from oem.components import State
from oem import interp


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


def test_lagrange_interpolator():
    states = _make_test_states(np.poly1d([.1, .1, .1, .1]), 60, 7, accel=True)
    interpolator = interp.LagrangeStateInterpolator(states)
    for state in states:
        predicted = interpolator(state.epoch)
        assert np.allclose(state.position, predicted.position)
        assert np.allclose(state.velocity, predicted.velocity)
        assert np.allclose(state.acceleration, predicted.acceleration)
