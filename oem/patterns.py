"""Regex patterns for parsing CCSDS ephemerides
"""


HS = r"(?:[ \t]|$)+"
"""Arbitrary Horizontal spacing or EOL"""

NL = r"(?:\n)+"
"""Arbitrary number of newlines"""

HSNL = r"(?:(?:[ \t]*\n)|[ \t]*$)+"
"""Arbitrary horizontal spacing and newlines"""

FLOAT = f"(?:[+-]?\\d\\.\\d+(?:[eE][+-]\\d{{1,3}})){HS}|[+-]?\\d+\\.\\d+"
"""Floating-point number"""

DATE = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?"
"""Date and time"""

KEY_VAL = f"([A-Z_]+){HS}={HS}(.+)"
"""Key-value pair"""

KEY_VAL_NC = f"[A-Z_]+{HS}={HS}.+"
"""Non-capturing key-value pair"""

DATA_LINE = f"{DATE}{HS}(?:(?:(?:{FLOAT}){HS}){{3}}){{2,3}}"
"""Ephemeris data line"""

COMMENT_LINE = r"COMMENT.+"
"""Comment line"""

COMMENT = f"(?:{COMMENT_LINE}{HSNL})+"
"""Single comment"""

HEADER_SEGMENT = (
    f"\\ACCSDS_OEM_VERS{HS}={HS}.+{HSNL}"
    f"(?:{COMMENT})?"
    f"(?:(?:{KEY_VAL_NC}{HSNL})+)"
)

METADATA_SEGMENT = (
    f"META_START{HSNL}"
    f"(?:{COMMENT})?"
    f"(?:{KEY_VAL_NC}{HSNL})+"
    f"META_STOP{HSNL}"
)

DATA_SEGMENT = (
    f"(?:{COMMENT})?"
    f"(?:{DATA_LINE}(?:{HSNL}|$))+"
)

COVARIANCE_MATRIX = "".join([
    f"(?:{FLOAT}{HS}){{{idx}}}{HSNL}"
    for idx in range(1, 7)
])

COVARIANCE_ENTRY = (
    f"(?:{KEY_VAL_NC}{HSNL}){{1,2}}"
    f"{COVARIANCE_MATRIX}"
)

COVARIANCE_SEGMENT = (
    f"COVARIANCE_START{HSNL}"
    f"(?:{COVARIANCE_ENTRY})+"
    f"COVARIANCE_STOP(?:{HSNL}|$)"
)

DATA_BLOCK = (
    f"({METADATA_SEGMENT})"
    f"({DATA_SEGMENT})"
    f"({COVARIANCE_SEGMENT})?"
)

CCSDS_EPHEMERIS = (
    f"({HEADER_SEGMENT})"
    f"(?:{DATA_BLOCK})+\\Z"
)
