import re

import numpy as np
from lxml.etree import SubElement

from oem import patterns, CURRENT_VERSION
from oem.tools import parse_epoch, require, format_float, format_epoch
from oem.base import ConstraintSpecification, Constraint


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
    "CZ_DOT_Z_DOT": (5, 5)
}


class ConstrainStateType(Constraint):

    versions = ["1.0"]

    def func(self, state):
        require(
            state.acceleration is None,
            "State in v1.0 OEM cannot have acceleration entries"
        )


class ConstrainStateDimension(Constraint):

    versions = ["1.0", "2.0"]

    def func(self, state):
        require(state.position.size == 3, "State position size != 3")
        require(state.velocity.size == 3, "State velocity size != 3")
        if state.acceleration is not None:
            require(
                state.acceleration.size == 3,
                "State acceleration size != 3"
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
        ConstrainStateType,
        ConstrainStateDimension
    )

    def __init__(self, epoch, position, velocity, acceleration=None,
                 version=CURRENT_VERSION):
        self.version = version
        self.epoch = epoch
        self.position = np.array(position)
        self.velocity = np.array(velocity)
        self.acceleration = (
            np.array(acceleration)
            if acceleration is not None else None
        )
        self._constraint_spec.apply(self)

    def __eq__(self, other):
        return (
            self.version == other.version and
            self.epoch == other.epoch and
            (self.position == other.position).all() and
            (self.velocity == other.velocity).all() and
            np.array([self.acceleration == other.acceleration]).all()
        )

    @classmethod
    def _from_string(cls, segment, version, metadata):
        """Create State from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM state line.

        Returns:
            new_state (State): New State instance.
        """
        raw_state = segment.split()
        has_accel = True if len(raw_state) == 10 else False

        epoch = parse_epoch(raw_state[0], metadata)
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
    def _from_xml(cls, segment, version, metadata):
        epoch = parse_epoch(segment[0].text, metadata)
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

    def _to_xml(self, parent):
        SubElement(parent, "EPOCH").text = format_epoch(self.epoch)
        SubElement(parent, "X").text = format_float(self.position[0])
        SubElement(parent, "Y").text = format_float(self.position[1])
        SubElement(parent, "Z").text = format_float(self.position[2])
        SubElement(parent, "X_DOT").text = format_float(self.velocity[0])
        SubElement(parent, "Y_DOT").text = format_float(self.velocity[1])
        SubElement(parent, "Z_DOT").text = format_float(self.velocity[2])
        if self.has_accel:
            SubElement(parent, "X_DDOT").text = (
                format_float(self.acceleration[0]))
            SubElement(parent, "Y_DDOT").text = (
                format_float(self.acceleration[1]))
            SubElement(parent, "Z_DDOT").text = (
                format_float(self.acceleration[2]))

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

    def __eq__(self, other):
        return (
            self.version == other.version and
            self.epoch == other.epoch and
            self.frame == other.frame and
            (self.matrix == other.matrix).all()
        )

    @classmethod
    def _from_string(cls, segment, version, metadata):
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
            epoch = parse_epoch(headers["EPOCH"], metadata)
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
    def _from_xml(cls, segment, version, metadata):
        parts = [entry for entry in segment if entry.tag != "COMMENT"]
        entries = {entry.tag: entry.text for entry in parts}
        if "EPOCH" not in entries:
            raise ValueError("Covariance entry missing keyword 'EPOCH'")
        else:
            epoch = parse_epoch(entries["EPOCH"], metadata)
        frame = entries.get("COV_REF_FRAME")

        matrix = np.zeros((6, 6))
        for key, index in COV_XML_ENTRY_MAP.items():
            matrix[index] = float(entries[key])
            if index[0] != index[1]:
                matrix[index[::-1]] = float(entries[key])

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

    def _to_xml(self, parent):
        SubElement(parent, "EPOCH").text = format_epoch(self.epoch)
        if self.frame:
            SubElement(parent, "COV_REF_FRAME").text = self.frame
        for key, index in COV_XML_ENTRY_MAP.items():
            SubElement(parent, key).text = format_float(self.matrix[index])
