import re

from oem.components import (
    HeaderSection, MetaDataSection, State, DataSection, EphemerisSegment
)
from oem import OrbitEphemerisMessage
from oem.components.types import _bulk_generate_states
from oem.patterns import KEY_VAL, DATA_LINE, COVARIANCE_LINE


class InvalidFormatError(Exception):
    pass


class KvnParser(object):

    def __init__(self):
        self._state = "HEADER"
        self._component_cache = []
        self._segment_cache = []
        self._section_cache = {}
        self._regex = {
            "KEY_VAL": re.compile(KEY_VAL),
            "DATA_LINE": re.compile(DATA_LINE),
            "COVARIANCE_LINE": re.compile(COVARIANCE_LINE),
        }

    def parse(self, stream):
        for line in stream:
            stripped_line = line.strip()
            if stripped_line and not line.startswith("COMMENT"):
                self._parser(stripped_line)
        return self._end_file()

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        self._state = new_state
        self._end_section()

    @property
    def _parser(self):
        if self.state == "HEADER":
            parser = self._parse_header_line
        elif self.state == "METADATA":
            parser = self._parse_metadata_line
        elif self.state == "DATA":
            parser = self._parse_data_line
        elif self.state == "COVARIANCE":
            parser = self._parse_covariance_line
        else:
            raise ValueError(f"Unknown state: {self.state}")
        return parser

    def _parse_header_line(self, line):
        match = self._regex["KEY_VAL"].match(line)
        if match:
            self._section_cache[match.group(1)] = match.group(2)
        elif "META_START" in line:
            self._component_cache.append(HeaderSection(self._section_cache))
            self.state = "METADATA"
            self._parser(line)
        else:
            self._raise()

    def _parse_metadata_line(self, line):
        if "META_START" in line:
            pass
        elif "META_STOP" in line:
            self._segment_cache.append(
                MetaDataSection(
                    self._section_cache, self._component_cache[0].version
                )
            )
            self.state = "DATA"
        else:
            match = self._regex["KEY_VAL"].match(line)
            if match:
                self._section_cache[match.group(1)] = match.group(2)
            else:
                self._raise()

    def _parse_data_line(self, line):
        finish = False
        match = self._regex["DATA_LINE"].match(line)
        if match:
            self._section_cache.setdefault("DATA", []).append(line)
        elif "COVARIANCE_START" in line:
            finish = True
            new_state = "COVARIANCE"
        elif "METADATA_START" in line:
            finish = True
            new_state = "METADATA"
        elif line == "END OF FILE":
            finish = True
            new_state = "SUCCESS"
        else:
            self._raise()

        if finish:
            states = _bulk_generate_states(
                self._section_cache["DATA"],
                self._segment_cache[0],
                self._component_cache[0].version
            )
            self._segment_cache.append(
                DataSection(
                    states,
                    self._component_cache[0].version,
                    _check=False
                )
            )
            self.state = new_state

    def _parse_covariance_line(self, line):
        finish = False
        if self._section_cache.get("SUBSTATE", "HEADER") == "HEADER":
            match = self._regex["KEY_VAL"].match(line)
            if match:
                self._section_cache.setdefault("DATA", []).append(line)
            else:
                if len(self._section_cache.get("DATA", [])) >= 1:
                    self._section_cache["SUBSTATE"] = "DATA"
                    return self._parse_covariance_line(line)
                else:
                    self._raise()

        elif self._section_cache.get("SUBSTATE", "HEADER") == "DATA":
            match = self._regex["COVARIANCE_LINE"].match(line)
            if match:
                self._section_cache["DATA"].append(line)
            else:
                match = self._regex["KEY_VAL"].match(line)
                if match:
                    self._section_cache["SUBSTATE"] = "HEADER"
                    return self._parse_covariance_line(line)
                elif "METADATA_START" in line:
                    finish = True
                    new_state = "METADATA"
                elif "END OF FILE" in line:
                    finish = True
                    new_state = "SUCCESS"
                else:
                    self._raise()

        if finish:
            pass
            # make covs
            self.state = new_state

    def _end_section(self):
        self._section_cache = {}

    def _end_segment(self):
        covariance_data = None
        if len(self._segment_cache) == 3:
            covariance_data = self._segment_cache[2]
        self._component_cache.append(
            EphemerisSegment(
                metadata=self._segment_cache[0],
                state_data=self._segment_cache[1],
                covariance_data=covariance_data,
                version=self._component_cache[0].version
            )
        )
        self._segment_cache = []

    def _end_file(self):
        self._parser("END OF FILE")
        self._end_segment()
        return OrbitEphemerisMessage(
            self._component_cache[0],
            self._component_cache[1:]
        )

    def _raise(self):
        raise InvalidFormatError("")
