import asyncio
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import BaseModel

from src.model.email import Email, Priority, EmailIdAndPriority


class OutputFormat(BaseModel):
    actionable: bool
    overdue: bool
    due_soon: bool
    urgent: int
    explanation: str


class EmailAnalyzer:
    def __init__(self, openai_key: str) -> None:
        self.now = datetime.now()
        self.client = AsyncOpenAI(api_key=openai_key)
        self.semaphore = asyncio.Semaphore(5)

    async def determine_email_priority(self, email: Email) -> EmailIdAndPriority:
        date_sent_timestamp = self.__get_timestamp_from_datetime(email.time_sent)
        now_timestamp = self.__get_timestamp_from_datetime(self.now)
        async with self.semaphore: # limit concurrency to 5 requests at a time
            print(f'submitting analyzation request for email with gmail id {email.gmail_id}')
            response = await self.client.responses.parse(
                model="gpt-5-nano",
                input=[
                    {
                        "role": "system",
                        "content": """
            You are an assistant that analyzes emails to extract actionable information.
    
            Given an email's subject, body, and timestamps, return a JSON object with the following fields:
            - "actionable" (bool): Does the email request or imply the user needs to do something?
            - "overdue" (bool): Is the requested action overdue based on the date it was sent and the current date?
            - "due_soon" (bool): Is the action due in the next 7 days from the current date?
            - "urgent" (int, 1-10): Rate the urgency of the action, where 1 is not urgent and 10 is extremely urgent.
            - "explanation" (str): A brief explanation justifying the urgency score.
    
            Use your best judgment if the email is vague. Be concise and consistent in the JSON response.
    
            Example output:
            {
              "actionable": true,
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
                text_format=OutputFormat
            )

            priority = self.get_email_priority(response.output_parsed)
            gmail_id = email.gmail_id
            return EmailIdAndPriority(gmail_id, priority)

    @staticmethod
    def get_email_priority(analysis: OutputFormat) -> Priority:
        # destructure the dictionary into variables
        if analysis.overdue:
            return Priority.HIGH
        elif analysis.due_soon or analysis.urgent >= 5:
            return Priority.MEDIUM
        elif not analysis.actionable or analysis.urgent < 5:
            return Priority.LOW
        return Priority.LOW

    @staticmethod
    def __get_timestamp_from_datetime(date_time: datetime) -> str:
        return f'{date_time.month}/{date_time.day}/{date_time.year} at {date_time.hour}:{date_time.minute}:{date_time.second}'
