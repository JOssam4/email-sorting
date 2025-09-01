import asyncio
from datetime import timedelta
from typing import Iterable, Generator

from fastapi import Request, HTTPException
from itsdangerous import Signer, BadSignature
from redis import Redis

from src.model.email import Email, EmailIdAndPriority, EmailIdAndExistence
from src.model.secrets import Secrets
from src.services.email_analyzer_service import EmailAnalyzer
from src.services.email_retriever_service import EmailRetriever
from src.services.mysql_connector_service import MySqlConnector


class EmailService:
    def __init__(self, scopes: list[str], secrets: Secrets, redis_client: Redis):
        self.scopes = scopes
        self.secrets = secrets
        self.redis_client = redis_client
        self.SESSION_COOKIE = 'session_id'
        self.signer = Signer(secrets.signing_key)

    def fetch_emails(self, credentials_json: str) -> tuple[str, list[Email]]:
        self.email_retriever = EmailRetriever(credentials_json, self.scopes)
        username = self.email_retriever.retrieve_username()
        emails = self.email_retriever.retrieve_emails()
        print('finished retrieving emails')
        return username, emails

    @staticmethod
    def get_emails_needing_priority(mysql_password: str, username: str, emails: list[Email]) -> Generator[Email]:
        with MySqlConnector(mysql_password, username) as mysql_connector:
            gmail_ids_without_priority = mysql_connector.get_gmail_ids_without_priority()
        return (email for email in emails if email.gmail_id in gmail_ids_without_priority)

    async def evaluate_email_priorities(self, emails_needing_priority: Iterable[Email]) -> list[Email]:
        email_analyzer = EmailAnalyzer(self.secrets.openai_key)
        emails = [email for email in emails_needing_priority]
        gmail_id_to_email_dict = {email.gmail_id: email for email in emails}
        priority_coros = [email_analyzer.determine_email_priority(email) for email in emails]
        email_ids_and_priorities: list[EmailIdAndPriority] = await asyncio.gather(*priority_coros)
        for email_id_and_priority in email_ids_and_priorities:
            gmail_id = email_id_and_priority.gmail_id
            email = gmail_id_to_email_dict.get(gmail_id)
            email.priority = email_id_and_priority.priority
        # print green
        print('\033[92mfinished evaluating email priorities\033[0m')
        return emails

    async def find_ids_of_emails_to_remove_from_db(self, all_gmail_ids: set[str]) -> set[str]:
        exists_in_gmail_coros = [self.email_retriever.email_exists(gmail_id) for gmail_id in all_gmail_ids]
        email_ids_and_existences: list[EmailIdAndExistence] = await asyncio.gather(*exists_in_gmail_coros)
        return {email.gmail_id for email in email_ids_and_existences if not email.exists}

    def get_should_pull_emails(self, request: Request) -> bool:
        signed_session_id = request.cookies.get(self.SESSION_COOKIE)
        if not signed_session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            session_id = self.signer.unsign(signed_session_id).decode()
        except BadSignature:
            raise HTTPException(status_code=401, detail='Invalid session cookie')

        existing_value = self.redis_client.hget(f'session:{session_id}', 'has_pulled_emails_recently')
        return existing_value is None

    def prevent_pulling_emails(self, request: Request) -> None:
        signed_session_id = request.cookies.get(self.SESSION_COOKIE)
        if not signed_session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            session_id = self.signer.unsign(signed_session_id).decode()
        except BadSignature:
            raise HTTPException(status_code=401, detail='Invalid session cookie')

        hash_name = f'session:{session_id}'
        self.redis_client.hset(hash_name, mapping={'has_pulled_emails_recently': 'true'})
        self.redis_client.hexpire(hash_name, timedelta(minutes=5), 'has_pulled_emails_recently')
