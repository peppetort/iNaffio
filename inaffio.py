import queue
import signal
import threading

from tasks.sensor_task import SensorTask
from tasks.db_task import DBTask
from tasks.bot_task import BotTask
from tasks.pump_task import PumpTask

from RPi import GPIO

db_queue = queue.Queue()
alarm_queue = queue.Queue(maxsize=1)
pump_queue = queue.Queue(maxsize=1)


def main():
    GPIO.setmode(GPIO.BOARD)

    def hadle_sigterm(signum, frame):
        GPIO.cleanup()
        exit(0)

    signal.signal(signal.SIGTERM, hadle_sigterm)

    try:
        db_task = DBTask(db_queue)
        sensor_task = SensorTask(alarm_queue, db_queue)
        bot_task = BotTask(alarm_queue, pump_queue)
        pump_task = PumpTask(pump_queue, alarm_queue)

        # start tasks in separate threads
        db_task_thread = threading.Thread(target=db_task.run)
        sensor_task_thread = threading.Thread(target=sensor_task.run)
        bot_task_thread = threading.Thread(target=bot_task.run)
        pump_task_thread = threading.Thread(target=pump_task.run)

        db_task_thread.start()
        sensor_task_thread.start()
        bot_task_thread.start()
        pump_task_thread.start()

        # wait for threads to finish
        db_task_thread.join()
        sensor_task_thread.join()
        bot_task_thread.join()
        pump_task_thread.join()
    except KeyboardInterrupt:
        GPIO.cleanup()
    except Exception as e:
        GPIO.cleanup()



if __name__ == '__main__':
    main()