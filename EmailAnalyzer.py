import json
from openai import OpenAI
from datetime import datetime
from typing import Any
from operator import itemgetter
from Email import Email, Priority


def get_key_from_file(filename: str) -> str:
    with open(filename, 'r') as f:
        key_obj = json.load(f)
    return key_obj['api_key']


class EmailAnalyzer:
    def __init__(self) -> None:
        self.api_key = get_key_from_file('apikey.json')
        self.now = datetime.now()

    def analyze_email(self, email: Email) -> dict[str, Any]:
        date_sent_timestamp = self.__get_timestamp_from_datetime(email.time_sent)
        now_timestamp = self.__get_timestamp_from_datetime(self.now)
        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model="gpt-4.1-nano",
            input=[
                {
                    'role': 'system',
                    'content': '''Read the following email subject and message. Respond with a JSON object containing:
                            - "action": a boolean indicating if the email asks the user to perform an action
                            - "overdue": a boolean indicating whether the action is overdue
                            - "due_soon": a boolean indicating whether the action should be done in the upcoming week
                            - "urgent": a scale from 1 to 10 indicating how urgent the email is
                            - "explanation": an explanation for urgency score
                        '''
                },
                {
                    'role': 'user',
                    'content': f'Today the date/time is: {now_timestamp} Message sent: "{date_sent_timestamp}" Subject: "{email.subject}" Message: "{email.body}"'
                }
            ],
            temperature=0
        )
        return json.loads(response.output_text)

    @staticmethod
    def get_email_priority(analysis: dict[str, Any]) -> Priority:
        # destructure the dictionary into variables
        action, overdue, due_soon, urgent, explanation = itemgetter('action', 'overdue', 'due_soon', 'urgent', 'explanation')(analysis)
        if overdue:
            return Priority.HIGH
        elif due_soon or urgent >= 5:
            return Priority.MEDIUM
        elif not action or urgent < 5:
            return Priority.LOW
        return Priority.LOW

    @staticmethod
    def __get_timestamp_from_datetime(date_time: datetime) -> str:
        return f'{date_time.month}/{date_time.day}/{date_time.year} at {date_time.hour}:{date_time.minute}:{date_time.second}'
