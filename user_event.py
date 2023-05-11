from dataclasses import dataclass


@dataclass
class UserEvent:
    event_id: str
    user_id: int
    name: str
    date: datetime
    period: str
