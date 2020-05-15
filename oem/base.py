"""Base classes"""


class HeaderField(object):
    """Base header field specification.

    Base class for OEM Key-Value field specifications.

    Attributes:
        parser (func): Function with a single input that returns a parsed
            version of the raw header value.
        required (bool): Indication of whether or not this field is required.
    """

    def __init__(self, parser, required=False):
        self.parser = parser
        self.required = required


class KeyValueSection(object):
    """Base key-value section.

    Base class for OEM Key-Value based sections.
    """

    _field_spec = {}

    def _validate_fields(self, fields):
        """Validate section fields.

        Args:
            fields (dict): Unprocessed field data.
        """
        for key in self.required_keys:
            if key not in fields:
                raise KeyError(f"Missing required header: {key}")
        for key in fields:
            if key not in self._field_spec:
                raise KeyError(f"Invalid header key: {key}")

    def _parse_fields(self, fields):
        """Parse section fields.

        Args:
            fields (dict): Unprocessed field data.
        """
        self._validate_fields(fields)
        self._fields = {
            key: self._field_spec[key].parser(value)
            for key, value
            in fields.items()
        }

    def __getitem__(self, key):
        return self._fields[key]

    def __setitem__(self, key, value):
        if key in self._field_spec:
            self._fields[key] = value
        else:
            raise ValueError(f"Invalid key: '{key}'")

    def __contains__(self, key):
        return key in self._fields

    def __iter__(self):
        return iter(self._fields)

    @property
    def required_keys(self):
        """Return list of keys required by this section."""
        return [
            key for key, header_spec
            in self._field_spec.items()
            if header_spec.required
        ]


class Constraint(object):
    """Base constraint type."""

    def apply(self, obj):
        """Apply constraint.

        Args:
            obj: Constrained object
        """
        if obj.version in self.versions:
            self.func(obj)


class ConstraintSpecification(object):
    """Base constraint group type."""

    def __init__(self, *constraints):
        self.constraints = constraints

    def apply(self, obj):
        """Apply all constraints in specification.

        Args:
            obj: Constrained object
        """
        for constraint in self.constraints:
            constraint().apply(obj)
