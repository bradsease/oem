import re
# from oem.parser.states import STATES


class FiniteStateMachineParser(object):

    def __init__(self, states, initial_state):
        '''Create a new parser.

        Args:
            states (dict):
            initial_state (str):
        '''
        self._states = states
        self._initial_state = initial_state
        self._state = initial_state

    def parse(self, stream, ignore_empty=True):
        '''Parse a text stream.

        Args:
            stream (list of str):

        returns:
            state_map (list of tuple): Collection of 3-tuple describing the
                states contained in the stream paired with start and end lines.
        '''
        last_state_change = 0
        state_map = []
        for idx, line in enumerate(stream):
            if line.strip() or not ignore_empty:
                observed_state = self._eval_line(idx, line)
                if observed_state != self.state:
                    state_map.append((self.state, last_state_change, idx-1))
                    last_state_change = idx
                    self._state = observed_state
        state_map.append((self.state, last_state_change, idx))
        return state_map

    def _eval_line(self, idx, line):
        for pattern in self.state_schema["valid_lines"]:
            if re.match(pattern, line):
                return self.state
        else:
            for future_state, pattern in self.state_schema["exit"].items():
                if re.match(pattern, line):
                    return future_state
            else:
                raise ValueError(f"Invalid transition on line {idx}: {line}")

    @property
    def states(self):
        return self._states

    @property
    def state(self):
        return self._state

    @property
    def state_schema(self):
        return self.states[self.state]
