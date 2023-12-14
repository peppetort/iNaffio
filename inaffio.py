import queue
import threading

from tasks.sensor_task import SensorTask
from tasks.db_task import DBTask
from tasks.bot_task import BotTask

db_queue = queue.Queue()
alarm_queue = queue.Queue()
pump_queue = queue.Queue()


def main():
    db_task = DBTask(db_queue)
    sensor_task = SensorTask(alarm_queue, db_queue)
    bot_task = BotTask(alarm_queue, pump_queue)

    # start tasks in separate threads
    db_task_thread = threading.Thread(target=db_task.run)
    sensor_task_thread = threading.Thread(target=sensor_task.run)
    bot_task_thread = threading.Thread(target=bot_task.run)

    db_task_thread.start()
    sensor_task_thread.start()
    bot_task_thread.start()

    # wait for threads to finish
    db_task_thread.join()
    sensor_task_thread.join()
    bot_task_thread.join()
    



if __name__ == '__main__':
    main()