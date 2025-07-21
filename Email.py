from dataclasses import dataclass
from datetime import datetime

@dataclass()
class Email:
    time_sent: datetime
    subject: str
    body: str

    def __repr__(self):
        return f'Email(time_sent={self.time_sent}, subject={self.subject}, body=...)'