from dataclasses import dataclass
from datetime import datetime

@dataclass()
class Email:
    time_sent: datetime
    subject: str
    body: str