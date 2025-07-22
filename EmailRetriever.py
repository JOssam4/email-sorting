import base64
import os.path
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from Email import Email
from typing import Any
from enum import StrEnum


class MimeType(StrEnum):
    TEXT_PLAIN = 'text/plain'
    TEXT_HTML = 'text/html'
    MULTIPART_ALTERNATIVE = 'multipart/alternative'
    MULTIPART_RELATED = 'multipart/related'


class EmailRetriever:
    def __init__(self, gmail_api_client_secret_filename: str):
        self.gmail_api_client_secret_filename = gmail_api_client_secret_filename
        self.SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
        self.creds = self.__retrieve_creds()

    def __retrieve_creds(self):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.gmail_api_client_secret_filename,
                    self.SCOPES
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
            query = 'in:inbox -category:social -category:promotions'
            unread_messages = (service.users().messages().list(userId='me', labelIds=['UNREAD'], q=query, maxResults=500).execute())
            emails: list[Email] = []
            for message in unread_messages.get('messages'):
                msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                message_id = message['id']
                link = self.__make_url_from_message_id(message_id)
                timestamp = msg['internalDate'] # unix-like timestamp (milliseconds from 1/1/1970)
                time_sent = datetime.fromtimestamp(int(timestamp) // 1000)
                sent_from = next(header.get('value') for header in msg['payload']['headers'] if header.get('name') == 'From')
                subject = next(header.get('value') for header in msg['payload']['headers'] if header.get('name') == 'Subject')
                body_base64 = self.__retrieve_body(msg.get('payload'))
                body = self.__decode_body(body_base64)
                email = Email(message_id, link, time_sent, sent_from, subject, body)
                emails.append(email)
            return emails

        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            print(f"An error occurred: {error}")
            return []

    def __retrieve_body(self, payload) -> Any:
        parts: list[Any] | None = payload.get('parts', None)
        if parts is None:
            return payload.get('body').get('data')

        parts_mimetypes = [part.get('mimeType') for part in parts]
        # desired mime type, in order: text/plain, text/html, multipart/alternative (contains plain & html), multipart/related. Images not supported (yet)
        # TODO: support passing images from image/jpeg, image/png, image/gif mime types to OpenAI api
        if MimeType.TEXT_PLAIN in parts_mimetypes:
            index = parts_mimetypes.index(MimeType.TEXT_PLAIN)
            part = parts[index]
            return part.get('body').get('data')

        if MimeType.TEXT_HTML in parts_mimetypes:
            index = parts_mimetypes.index(MimeType.TEXT_HTML)
            part = parts[index]
            return part.get('body').get('data')

        if MimeType.MULTIPART_ALTERNATIVE in parts_mimetypes:
            index = parts_mimetypes.index(MimeType.MULTIPART_ALTERNATIVE)
            part = parts[index]
            return self.__retrieve_body(part)

        if MimeType.MULTIPART_RELATED in parts_mimetypes:
            index = parts_mimetypes.index(MimeType.MULTIPART_RELATED)
            part = parts[index]
            return self.__retrieve_body(part)

        assert False

    @staticmethod
    def __decode_body(body_base64: str) -> str:
        decoded_body = base64.urlsafe_b64decode(body_base64)
        return decoded_body.decode('utf-8')

    @staticmethod
    def __make_url_from_message_id(message_id: str) -> str:
        user_id = 'me'
        return f'https://mail.google.com/mail/u/{user_id}/#all/{message_id}'