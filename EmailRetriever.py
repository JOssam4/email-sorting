import base64
import os.path
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from Email import Email


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class EmailRetriever:
    def __init__(self, gmail_api_client_secret_filename: str):
        self.gmail_api_client_secret_filename = gmail_api_client_secret_filename
        self.creds = self.__retrieve_creds()

    def __retrieve_creds(self):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.gmail_api_client_secret_filename,
                    SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds

    def retrieve_emails(self) -> list[Email]:
        try:
            # Call the Gmail API
            service = build("gmail", "v1", credentials=self.creds)
            # Retrieve emails in 'primary' section of inbox
            query = 'in:inbox -category:social -category:promotions -category:updates -category:forums'
            unread_messages = (service.users().messages().list(userId='me', labelIds=['UNREAD'], q=query).execute())
            emails: list[Email] = []
            for message in unread_messages.get('messages'):
                msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                timestamp = msg['internalDate'] # unix-like timestamp (milliseconds from 1/1/1970)
                time_sent = datetime.fromtimestamp(int(timestamp) // 1000)
                subject = next(header.get('value') for header in msg['payload']['headers'] if header.get('name') == 'Subject')
                body = self.__retrieve_body(msg)
                email = Email(time_sent, subject, body)
                emails.append(email)
            return emails

        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            print(f"An error occurred: {error}")
            return []

    def __retrieve_body(self, msg) -> str:
        body_base64 = next(part.get('body').get('data') for part in msg['payload']['parts'] if part.get('mimeType') == 'text/plain')
        decoded_body = base64.urlsafe_b64decode(body_base64)
        return decoded_body.decode('utf-8')


def main():
    email_retriever = EmailRetriever()
    email_retriever.retrieve_emails()


if __name__ == "__main__":
    main()