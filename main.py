
def run() -> None:
    emails = fetch_emails()
    [low_priority_emails, medium_priority_emails, high_priority_emails] = process_emails(emails)

    print(low_priority_emails)
    print(medium_priority_emails)
    print(high_priority_emails)

def fetch_emails():
    pass

def process_emails(emails):
    pass

if __name__ == '__main__':
    run()
