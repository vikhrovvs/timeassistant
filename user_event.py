from dataclasses import dataclass
from datetime import datetime

from utils import DEFAULT_TZ


@dataclass
class UserEvent:
    event_id: str
    user_id: int
    name: str
    date: datetime
    period: str


def create_event_from_row(row) -> UserEvent:
    event_id, user_id, name, date_str, period, is_active = row
    date = datetime.strptime(date_str, "%d/%m/%Y %H:%M:%S")
    date = date.replace(tzinfo=DEFAULT_TZ)
    event = UserEvent(event_id, user_id, name, date, period)
    return event
