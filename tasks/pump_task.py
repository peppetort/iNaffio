import logging
import json
import time

from RPi import GPIO

logging.basicConfig(level=logging.INFO)
CONFIG_FILE = "configs.json"

class PumpTask:
    def __init__(self, pump_quque, alarm_queue):
        self._tag = "PUMP_TASK"
        self.pump_quque = pump_quque
        self.alarm_queue = alarm_queue

        self.activity_seconds = 0
        self.gpio_pin = None

    def _water(self):
        if self.gpio_pin is None:
            return

        try:
            logging.info(f"[{self._tag}]: activating pump")
            GPIO.output(self.gpio_pin, GPIO.HIGH)
            time.sleep(self.activity_seconds)
            GPIO.output(self.gpio_pin, GPIO.LOW)
            logging.info(f"[{self._tag}]: deativating pump")
            # clear all messages in alarm queue
            while not self.alarm_queue.empty():
                self.alarm_queue.get()
            logging.info(f"[{self._tag}]: alarms cleared")
        except Exception as e:
            logging.error(f"[{self._tag}]: error while activating pump: {e}")
            # set GPIO to default state
            GPIO.output(self.gpio_pin, GPIO.LOW)



    def _load_configs(self):
        with open(CONFIG_FILE, "r") as f:
            configs = json.load(f)
            section = self._tag.lower()

            if section not in configs:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return

            if "activity_seconds" not in configs[section]:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return
            if "gpio_pin" not in configs[section]:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return


            self.activity_seconds = configs[section]["activity_seconds"]
            self.gpio_pin = configs[section]["gpio_pin"]

            if self.gpio_pin is not None:
                GPIO.setmode(GPIO.BOARD)
                GPIO.setup(self.gpio_pin, GPIO.OUT, initial=GPIO.LOW)


            logging.info(
                f"[{self._tag}]: config loaded\n\tactivity_seconds: {self.activity_seconds}\n\tgpio_pin: {self.gpio_pin}"
            )

    def run(self):
        try:
            logging.info(f"[{self._tag}]: started")
            self._load_configs()

            while True:
                if self.pump_quque.empty():
                    time.sleep(1)
                    continue

                if not self.pump_quque.empty():
                    self._water()
                    self.pump_quque.get()
        except Exception as e:
                GPIO.setup(self.gpio_pin, GPIO.OUT, initial=GPIO.LOW)
        
        GPIO.cleanup()