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
        np.arange(order + 1)
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
        np.hstack(([1], np.arange(order)))
    )
    A = np.vstack((Au, Al))
    b = np.hstack((y, dy))
    a = np.linalg.solve(A, b)[::-1]
    return np.poly1d(a)


class Interpolator(object):
    """Base interpolation type."""

    def __init__(self, states):
        self._start_time = states[0].epoch
        self._setup(states)

    def __call__(self, epoch):
        t = (epoch - self.start_time).sec
        raw_state = np.array([poly(t) for poly in self._state_polynomials])
        position = raw_state[:3]
        velocity = raw_state[3:6]
        if len(raw_state) == 9:
            acceleration = raw_state[6:]
        else:
            acceleration = None
        return State(epoch, position, velocity, acceleration=acceleration)

    def _elapsed_times(self, states):
        return np.array(
            [(entry.epoch - self.start_time).sec for entry in states]
        )

    @property
    def start_time(self):
        """Interpolator reference epoch."""
        return self._start_time


class LagrangeStateInterpolator(Interpolator):

    def _setup(self, states):
        t = self._elapsed_times(states)
        state_vectors = np.vstack((entry.vector for entry in states))
        self._state_polynomials = [
            lagrange(t, state_vectors[:, idx])
            for idx in range(state_vectors.shape[1])
        ]


class HermiteStateInterpolator(Interpolator):

    def _setup(self, states):
        t = self._elapsed_times(states)
        state_vectors = np.vstack((entry.vector for entry in states))
        self._state_polynomials = [
            hermite(t, state_vectors[:, idx], state_vectors[:, idx+3])
            for idx in range(3)
        ]

        if state_vectors.shape[1] == 9:
            self._state_polynomials += [
                hermite(t, state_vectors[:, idx+3], state_vectors[:, idx+6])
                for idx in range(3)
            ]
            self._state_polynomials += [
                entry.deriv() for entry in self._state_polynomials[3:]
            ]

        else:
            self._state_polynomials += [
                entry.deriv() for entry in self._state_polynomials
            ]


class EphemerisInterpolator(Interpolator):

    def __init__(self, times, states, order, method):
        pass
