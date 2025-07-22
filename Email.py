from dataclasses import dataclass
from datetime import datetime

@dataclass()
class Email:
    gmail_id: str
    link: str
    time_sent: datetime
    sent_from: str
    subject: str
    body: str

    def __repr__(self):
        return f'Email(time_sent={self.time_sent}, sent_from={self.sent_from}, subject={self.subject}, body=...)'