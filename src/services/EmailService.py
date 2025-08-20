import asyncio
from datetime import timedelta
from typing import Iterable, Generator
from fastapi import Request, HTTPException
from src.model.Email import Email, EmailIdAndPriority
from src.model.Secrets import Secrets
from src.services.EmailRetrieverService import EmailRetriever
from src.services.MySqlConnectorService import MySqlConnector
from src.services.EmailAnalyzerService import EmailAnalyzer
from redis import Redis
from itsdangerous import Signer, BadSignature


class EmailService:
    def __init__(self, scopes: list[str], secrets: Secrets, redis_client: Redis):
        self.scopes = scopes
        self.secrets = secrets
        self.redis_client = redis_client
        self.SESSION_COOKIE = 'session_id'
        self.signer = Signer(secrets.signing_key)

    def fetch_emails(self, credentials_json: str) -> tuple[str, list[Email]]:
        email_retriever = EmailRetriever(credentials_json, self.scopes)
        username = email_retriever.retrieve_username()
        emails = email_retriever.retrieve_emails()
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
