import datetime
import logging
import queue

from enum import Enum
import time
from tinydb import TinyDB, Query
from db_utils.db_message import DBMessage, DBAction

logging.basicConfig(level=logging.INFO)

DB_FILE = "../telemetry.json"

class QueryType(Enum):
    LATEST = 1
    LAST_HOUR = 2
    LAST_DAY = 3


class DBTask:
    def __init__(self, db_queue):
        self._tag = "DB_TASK"
        self.db_queue = db_queue

        self.db = TinyDB(DB_FILE)

        self._can_touch_db = True

    def _handle_add(self, payload):
        self.db.insert(payload)

    def query(self, type: QueryType):
        self._can_touch_db = False
        if type == QueryType.LATEST:
            logging.info(f"[{self._tag}]: getting latest telemetry")
            # get latest telemetry
            res = self.db.all()

            if len(res) == 0:
                logging.warning(f"[{self._tag}]: no telemetry found")
                self._can_touch_db = True
                return None

            self._can_touch_db = True
            return res[-1]
        
        if type == QueryType.LAST_HOUR:
            logging.info(f"[{self._tag}]: getting last hour telemetry")
            last_hour_ts = (datetime.datetime.now() - datetime.timedelta(hours=1)).timestamp()

            res = self.db.search(Query().timestamp > last_hour_ts)

            if len(res) == 0:
                logging.warning(f"[{self._tag}]: no telemetry found")
                self._can_touch_db = True
                return None
            
            self._can_touch_db = True
            return res
        
        if type == QueryType.LAST_DAY:
            logging.info(f"[{self._tag}]: getting last day telemetry")
            last_day_ts = (datetime.datetime.now() - datetime.timedelta(days=1)).timestamp()

            res = self.db.search(Query().timestamp > last_day_ts)

            if len(res) == 0:
                logging.warning(f"[{self._tag}]: no telemetry found")
                self._can_touch_db = True
                return None
            
            self._can_touch_db = True
            return res
        
    def _handle_clean(self):
        logging.info(f"[{self._tag}]: cleaning db")
        # remove all data from db
        self.db.purge()

    def run(self):
        logging.info(f"[{self._tag}]: started")

        while True:
            if not self._can_touch_db or self.db_queue.empty():
                time.sleep(1)
                continue

            message = self.db_queue.get()

            if message.action == DBAction.ADD:
                self._can_touch_db = False
                self._handle_add(message.payload)
                self._can_touch_db = True
            elif message.action == DBAction.CLEAN:
                self._can_touch_db = False
                self._handle_clean()
                self._can_touch_db = True
            else:
                logging.error(f"[{self._tag}]: unknown action {message.action}")