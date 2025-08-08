import base64
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
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
    def __init__(self, credentials_json: str, scopes: list[str]):
        credentials_dict = json.loads(credentials_json)
        self.creds = Credentials.from_authorized_user_info(credentials_dict, scopes)

    def retrieve_username(self) -> str:
        """
        :return: username of user (email address = username@gmail.com)
        """
        service = build("gmail", "v1", credentials=self.creds)
        profile = service.users().getProfile(userId='me').execute()
        return profile['emailAddress'].removesuffix('@gmail.com')

    def retrieve_emails(self) -> list[Email]:
        try:
            # Call the Gmail API
            service = build("gmail", "v1", credentials=self.creds)
            # Retrieve emails in 'primary' section of inbox
            query = 'in:inbox -category:social -category:promotions'
            # TODO: remove max rows
            unread_messages = (service.users().messages().list(userId='me', labelIds=['UNREAD'], q=query, maxResults=3).execute())
            emails: list[Email] = []
            if unread_messages.get('resultSizeEstimate') > 0:
                for message in unread_messages.get('messages'):
                    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                    message_id = message['id']
                    link = self.__make_url_from_message_id(message_id)
                    timestamp = msg['internalDate'] # unix-like timestamp (milliseconds from 1/1/1970)
                    time_sent = datetime.fromtimestamp(int(timestamp) // 1000)
                    sent_from = next(header.get('value') for header in msg['payload']['headers'] if header.get('name').lower() == 'from')
                    subject = next(header.get('value') for header in msg['payload']['headers'] if header.get('name') == 'Subject')
                    body_base64 = self.__retrieve_body(msg.get('payload'))
                    body = self.__decode_body(body_base64)
                    email = Email(message_id, link, time_sent, sent_from, subject, body, None)
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
        user_id = '0'
        return f'https://mail.google.com/mail/u/{user_id}/#all/{message_id}'