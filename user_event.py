from dataclasses import dataclass
from datetime import datetime


@dataclass
class UserEvent:
    event_id: str
    user_id: int
    name: str
    date: datetime
    period: str
