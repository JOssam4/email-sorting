from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional


class Priority(StrEnum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


@dataclass()
class Email:
    gmail_id: str
    link: str
    time_sent: datetime
    sent_from: str
    subject: str
    body: str
    priority: Optional[Priority]


    def __repr__(self):
        return f'Email(time_sent={self.time_sent}, sent_from={self.sent_from}, subject={self.subject}, body=...)'


@dataclass()
class EmailWithoutBody:
    gmail_id: str
    link: str
    time_sent: datetime
    sent_from: str
    subject: str
    priority: Optional[Priority]