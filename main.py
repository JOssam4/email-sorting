from Email import Email, EmailWithoutBody
from EmailAnalyzer import EmailAnalyzer
from EmailRetriever import EmailRetriever
from MySqlConnector import MySqlConnector
from Secrets import Secrets
from fastapi import FastAPI
import json


app = FastAPI()


def read_secrets_from_json() -> Secrets:
    with open('secrets.json', 'r') as f:
        secrets = json.load(f)
        gmail_api_client_secret_filename = secrets['gmail_api_client_secret_filename']
        mysql_password = secrets['mysql_password']
        return Secrets(gmail_api_client_secret_filename, mysql_password)


def run(gmail_api_client_secret_filename: str, mysql_password: str) -> list[EmailWithoutBody]:
    """
    1. Retrieve emails
    2. Put emails in database
    3. Analyze emails
    4. Put the analysis into the database
    """
    email_retriever = EmailRetriever(gmail_api_client_secret_filename)
    username = email_retriever.retrieve_username()
    emails = email_retriever.retrieve_emails()

    schema_name = f'{username}_emails'
    mysql_connector = MySqlConnector(mysql_password, schema_name)
    store_emails_in_database(mysql_connector, emails)
    analyze_emails(emails)
    update_priorities_in_database(mysql_connector, emails)
    return [EmailWithoutBody(email.gmail_id, email.link, email.time_sent, email.sent_from, email.subject, email.priority) for email in emails]


def fetch_emails(gmail_api_client_secret_filename: str) -> list[Email]:
    email_retriever = EmailRetriever(gmail_api_client_secret_filename)
    emails = email_retriever.retrieve_emails()
    print('finished retrieving emails')
    return emails


def store_emails_in_database(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    mysql_connector.insert_emails(emails)
    print('finished adding emails to database')


def update_priorities_in_database(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    mysql_connector.update_priorities(emails)
    print('finished setting priorities')


def process_emails(emails: list[Email]) -> None:
    email_analyzer = EmailAnalyzer()
    for email in emails:
        analysis = email_analyzer.analyze_email(email)
        priority = EmailAnalyzer.get_email_priority(analysis)
        email.priority = priority

@app.get('/analyze_emails')
def read_analyzed_emails():
    print('ACTUALLY HIT ENDPOINT')
    # return run(secrets_filename)


if __name__ == '__main__':
    # read_analyzed_emails()
    secrets = read_secrets_from_json()
    run(secrets.gmail_api_client_secret_filename, secrets.mysql_password)