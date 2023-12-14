import logging

import time
from tinydb import TinyDB
from db_utils.db_message import DBAction

logging.basicConfig(level=logging.INFO)

DB_FILE = "telemetry.json"

class DBTask:
    def __init__(self, db_queue):
        self._tag = "DB_TASK"

        self.db_queue = db_queue


        self.db = TinyDB(DB_FILE)


    def _handle_add(self, payload):
        self.db.insert(payload)
        
    def _handle_clean(self):
        logging.info(f"[{self._tag}]: cleaning db")
        # remove all data from db
        self.db.purge()

    def run(self):
        logging.info(f"[{self._tag}]: started")

        while True:
            if self.db_queue.empty():
                time.sleep(1)
                continue

            message = self.db_queue.get()

            if message.action == DBAction.ADD:
                self._handle_add(message.payload)
            elif message.action == DBAction.CLEAN:
                self._handle_clean()
            else:
                logging.error(f"[{self._tag}]: unknown action {message.action}")