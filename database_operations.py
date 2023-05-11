import sqlite3
from dataclasses import dataclass
from datetime import datetime

from user_event import UserEvent
from utils import get_logger, DEFAULT_TZ

log = get_logger()


@dataclass
class UserEvent:
    event_id: str
    user_id: int
    name: str
    date: datetime
    period: str


def create_necessary_tables_if_not_exist():
    with sqlite3.connect("bot_db.db") as connection:
        sql = "CREATE TABLE IF NOT EXISTS events (event_id str primary key, user_id INT, name str, date str, period str, is_active int)"
        cursor = connection.cursor()
        cursor.execute(sql)
        connection.commit()
        cursor.close()


def save_event(user_event: UserEvent):
    with sqlite3.connect("bot_db.db") as connection:
        sql = "INSERT INTO events (event_id, user_id, name, date, period, is_active) VALUES (?, ?, ?, ?, ?, ?)"
        cursor = connection.cursor()
        cursor.execute(sql, (user_event.event_id, user_event.user_id, user_event.name,
                             user_event.date.strftime("%d/%m/%Y %H:%M:%S"), user_event.period, 1))
        connection.commit()
        cursor.close()


def set_inactive(event_id: str):
    with sqlite3.connect("bot_db.db") as connection:
        cursor = connection.cursor()
        sql = "UPDATE events SET is_active = 0 WHERE event_id = ?"
        cursor.execute(sql, (event_id,))
        connection.commit()
        cursor.close()


def load_all_events() -> list[UserEvent]:
    events = []
    with sqlite3.connect("bot_db.db") as connection:
        cursor = connection.cursor()
        sql = "SELECT * FROM events WHERE is_active = 1"
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
    for row in rows:
        event_id, user_id, name, date_str, period, is_active = row
        date = datetime.strptime(date_str, "%d/%m/%Y %H:%M:%S")
        date = date.replace(tzinfo=DEFAULT_TZ)
        event = UserEvent(event_id, user_id, name, date, period)
        events.append(event)
        log.info(event)
    return events
