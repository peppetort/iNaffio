from enum import Enum

class DBAction(Enum):
    ADD = 1
    QUERY = 2
    CLEAN = 3


class DBMessage:
    def __init__(self, action, **kwargs):
        self.action = action