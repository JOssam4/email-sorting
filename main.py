from Email import Email
from EmailAnalyzer import EmailAnalyzer, Priority


def run() -> None:
    emails = fetch_emails()
    [low_priority_emails, medium_priority_emails, high_priority_emails] = process_emails(emails)

    print(low_priority_emails)
    print(medium_priority_emails)
    print(high_priority_emails)


def fetch_emails():
    pass


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
    run()
