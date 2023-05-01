import sqlite3
from datetime import timedelta, datetime


def create_necessary_tables_if_not_exist():
    with sqlite3.connect("bot_db.db") as connection:
        pass
        # sql = "CREATE TABLE IF NOT EXISTS events (user_id INT, )"
        # cursor = connection.cursor()
        # cursor.execute(sql)
        # connection.commit()

        # sql = "CREATE TABLE IF NOT EXISTS requests (user_id INT, request TEXT)"
        # cursor = connection.cursor()
        # cursor.execute(sql)
        # connection.commit()
        #
        # sql = "CREATE TABLE IF NOT EXISTS shows (user_id INT, movie TEXT)"
        # cursor = connection.cursor()
        # cursor.execute(sql)
        # connection.commit()
        # cursor.close()


def save_event(user_id: int, event_description: str, start_time: datetime, period: timedelta):
    pass