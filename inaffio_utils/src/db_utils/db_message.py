from enum import Enum

class DBAction(Enum):
    ADD = 100
    CLEAN = 200

class DBMessage:
    def __init__(self, action, **kwargs):
        self.action = action
        
        # check if payload is present
        if "payload" in kwargs:
            self.payload = kwargs["payload"]
        else:
            self.payload = None