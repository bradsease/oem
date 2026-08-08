import numpy as np
from astropy.time import Time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type


def lagrange(x: np.ndarray, y: np.ndarray) -> np.poly1d:
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


class HermitePolynomial(object):
    """Hermite interpolating polynomial in Newton divided-difference form."""

    def __init__(self, x: np.ndarray, y: np.ndarray, dy: np.ndarray) -> None:
        count = 2 * x.size
        self._nodes = np.repeat(x, 2)
        table = np.zeros(
            (count, count, *y.shape[1:]), dtype=np.result_type(y, dy, float)
        )
        table[::2, 0] = y
        table[1::2, 0] = y
        table[1::2, 1] = dy

        rows = np.arange(2, count, 2)
        reshape = (-1,) + (1,) * (y.ndim - 1)
        table[rows, 1] = (y[1:] - y[:-1]) / np.diff(x).reshape(reshape)

        for column in range(2, count):
            rows = np.arange(column, count)
            denom = (self._nodes[rows] - self._nodes[rows - column]).reshape(reshape)
            table[rows, column] = (
                table[rows, column - 1] - table[rows - 1, column - 1]
            ) / denom

        diagonal = np.arange(count)
        self._coefficients = table[diagonal, diagonal]

    def __call__(self, x_eval: float) -> Tuple[Any, Any]:
        value = self._coefficients[-1].copy()
        derivative = np.zeros_like(value)

        for idx in range(self._coefficients.shape[0] - 2, -1, -1):
            delta = x_eval - self._nodes[idx]
            derivative = derivative * delta + value
            value = self._coefficients[idx] + value * delta

        return value, derivative


class Interpolator(object):
    _state_polynomials: List[np.poly1d]

    @classmethod
    def _samples_required(cls, order: int) -> int:
        raise NotImplementedError

    def __init__(self, states: Tuple[Sequence[Any], ...]) -> None:
        self._reference_epoch = states[0][0]
        self._setup(states)

    def __call__(
        self, epoch: Time
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        t = (epoch - self.reference_epoch).sec
        raw_state = np.array([poly(t) for poly in self._state_polynomials])
        position = raw_state[:3]
        velocity = raw_state[3:6]
        if len(raw_state) == 9:
            acceleration = raw_state[6:]
        else:
            acceleration = None
        return position, velocity, acceleration

    def _elapsed_times(self, states: Tuple[Sequence[Any], ...]) -> np.ndarray:
        reference = self.reference_epoch
        return np.array(tuple((epoch - reference).sec for epoch in states[0]))

    def _setup(self, states: Tuple[Sequence[Any], ...]) -> None:
        raise NotImplementedError

    @property
    def reference_epoch(self) -> Time:
        return self._reference_epoch


class LagrangeStateInterpolator(Interpolator):
    @classmethod
    def _samples_required(cls, order: int) -> int:
        count = order + 1
        if count % 1 != 0:
            raise ValueError("Unachievable order: {order}")
        else:
            return int(count)

    def _setup(self, states: Tuple[Sequence[Any], ...]) -> None:
        t = self._elapsed_times(states)
        state_vectors = np.column_stack(states[1:])
        self._state_polynomials = [
            lagrange(t, state_vectors[:, idx]) for idx in range(state_vectors.shape[1])
        ]


class HermiteStateInterpolator(Interpolator):
    @classmethod
    def _samples_required(cls, order: int) -> int:
        count = (order + 1) / 2
        if count % 1 != 0:
            raise ValueError("Unachievable order: {order}")
        else:
            return int(count)

    def _setup(self, states: Tuple[Sequence[Any], ...]) -> None:
        times = self._elapsed_times(states)
        state_vectors = np.column_stack(states[1:])
        self._has_accel = state_vectors.shape[1] == 9
        if self._has_accel:
            values = state_vectors[:, :6]
            derivatives = state_vectors[:, 3:]
        else:
            values = state_vectors[:, :3]
            derivatives = state_vectors[:, 3:]
        self._interpolator = HermitePolynomial(times, values, derivatives)

    def __call__(
        self, epoch: Time
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        t = (epoch - self.reference_epoch).sec
        values, derivatives = self._interpolator(t)
        position = values[:3]

        if self._has_accel:
            velocity = values[3:]
            acceleration = derivatives[3:]
        else:
            velocity = derivatives
            acceleration = None

        return position, velocity, acceleration


class EphemerisInterpolator(object):
    method_map: Dict[str, Type[Interpolator]] = {
        "lagrange": LagrangeStateInterpolator,
        "hermite": HermiteStateInterpolator,
    }

    def __init__(
        self, states: Tuple[Sequence[Any], ...], method: str, order: int
    ) -> None:
        self.base_interpolator = self.method_map[method.lower()]
        self._states = states
        self._order = order
        self._cached_interpolator: Optional[Tuple[int, Interpolator]] = None
        self._populate_interpolator_nodes(states[0], order)

    def __call__(
        self, epoch: Time
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        interpolator = self._get_best_interpolator(epoch)
        return interpolator(epoch)

    def _populate_interpolator_nodes(self, epochs: Sequence[Time], order: int) -> None:
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

    def _get_best_interpolator(self, epoch: Time) -> Interpolator:
        elapsed_time = (epoch - self.reference_epoch).sec
        best_idx = int(np.argmin(np.abs(self._nodes - elapsed_time)))
        cached = self._cached_interpolator
        if cached is None or best_idx != cached[0]:
            samples = self.base_interpolator._samples_required(self.order)
            interpolator = self.base_interpolator(
                tuple(entry[best_idx : best_idx + samples] for entry in self._states)
            )
            self._cached_interpolator = (best_idx, interpolator)
            return interpolator
        return cached[1]

    @property
    def reference_epoch(self) -> Time:
        return self._states[0][0]

    @property
    def order(self) -> int:
        return self._order
