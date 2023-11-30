"""Base classes"""


class HeaderField(object):
    """Base header field specification.

    Base class for OEM Key-Value field specifications.

    Attributes:
        parser (func): Function with a single input that returns a parsed
            version of the raw header value.
        required (bool): Indication of whether or not this field is required.
    """

    def __init__(self, parser, formatter, required=False):
        self.parser = parser
        self.formatter = formatter
        self.required = required


class KeyValueSection(object):
    """Base key-value section.

    Base class for OEM Key-Value based sections.
    """

    _field_spec = {}

    def _validate_fields(self, fields):
        for key in self.required_keys:
            if key not in fields:
                raise KeyError(f"Missing required header: {key}")
        for key in fields:
            if key not in self._field_spec:
                raise KeyError(f"Invalid header key: {key}")

    def _parse_fields(self, fields):
        self._validate_fields(fields)
        self._fields = fields

    def _format_fields(self):
        return [f"{key} = {value}" for key, value in self._fields.items()]

    def __getitem__(self, key):
        return self._field_spec[key].parser(self._fields[key], self)

    def __setitem__(self, key, value):
        if key in self._field_spec:
            self._fields[key] = value
        else:
            raise ValueError(f"Invalid key: '{key}'")

    def __contains__(self, key):
        return key in self._fields

    def __iter__(self):
        return iter(self._fields)

    def items(self):
        return [(key, self[key]) for key in self]

    @property
    def required_keys(self):
        """Return list of keys required by this section."""
        return [
            key for key, header_spec in self._field_spec.items() if header_spec.required
        ]


class Constraint(object):
    """Base constraint type."""

    def apply(self, obj):
        """Apply constraint.

        Args:
            obj: Constrained object
        """
        if obj.version in self.versions or self.versions == ["*"]:
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
