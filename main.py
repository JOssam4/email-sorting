from Email import Email, EmailMetadata
from EmailAnalyzer import EmailAnalyzer
from EmailRetriever import EmailRetriever
from MySqlConnector import MySqlConnector
from fastapi import FastAPI

from Secrets import Secrets

app = FastAPI()


def run(gmail_api_client_secret_filename: str, mysql_password: str, call_chatgpt_api: bool=False) -> list[EmailMetadata]:
    """
    1. Retrieve emails
    2. Analyze emails if necessary
    3. Update database with any new emails and/or priorities
    """
    (username, emails) = fetch_emails(gmail_api_client_secret_filename)
    with MySqlConnector(mysql_password, username) as mysql_connector:
        if call_chatgpt_api: evaluate_email_priorities_if_necessary(mysql_connector, emails)
        mysql_connector.sync_emails_to_db(emails)
    return [EmailMetadata.from_email(email) for email in emails]


def fetch_emails(gmail_api_client_secret_filename: str) -> (str, list[Email]):
    email_retriever = EmailRetriever(gmail_api_client_secret_filename)
    username = email_retriever.retrieve_username()
    emails = email_retriever.retrieve_emails()
    print('finished retrieving emails')
    return username, emails


def evaluate_email_priorities_if_necessary(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    email_analyzer = EmailAnalyzer()
    gmail_ids_without_priority = mysql_connector.get_gmail_ids_without_priority()
    emails_needing_priority = [email for email in emails if email.gmail_id in gmail_ids_without_priority]
    for email in emails_needing_priority:
        email.priority = email_analyzer.determine_email_priority(email)
    print('finished evaluating email priorities')


@app.get('/analyze_emails')
def read_analyzed_emails():
    print('ACTUALLY HIT ENDPOINT')
    # return run(secrets_filename)


if __name__ == '__main__':
    secrets = Secrets.from_env()
    run(secrets.gmail_api_client_secret_filename, secrets.mysql_password, secrets.call_chatgpt_api)
