import datetime
import json
import queue
import sched
import smbus
import time
import logging

from db_utils.db_message import DBMessage, DBAction

logging.basicConfig(level=logging.INFO)

CONFIG_FILE = "../configs.json"

class SensorTask:

    def __init__(self, alarm_queue, db_queue):
        self._tag = "SENSOR_TASK"
        self.alarm_queue = alarm_queue
        self.db_queue = db_queue
        self.bus = smbus.SMBus(1)

        # default configs
        # will be overwritten by configs.json if exists
        self.sample_rate_seconds = 60

    def _read_measurement(self) -> (float, float):
        # import random
        # return random.randint(0, 100), random.randint(0, 100)

        try:
            self.bus.write_i2c_block_data(0x44, 0x2C, [0x06])

            time.sleep(0.5)

            # Read data from sensor
            data = self.bus.read_i2c_block_data(0x44, 0x00, 6)   

            c_temp = ((((data[0] * 256.0) + data[1]) * 175) / 65535.0) - 45
            humidity = 100 * (data[3] * 256 + data[4]) / 65535.0

            return c_temp, humidity
        except Exception as e:
            logging.error(f"[{self._tag}]: {e}")
            return None, None

    def _load_configs(self):
        with open(CONFIG_FILE, "r") as f:
            configs = json.load(f)
            section = self._tag.lower()

            if section not in configs:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return

            if "sampling_rate_seconds" not in configs[section]:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return
            
            self.sample_rate_seconds = configs[section]["sampling_rate_seconds"]

            logging.info(f"[{self._tag}]: config loaded\n\tsample_rate_seconds: {self.sample_rate_seconds}")
            
    def _scheduler_task(self):
        c_temp, humidity = self._read_measurement()

        if c_temp is None or humidity is None:
            return

        logging.info(f"[{self._tag}]: c_temp: {c_temp}, humidity: {humidity}")

        payload = {
            "time": datetime.datetime.now().timestamp(),
            "measures": {
                "temperature": c_temp,
                "humidity": humidity
            }
        }

        message = DBMessage( DBAction.ADD, payload=payload)
        self.db_queue.put(message)

        # reschedule
        self.scheduler.enter(self.sample_rate_seconds, 1, self._scheduler_task)



    def run(self):
        logging.info(f"[{self._tag}]: started")
        self._load_configs()

        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler.enter(self.sample_rate_seconds, 1, self._scheduler_task)
        self.scheduler.run()



if __name__ == "__main__":
    alarm_queue = queue.Queue()
    db_queue = queue.Queue()
    sensor_task = SensorTask(alarm_queue, db_queue)
    sensor_task.run()

