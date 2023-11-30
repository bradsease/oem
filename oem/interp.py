import numpy as np


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
    A = np.power(np.tile(x, (order + 1, 1)).T, np.arange(order + 1))
    a = np.linalg.solve(A, y)
    return np.poly1d(a[::-1])


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
    order = 2 * x.size - 1
    c = np.tile(x, (order + 1, 1)).T
    Au = np.power(c, np.arange(order + 1))
    Al = np.multiply(
        np.power(c, np.hstack(([1], np.arange(order)))),
        np.tile(np.hstack(([0, 1], np.arange(2, order + 1))), (x.size, 1)),
    )
    A = np.vstack((Au, Al))
    b = np.hstack((y, dy))
    a = np.linalg.solve(A, b)
    return np.poly1d(a[::-1])


class Interpolator(object):
    def __init__(self, states):
        self._reference_epoch = states[0][0]
        self._setup(states)

    def __call__(self, epoch):
        t = (epoch - self.reference_epoch).sec
        raw_state = np.array([poly(t) for poly in self._state_polynomials])
        position = raw_state[:3]
        velocity = raw_state[3:6]
        if len(raw_state) == 9:
            acceleration = raw_state[6:]
        else:
            acceleration = None
        return position, velocity, acceleration

    def _elapsed_times(self, states):
        reference = self.reference_epoch
        return np.array(tuple((epoch - reference).sec for epoch in states[0]))

    @property
    def reference_epoch(self):
        return self._reference_epoch


class LagrangeStateInterpolator(Interpolator):
    @classmethod
    def _samples_required(cls, order):
        count = order + 1
        if count % 1 != 0:
            raise ValueError("Unachievable order: {order}")
        else:
            return int(count)

    def _setup(self, states):
        t = self._elapsed_times(states)
        state_vectors = np.column_stack(states[1:])
        self._state_polynomials = [
            lagrange(t, state_vectors[:, idx]) for idx in range(state_vectors.shape[1])
        ]


class HermiteStateInterpolator(Interpolator):
    @classmethod
    def _samples_required(cls, order):
        count = (order + 1) / 2
        if count % 1 != 0:
            raise ValueError("Unachievable order: {order}")
        else:
            return int(count)

    def _setup(self, states):
        t = self._elapsed_times(states)
        state_vectors = np.column_stack(states[1:])
        self._state_polynomials = [
            hermite(t, state_vectors[:, idx], state_vectors[:, idx + 3])
            for idx in range(3)
        ]

        if state_vectors.shape[1] == 9:
            self._state_polynomials += [
                hermite(t, state_vectors[:, idx + 3], state_vectors[:, idx + 6])
                for idx in range(3)
            ]
            self._state_polynomials += [
                entry.deriv() for entry in self._state_polynomials[3:]
            ]

        else:
            self._state_polynomials += [
                entry.deriv() for entry in self._state_polynomials
            ]


class EphemerisInterpolator(object):
    method_map = {
        "lagrange": LagrangeStateInterpolator,
        "hermite": HermiteStateInterpolator,
    }

    def __init__(self, states, method, order):
        self.base_interpolator = self.method_map[method.lower()]
        self._states = states
        self._order = order
        self._populate_interpolator_nodes(states[0], order)

    def __call__(self, epoch):
        interpolator = self._get_best_interpolator(epoch)
        return interpolator(epoch)

    def _populate_interpolator_nodes(self, epochs, order):
        samples = self.base_interpolator._samples_required(order)
        elapsed_times = np.array(
            [(entry - self.reference_epoch).sec for entry in epochs]
        )
        self._nodes = np.array(
            [
                np.mean(elapsed_times[idx : (idx + samples)])
                for idx in range(len(elapsed_times) - samples + 1)
            ]
        )

    def _get_best_interpolator(self, epoch):
        elapsed_time = (epoch - self.reference_epoch).sec
        best_idx = np.argmin(np.abs(self._nodes - elapsed_time))
        samples = self.base_interpolator._samples_required(self.order)
        return self.base_interpolator(
            tuple(entry[best_idx : best_idx + samples] for entry in self._states)
        )

    @property
    def reference_epoch(self):
        return self._states[0][0]

    @property
    def order(self):
        return self._order
