from oem.patterns import HS, FLOAT, KEY_VAL_NC, DATA_LINE


STATES = {
    "HEADER": {
        "valid_lines": [
            KEY_VAL_NC,
        ],
        "exit": {
            "START_METADATA": f"META_START{HS}",
        },
    },

    "START_METADATA": {
        "valid_lines": [],
        "exit": {
            "METADATA": KEY_VAL_NC,
        },
    },

    "METADATA": {
        "valid_lines": [
            KEY_VAL_NC
        ],
        "exit": {
            "STOP_METADATA": f"META_STOP{HS}",
        },
    },

    "STOP_METADATA": {
        "valid_lines": [],
        "exit": {
            "DATA": DATA_LINE,
        },
    },

    "DATA": {
        "valid_lines": [
            DATA_LINE
        ],
        "exit": {
            "METADATA": f"META_START{HS}",
            "START_COVARIANCE": f"COVARIANCE_START{HS}",
        },
    },

    "START_COVARIANCE": {
        "valid_lines": [],
        "exit": {
            "COVARIANCE_HEADER": KEY_VAL_NC,
        },
    },

    "COVARIANCE_HEADER": {
        "valid_lines": [
            KEY_VAL_NC
        ],
        "exit": {
            "COVARIANCE_MATRIX": f"{FLOAT}{HS}",
        },
    },

    "COVARIANCE_MATRIX": {
        "valid_lines": [
            f"(?:{FLOAT}{HS}){{1,6}}"
        ],
        "exit": {
            "COVARIANCE_HEADER": KEY_VAL_NC,
            "STOP_COVARIANCE": f"COVARIANCE_STOP{HS}"
        },
    },

    "STOP_COVARIANCE": {
        "valid_lines": [],
        "exit": {
            "START_METADATA": f"META_START{HS}",
        },
    },

}
