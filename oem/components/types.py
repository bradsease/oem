import re
import numpy as np
from oem import patterns, CURRENT_VERSION
from oem.tools import parse_epoch, require
from oem.base import ConstraintSpecification, Constraint


class ConstrainStateSize(Constraint):

    versions = ["1.0"]

    def func(self, state):
        require(
            state.acceleration is None,
            "State in v1.0 OEM cannot have acceleration entries"
        )


class State(object):
    """Basic Cartesian state.

    Attributes:
        epoch (DateTime): Epoch date and time.
        position (ndarray): 3-element array describing the position at epoch.
        velocity (ndarray): 3-element array describing the velocity at epoch.
        acceleration (ndarray): 3-element array describing the acceleration
            at epoch. If unavailable, this attribute is None.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainStateSize
    )

    def __init__(self, epoch, position, velocity, acceleration=None,
                 version=CURRENT_VERSION):
        self.version = version
        self.epoch = epoch
        self.position = np.array(position)
        self.velocity = np.array(velocity)
        self.acceleration = (
            np.array(acceleration)
            if acceleration else None
        )
        self._constraint_spec.apply(self)

    @classmethod
    def from_string(cls, segment, version):
        """Create State from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM state line.

        Returns:
            new_state (State): New State instance.
        """
        raw_state = segment.split()
        has_accel = True if len(raw_state) == 10 else False

        epoch = parse_epoch(raw_state[0])
        position = [float(entry) for entry in raw_state[1:4]]
        velocity = [float(entry) for entry in raw_state[4:7]]
        if has_accel:
            acceleration = [float(entry) for entry in raw_state[7:]]
        else:
            acceleration = None

        return cls(
            epoch,
            position,
            velocity,
            acceleration=acceleration,
            version=version
        )


class Covariance(object):
    """Basic 6x6 covariance.

    Attributes:
        epoch (DateTime): Epoch date and time.
        frame (str): Reference from of this covariance.
        matrix (ndarray): 6x6 covariance matrix.
    """

    def __init__(self, epoch, frame, matrix, version=CURRENT_VERSION):
        self.version = version
        self.epoch = epoch
        self.frame = frame
        self.matrix = np.array(matrix)

    @classmethod
    def from_string(cls, segment, version):
        """Create Covariance from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM covariance block.

        Returns:
            new_covariance (Covariance): New Covariance instance.
        """
        headers = {
            entry[0]: entry[1].strip()
            for entry in re.findall(patterns.KEY_VAL, segment, re.MULTILINE)
        }
        if "EPOCH" not in headers:
            raise ValueError("Covariance entry missing keyword 'EPOCH'")
        else:
            epoch = parse_epoch(headers["EPOCH"])
        frame = headers.get("COV_REF_FRAME")

        raw_covariance = re.findall(
            patterns.COVARIANCE_MATRIX,
            segment,
            re.MULTILINE
        )[0]

        matrix = np.zeros((6, 6))
        covariance_lines = [
            entry for entry in raw_covariance.splitlines()
            if entry.strip()
        ]
        for row_idx, row in enumerate(covariance_lines):
            for col_idx, entry in enumerate(row.split()):
                matrix[row_idx, col_idx] = float(entry)
                matrix[col_idx, row_idx] = float(entry)

        return cls(epoch, frame, matrix, version=version)
