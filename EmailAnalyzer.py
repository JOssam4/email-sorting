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

    def determine_email_priority(self, email: Email) -> Priority:
        date_sent_timestamp = self.__get_timestamp_from_datetime(email.time_sent)
        now_timestamp = self.__get_timestamp_from_datetime(self.now)
        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model="gpt-4.1-nano",
            input=[
                {
                    "role": "system",
                    "content": """
        You are an assistant that analyzes emails to extract actionable information.

        Given an email's subject, body, and timestamps, return a JSON object with the following fields:
        - "action" (bool): Does the email request or imply the user needs to do something?
        - "overdue" (bool): Is the requested action overdue based on the date it was sent and the current date?
        - "due_soon" (bool): Is the action due in the next 7 days from the current date?
        - "urgent" (int, 1-10): Rate the urgency of the action, where 1 is not urgent and 10 is extremely urgent.
        - "explanation" (str): A brief explanation justifying the urgency score.

        Use your best judgment if the email is vague. Be concise and consistent in the JSON response.

        Example output:
        {
          "action": true,
          "overdue": false,
          "due_soon": true,
          "urgent": 7,
          "explanation": "The sender asked for a reply within a week, indicating moderate urgency."
        }
        """
                },
                {
                    "role": "user",
                    "content": f"""
        Current date/time: {now_timestamp}
        Message sent: {date_sent_timestamp}

        Subject: {email.subject}

        Body:
        {email.body}
        """
                }
            ],
            temperature=0
        )

        analysis = json.loads(response.output_text)
        return self.get_email_priority(analysis)

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
