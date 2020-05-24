import re
from oem import patterns, CURRENT_VERSION
from oem.base import ConstraintSpecification, Constraint
from oem.tools import require
from oem.components.types import Covariance
from lxml.etree import SubElement


class ConstrainCovarianceSectionEpochOrder(Constraint):
    """Apply constraints to data section state epochs."""

    versions = ["1.0", "2.0"]

    def func(self, covariance_section):
        require(
            all(
                (covariance_section.covariances[idx].epoch
                 < covariance_section.covariances[idx+1].epoch)
                for idx in range(len(covariance_section.covariances)-1)
            ),
            "States in data section are not ordered by epoch"
        )


class CovarianceSection(object):
    """OEM covariance section.

    Container for a single OEM covariance section.
    """

    _constraint_spec = ConstraintSpecification(
        ConstrainCovarianceSectionEpochOrder
    )

    def __init__(self, covariances, version=CURRENT_VERSION):
        self.version = version
        self._covariances = covariances
        self._constraint_spec.apply(self)

    def __iter__(self):
        return iter(self.covariances)

    @classmethod
    def from_string(cls, segment, version):
        """Create CovarianceSection from OEM-formatted string.

        Args:
            segment (str): String containing a single OEM covariance section.

        Returns:
            new_section (CovarianceSection): New CovarianceSection instance.
        """
        raw_covariances = re.findall(
            patterns.COVARIANCE_ENTRY,
            segment,
            re.MULTILINE
        )
        covariances = [
            Covariance.from_string(entry, version)
            for entry in raw_covariances
        ]
        return cls(covariances, version=version)

    @classmethod
    def _from_xml(cls, segment, version=CURRENT_VERSION):
        covariances = [
            Covariance._from_xml(entry, version)
            for entry in segment
        ]
        return cls(covariances, version=version)

    def _to_string(self):
        lines = "COVARIANCE_START\n"
        lines += "\n".join(
            entry._to_string()
            for entry in self._covariances
        )
        lines += "COVARIANCE_STOP\n"
        return lines

    def _to_xml(self, parent):
        for entry in self._covariances:
            entry._to_xml(SubElement(parent, "covarianceMatrix"))

    @property
    def covariances(self):
        """Return a list of covariances in this section."""
        return self._covariances
