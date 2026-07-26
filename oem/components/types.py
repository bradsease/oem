from typing import Any, Optional, Sequence, Union

import numpy as np
from astropy.time import Time

from oem import CURRENT_VERSION
from oem.base import Constraint, ConstraintSpecification
from oem.compare import StateCompare
from oem.tools import require

COV_XML_ENTRY_MAP = {
    "CX_X": (0, 0),
    "CY_X": (1, 0),
    "CZ_X": (2, 0),
    "CX_DOT_X": (3, 0),
    "CY_DOT_X": (4, 0),
    "CZ_DOT_X": (5, 0),
    "CY_Y": (1, 1),
    "CZ_Y": (2, 1),
    "CX_DOT_Y": (3, 1),
    "CY_DOT_Y": (4, 1),
    "CZ_DOT_Y": (5, 1),
    "CZ_Z": (2, 2),
    "CX_DOT_Z": (3, 2),
    "CY_DOT_Z": (4, 2),
    "CZ_DOT_Z": (5, 2),
    "CX_DOT_X_DOT": (3, 3),
    "CY_DOT_X_DOT": (4, 3),
    "CZ_DOT_X_DOT": (5, 3),
    "CY_DOT_Y_DOT": (4, 4),
    "CZ_DOT_Y_DOT": (5, 4),
    "CZ_DOT_Z_DOT": (5, 5),
}


class ConstrainStateType(Constraint):
    versions = ["1.0"]

    def func(self, state: "State") -> None:
        require(
            state.acceleration is None,
            "State in v1.0 OEM cannot have acceleration entries",
        )


class ConstrainStateDimension(Constraint):
    versions = ["*"]

    def func(self, state: "State") -> None:
        require(state.position.size == 3, "State position size != 3")
        require(state.velocity.size == 3, "State velocity size != 3")
        if state.acceleration is not None:
            require(state.acceleration.size == 3, "State acceleration size != 3")


class State(object):
    """Basic Cartesian state.

    Attributes:
        epoch (Time): Epoch date and time.
        frame (str): Reference frame.
        center (str): Central body.
        position (ndarray): 3-element array describing the position at epoch.
        velocity (ndarray): 3-element array describing the velocity at epoch.
        acceleration (ndarray): 3-element array describing the acceleration
            at epoch. If unavailable, this attribute is None.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainStateType, ConstrainStateDimension
    )

    def __init__(
        self,
        epoch: Time,
        frame: str,
        center: str,
        position: Sequence[float],
        velocity: Sequence[float],
        acceleration: Optional[Sequence[float]] = None,
        version: str = CURRENT_VERSION,
    ) -> None:
        self.version = version
        self.epoch = epoch
        self.frame = frame
        self.center = center
        self.position = np.array(position)
        self.velocity = np.array(velocity)
        self.acceleration: Optional[np.ndarray] = (
            np.array(acceleration) if acceleration is not None else None
        )
        self._constraint_spec.apply(self)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, State) and (
            self.version == other.version
            and self.epoch == other.epoch
            and (self.position == other.position).all()
            and (self.velocity == other.velocity).all()
            and np.array([self.acceleration == other.acceleration]).all()
        )

    def __sub__(self, other: "State") -> StateCompare:
        return StateCompare(other, self)

    def __repr__(self) -> str:
        return f"State({str(self.epoch)})"

    @classmethod
    def _from_raw_data(cls, data: Any, version: str, metadata: Any) -> "State":
        epoch, *state = data
        return cls(
            epoch,
            metadata["REF_FRAME"],
            metadata["CENTER_NAME"],
            state[:3],
            state[3:6],
            acceleration=state[6:] if len(state) == 9 else None,
            version=version,
        )

    def copy(self) -> "State":
        """Create an independent copy of this instance."""
        return State(
            self.epoch,
            self.frame,
            self.center,
            self.position.copy(),
            self.velocity.copy(),
            self.acceleration.copy() if self.acceleration is not None else None,
            version=self.version,
        )

    @property
    def has_accel(self) -> bool:
        return True if self.acceleration is not None else False

    @property
    def vector(self) -> np.ndarray:
        if self.has_accel:
            vec = np.hstack((self.position, self.velocity, self.acceleration))
        else:
            vec = np.hstack((self.position, self.velocity))
        return vec


class Covariance(object):
    """Basic 6x6 covariance.

    Attributes:
        epoch (Time): Epoch date and time.
        frame (str): Reference from of this covariance.
        matrix (ndarray): 6x6 covariance matrix.
    """

    def __init__(
        self,
        epoch: Time,
        frame: str,
        matrix: Union[np.ndarray, Sequence[Sequence[float]]],
        version: str = CURRENT_VERSION,
    ) -> None:
        self.version = version
        self.epoch = epoch
        self.frame = frame
        self.matrix = np.array(matrix)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Covariance) and (
            self.version == other.version
            and self.epoch == other.epoch
            and self.frame == other.frame
            and (self.matrix == other.matrix).all()
        )

    def __repr__(self) -> str:
        return f"Covariance({str(self.epoch)})"

    @classmethod
    def _from_raw_data(cls, data: Any, version: str) -> "Covariance":
        epoch, frame, *s = data
        matrix = np.array(
            (
                (s[0], s[1], s[3], s[6], s[10], s[15]),
                (s[1], s[2], s[4], s[7], s[11], s[16]),
                (s[3], s[4], s[5], s[8], s[12], s[17]),
                (s[6], s[7], s[8], s[9], s[13], s[18]),
                (s[10], s[11], s[12], s[13], s[14], s[19]),
                (s[15], s[16], s[17], s[18], s[19], s[20]),
            )
        )
        return cls(epoch, frame, matrix, version=version)

    def copy(self) -> "Covariance":
        """Create an independent copy of this instance."""
        return Covariance(
            self.epoch, self.frame, self.matrix.copy(), version=self.version
        )
