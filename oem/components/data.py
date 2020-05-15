import re
from oem import patterns, CURRENT_VERSION
from oem.base import ConstraintSpecification, Constraint
from oem.tools import require
from oem.components.types import State


class ConstrainDataSectionEpochOrder(Constraint):
    """Apply constraints to data section state epochs."""

    versions = ["1.0", "2.0"]

    def func(self, data_section):
        require(
            all(
                (data_section.states[idx].epoch
                 < data_section.states[idx+1].epoch)
                for idx in range(len(data_section.states)-1)
            ),
            "States in data section are not ordered by epoch"
        )


class ConstrainDataSectionStates(Constraint):
    """Apply constraint to data section states."""

    versions = ["1.0", "2.0"]

    def func(self, data_section):
        for state in data_section:
            if (not data_section.has_accel
                    and state.acceleration is not None
                    or data_section.has_accel
                    and state.acceleration is None):
                raise ValueError("Cannot change state type mid-segment.")


class DataSection(object):
    """OEM data section.

    Container for a single OEM ephemeris state data section.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainDataSectionStates,
        ConstrainDataSectionEpochOrder
    )

    def __init__(self, states, version=CURRENT_VERSION):
        self.version = version
        self._has_accel = False if states[0].acceleration is None else True
        self._states = states
        self._constraint_spec.apply(self)

    def __iter__(self):
        return iter(self.states)

    @classmethod
    def from_string(cls, segment, version):
        """Create DataSection from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM data section.

        Returns:
            new_section (DataSection): New DataSection instance.
        """
        raw_states = re.findall(patterns.DATA_LINE, segment, re.MULTILINE)
        states = [State.from_string(entry, version) for entry in raw_states]
        return cls(states, version=version)

    @property
    def states(self):
        """Return a list of States in this section."""
        return self._states

    @property
    def has_accel(self):
        """Evaluate if section contains acceleration data."""
        return self._has_accel
