import numpy as np

from oem.components import State


def lagrange(x, y):
    """Create a Lagrange interpolation polynomial.

    Create a Lagrange interpolation polynomial of order N-1 where N is the
    number of (x, y) coordinates provided.

    Args:
        x (ndarray): Interpolation point x values, length N.
        y (ndarray): Interpolation point y values, length N.

    Returns:
        poly (poly1d): Polynomial object called with poly(x).
    """
    order = x.size - 1
    A = np.power(
        np.tile(x, (order + 1, 1)).T,
        np.arange(0, order + 1)
    )
    a = np.linalg.solve(A, y)[::-1]
    return np.poly1d(a)


def hermite(x, y, dy):
    """Create a Hermite interpolation polynomial.

    Create a Hermite interpolation polynomial of order N-1 where N is the
    number of (x, y, dy) entries provided.

    Args:
        x (ndarray): Interpolation point x values, length N.
        y (ndarray): Interpolation point y values, length N.
        dy (ndarray): Interpolation point dy/dx values, length N.

    Returns:
        poly (poly1d): Polynomial object called with poly(x).
    """
    order = 2*x.size - 1
    tiled_x = np.tile(x, (order + 1, 1)).T
    Au = np.power(
        tiled_x,
        np.arange(order + 1)
    )
    Al = np.power(
        np.multiply(
            tiled_x,
            np.tile(np.arange(order+1), (x.size, 1))
        ),
        np.hstack((
            np.array([0]),
            np.arange(order)
        ))
    )
    A = np.vstack((Au, Al))
    b = np.hstack((y, dy))
    a = np.linalg.solve(A, b)[::-1]
    return np.poly1d(a)


class Interpolator(object):
    """Base interpolation type."""

    def __init__(self, states):
        self.states = states
        self._setup()

    def __call__(self, epoch):
        t = (epoch - self.epochs[0]).sec
        raw_state = np.array([poly(t) for poly in self._state_polynomials])
        position = raw_state[:3]
        velocity = raw_state[3:6]
        if self.has_accel:
            acceleration = raw_state[6:]
        else:
            acceleration = None
        return State(epoch, position, velocity, acceleration=acceleration)

    @property
    def epochs(self):
        return np.array([entry.epoch for entry in self.states])

    @property
    def elapsed_times(self):
        return np.array(
            [(entry - self.epochs[0]).sec for entry in self.epochs]
        )

    @property
    def has_accel(self):
        return self.states[0].has_accel

    def _get_positions(self):
        return (
            np.array([entry.position[idx] for entry in self.states])
            for idx in range(3)
        )

    def _get_velocities(self):
        return [
            np.array([entry.velocity[idx] for entry in self.states])
            for idx in range(3)
        ]

    def _get_accelerations(self):
        return [
            np.array([entry.acceleration[idx] for entry in self.states])
            for idx in range(3)
        ]


class LagrangeStateInterpolator(Interpolator):

    def _setup(self):
        t = self.elapsed_times
        self._state_polynomials = [
            *(lagrange(t, entry) for entry in self._get_positions()),
            *(lagrange(t, entry) for entry in self._get_velocities())
        ]
        if self.has_accel:
            self._state_polynomials += (
                lagrange(t, entry) for entry in self._get_accelerations()
            )


class HermiteStateInterpolator(Interpolator):
    pass


class EphemerisInterpolator(Interpolator):

    def __init__(self, times, states, order, method):
        pass
