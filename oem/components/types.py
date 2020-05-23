import re
import numpy as np
from oem import patterns, CURRENT_VERSION
from oem.tools import parse_epoch, require, format_float, format_epoch
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

    @classmethod
    def _from_xml(cls, segment, version):
        epoch = parse_epoch(segment[0].text)
        position = [float(entry.text) for entry in segment[1:4]]
        velocity = [float(entry.text) for entry in segment[4:7]]
        if len(segment) == 10:
            acceleration = [float(entry.text) for entry in segment[7:]]
        else:
            acceleration = None
        return cls(
            epoch,
            position,
            velocity,
            acceleration=acceleration,
            version=version
        )

    def _to_string(self):
        entries = list(self.position) + list(self.velocity)
        if self.has_accel:
            entries += list(self.acceleration)
        formatted_epoch = format_epoch(self.epoch)
        formatted_entries = "  ".join(
            [format_float(entry) for entry in entries]
        )
        return f"{formatted_epoch}  {formatted_entries}\n"

    @property
    def has_accel(self):
        return True if self.acceleration is not None else False


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

    @classmethod
    def _from_xml(cls, segment, version):
        parts = [entry for entry in segment if entry.tag != "COMMENT"]
        entries = {entry.tag: entry.text for entry in parts}
        if "EPOCH" not in entries:
            raise ValueError("Covariance entry missing keyword 'EPOCH'")
        else:
            epoch = parse_epoch(entries["EPOCH"])
        frame = entries.get("COV_REF_FRAME")

        matrix = np.zeros((6, 6))
        matrix[1, 0] = float(entries["CY_X"])
        matrix[2, 0] = float(entries["CZ_X"])
        matrix[3, 0] = float(entries["CX_DOT_X"])
        matrix[4, 0] = float(entries["CY_DOT_X"])
        matrix[5, 0] = float(entries["CZ_DOT_X"])
        matrix[2, 1] = float(entries["CZ_Y"])
        matrix[3, 1] = float(entries["CX_DOT_Y"])
        matrix[4, 1] = float(entries["CY_DOT_Y"])
        matrix[5, 1] = float(entries["CZ_DOT_Y"])
        matrix[3, 2] = float(entries["CX_DOT_Z"])
        matrix[4, 2] = float(entries["CY_DOT_Z"])
        matrix[5, 2] = float(entries["CZ_DOT_Z"])
        matrix[4, 3] = float(entries["CY_DOT_X_DOT"])
        matrix[5, 3] = float(entries["CZ_DOT_X_DOT"])
        matrix[5, 4] = float(entries["CZ_DOT_Y_DOT"])
        matrix += matrix.T
        matrix += np.diag([
            float(entries["CX_X"]),
            float(entries["CY_Y"]),
            float(entries["CZ_Z"]),
            float(entries["CX_DOT_X_DOT"]),
            float(entries["CY_DOT_Y_DOT"]),
            float(entries["CZ_DOT_Z_DOT"])
        ])

        return cls(epoch, frame, matrix, version=version)

    def _to_string(self):
        lines = f"EPOCH = {format_epoch(self.epoch)}\n"
        if self.frame:
            lines += f"COV_REF_FRAME = {self.frame}\n"

        idx = 1
        for row in self.matrix:
            formatted_entries = [format_float(entry) for entry in row[:idx]]
            lines += "  ".join(formatted_entries) + "\n"
            idx += 1

        return lines
