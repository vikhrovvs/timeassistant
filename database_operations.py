import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from user_event import UserEvent, create_event_from_row
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
        event = create_event_from_row(row)
        events.append(event)
        log.info(event)
    return events


def load_event(event_id: str) -> Optional[UserEvent]:
    with sqlite3.connect("bot_db.db") as connection:
        cursor = connection.cursor()
        sql = "SELECT * FROM events WHERE event_id = ? LIMIT 1"
        cursor.execute(sql, (event_id, ))
        rows = cursor.fetchall()
        cursor.close()
    log.info(f"Loaded {len(rows)} rows")
    if len(rows) == 0:
        log.error("No event found")
        return None
    row = rows[0]
    log.info(row)
    event = create_event_from_row(row)
    return event


def try_set_active(event_id: str):
    with sqlite3.connect("bot_db.db") as connection:
        cursor = connection.cursor()
        sql = "SELECT is_active FROM events WHERE event_id = ? LIMIT 1"
        cursor.execute(sql, (event_id,))
        rows = cursor.fetchall()
        cursor.close()

        is_active = rows[0][0]
        log.info(is_active)
        if is_active == 1:
            return False
        else:
            cursor = connection.cursor()
            sql = "UPDATE events SET is_active = 1 WHERE event_id = ?"
            cursor.execute(sql, (event_id,))
            connection.commit()
            cursor.close()
            return True
