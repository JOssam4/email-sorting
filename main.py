from Email import Email
from EmailAnalyzer import EmailAnalyzer, Priority
from EmailRetriever import EmailRetriever
from argparse import ArgumentParser


def run(gmail_api_client_secret_filename: str) -> None:
    emails = fetch_emails(gmail_api_client_secret_filename)
    [low_priority_emails, medium_priority_emails, high_priority_emails] = process_emails(emails)

    print(f'{low_priority_emails=}')
    print(f'{medium_priority_emails=}')
    print(f'{high_priority_emails=}')


def fetch_emails(gmail_api_client_secret_filename: str) -> list[Email]:
    email_retriever = EmailRetriever(gmail_api_client_secret_filename)
    emails = email_retriever.retrieve_emails()
    return emails


def process_emails(emails: list[Email]) -> list[list[Email]]:
    email_analyzer = EmailAnalyzer()
    low_priority_emails = []
    medium_priority_emails = []
    high_priority_emails = []
    for email in emails:
        analysis = email_analyzer.analyze_email(email)
        priority = EmailAnalyzer.get_email_priority(analysis)
        match priority:
            case Priority.LOW:
                low_priority_emails.append(email)
            case Priority.MEDIUM:
                medium_priority_emails.append(email)
            case Priority.HIGH:
                high_priority_emails.append(email)
            case _:
                assert False
    return [low_priority_emails, medium_priority_emails, high_priority_emails]


if __name__ == '__main__':
    parser = ArgumentParser(
        prog='email-sorter',
        description='Sorts emails based on urgency',
    )
    parser.add_argument('-s', '--secret', help='filename of gmail secrets file', required=True)
    args = parser.parse_args()
    secrets_filename = args.secret
    run(secrets_filename)
