import datetime
from io import BytesIO
import json
import os
import sched
import threading
import time
from matplotlib import dates
import telebot
import logging
import matplotlib.pyplot as plt
import matplotlib

from tinydb import TinyDB, Query
from dotenv import load_dotenv
from message_utils.bot_messages import *

logging.basicConfig(level=logging.INFO)
load_dotenv(".env")

matplotlib.pyplot.switch_backend("Agg")

TOKEN = os.getenv("TOKEN")
DB_FILE = "telemetry.json"
CONFIG_FILE = "configs.json"


class BotTask:
    def __init__(self, alarm_queue, pump_queue):
        self._tag = "BOT_TASK"
        self.bot = telebot.TeleBot(TOKEN)
        self.db = TinyDB(DB_FILE)

        self.alarm_queue = alarm_queue
        self.pump_queue = pump_queue
        self.alarm_notification_period = 60 * 10
        self.allowed_users = {}

        # define bindings for commands
        @self.bot.message_handler(commands=["start"])
        def _process_command_start(message):
            self._handle_command_start(message)

        @self.bot.message_handler(commands=["telemetry"])
        def _process_command_telemetry(message):
            self._handle_command_telemetry(message)

        @self.bot.message_handler(commands=["water"])
        def _process_command_water(message):
            self._handle_command_water(message)

        @self.bot.callback_query_handler(func=lambda call: True)
        def _process_callback_query(call):
            self._handle_callback_query(call)

        @self.bot.message_handler(commands=["alarms"])
        def _process_command_alarm(message):
            self._handle_command_alarm(message)

        @self.bot.message_handler(commands=["alarms_off"])
        def _process_command_remove_alarms(message):
            self._handle_command_remove_alarms(message)

        @self.bot.message_handler(commands=["stats"])
        def _process_command_stats(message):
            self._handle_command_stats(message)

    def _generate_plot(self, res, bio):
        _, (ax1, ax2) = plt.subplots(2, 1)

        x = [datetime.datetime.fromtimestamp(r["time"]) for r in res]
        y1 = [r["measures"]["temperature"] for r in res]
        y2 = [r["measures"]["humidity"] for r in res]

        ax1.plot(x, y1, "-o", color="orange")
        ax1.set_ylabel("Temperature [°C]")

        ax2.plot(x, y2, "-o", color="blue")
        ax2.set_ylabel("Humidity [%]")
        ax2.set_xlabel("Time")

        # add grid
        ax1.grid()
        ax2.grid()

        # remove seconds from x axis
        ax1.xaxis.set_major_formatter(dates.DateFormatter("%H:%M"))
        ax2.xaxis.set_major_formatter(dates.DateFormatter("%H:%M"))

        # set scale
        ax2.set_ylim([0, 100])

        plt.savefig(bio, format="png")
        bio.seek(0)
        plt.close()

        return bio

    def _handle_command_stats(self, message):
        if not self._check_user(message):
            return

        # get telemetry of last 24 hours
        res = self.db.search(
            Query().time
            > (datetime.datetime.now() - datetime.timedelta(hours=24)).timestamp()
        )

        if len(res) == 0:
            self.bot.send_message(message.chat.id, "No telemetry found \U0001F622")
            return

        with BytesIO() as bio:
            bio = self._generate_plot(res, bio)
            self.bot.send_photo(message.chat.id, bio)

    def _handle_command_remove_alarms(self, message):
        if not self._check_user(message):
            return

        # send confirmation message with two buttons
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton(
                "Yes", callback_data="remove_alarms_yes"
            ),
            telebot.types.InlineKeyboardButton("No", callback_data="remove_alarms_no"),
        )
        self.bot.send_message(
            message.chat.id,
            "Are you sure to turn off all alarms?",
            reply_markup=markup,
        )

    def _handle_command_alarm(self, message):
        if not self._check_user(message):
            return

        if len(self.alarm_queue.queue) == 0:
            self.bot.send_message(message.chat.id, "No alarms found ")
            return

        for alarm in self.alarm_queue.queue:
            ts = alarm["time"]
            date = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
            time = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            temperature = alarm["measures"]["temperature"]
            humidity = alarm["measures"]["humidity"]

            self.bot.send_message(
                message.chat.id,
                ALARM_MESSAGE.format(
                    temperature=temperature, humidity=humidity, time=time, date=date
                ),
            )

    def _handle_command_water(self, message):
        if not self._check_user(message):
            return

        # send confirmation message with two buttons
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("Yes", callback_data="water_yes"),
            telebot.types.InlineKeyboardButton("No", callback_data="water_no"),
        )
        self.bot.send_message(
            message.chat.id,
            "Do you want to water the Bonsai?",
            reply_markup=markup,
        )

    def _handle_callback_query(self, call):
        if call.data == "water_yes":
            self.bot.send_message(call.message.chat.id, "I will water the Bonsai")
            self.pump_queue.put(True)
        elif call.data == "water_no":
            self.bot.send_message(
                call.message.chat.id, "Ok, I will not water the Bonsai"
            )
        elif call.data == "remove_alarms_yes":
            self.bot.send_message(
                call.message.chat.id, "Ok, I will turn off all alarms"
            )
            self.alarm_queue.queue.clear()
        elif call.data == "remove_alarms_no":
            self.bot.send_message(
                call.message.chat.id, "Ok, I will not turn off all alarms"
            )
        else:
            self.bot.send_message(call.message.chat.id, "Unknown command")

    def _check_user(self, message):
        user = message.from_user.username

        if user is None:
            self.bot.send_message(
                message.chat.id, "You need to set a username to use this bot"
            )
            return False

        if user not in self.allowed_users.keys():
            self.bot.send_message(
                message.chat.id, "You are not allowed to use this bot"
            )
            return False

        self.allowed_users[user] = message.chat.id
        return True

    def _handle_command_start(self, message):
        if not self._check_user(message):
            return

        self.bot.send_message(message.chat.id, "Welcome! I am monitoring your Bonsai")

    def _handle_command_telemetry(self, message):
        if not self._check_user(message):
            return

        res = self.db.all()

        if len(res) == 0:
            self.bot.send_message(message.chat.id, "No telemetry found \U0001F622")
            return

        res = res[-1]

        ts = res["time"]
        dt = datetime.datetime.fromtimestamp(ts) + datetime.timedelta(hours=1)
        date = dt.strftime("%d/%m/%Y")
        time = dt.strftime("%H:%M:%S")
        temperature = res["measures"]["temperature"]
        humidity = res["measures"]["humidity"]

        temperature = round(temperature, 2)
        humidity = round(humidity, 2)

        # send latest telemetry
        self.bot.send_message(
            message.chat.id,
            LATEST_TELEMETRY_MESSAGE.format(
                temperature=temperature, humidity=humidity, time=time, date=date
            ),
        )

    def _scheduler_task(self):
        if not self.alarm_queue.empty():
            alarm = self.alarm_queue.queue[0]
            logging.info(f"[{self._tag}]: sending alarm message")

            ts = alarm["time"]
            date = datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
            time = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            temperature = alarm["measures"]["temperature"]
            humidity = alarm["measures"]["humidity"]

            for chat_id in self.allowed_users.values():
                if chat_id is None:
                    logging.warning(f"[{self._tag}]: no chat_id found, skipping")
                    continue
                self.bot.send_message(
                    chat_id,
                    ALARM_MESSAGE.format(
                        temperature=temperature, humidity=humidity, time=time, date=date
                    ),
                )

        self.scheduler.enter(self.alarm_notification_period, 1, self._scheduler_task)

    def _load_configs(self):
        with open(CONFIG_FILE, "r") as f:
            configs = json.load(f)
            section = self._tag.lower()

            if section not in configs:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return

            if "alarm_notification_period" not in configs[section]:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return

            if "allowed_users" not in configs[section]:
                logging.warning(f"[{self._tag}]: no configs found, using defaults")
                return

            self.alarm_notification_period = configs[section][
                "alarm_notification_period"
            ]
            for user in configs[section]["allowed_users"]:
                self.allowed_users[user] = None

            logging.info(
                f"[{self._tag}]: config loaded\n\talarm_notification_period: {self.alarm_notification_period}\n\tallowed_users: {self.allowed_users.keys()}"
            )

    def run(self):
        logging.info(f"[{self._tag}]: starting")
        self._load_configs()

        # creating a non blovking scheduler that will run _scheduler_task every 10 seconds in a separate thread
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self.scheduler.enter(5, 1, self._scheduler_task)
        scheduler_thread = threading.Thread(target=self.scheduler.run)
        scheduler_thread.start()

        while True:
            try:
                self.bot.polling()
            except Exception as e:
                print(e)
                logging.error(f"[{self._tag}]: error polling, retrying in 5 seconds")
                time.sleep(5)
                continue
