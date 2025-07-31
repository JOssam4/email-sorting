from dataclasses import dataclass
from dotenv import load_dotenv
import os

@dataclass
class Secrets:
    gmail_api_client_secret_filename: str
    mysql_password: str
    call_chatgpt_api: bool

    @staticmethod
    def from_env() -> 'Secrets':
        load_dotenv()
        gmail_api_client_secret_filename = os.getenv('GMAIL_API_CLIENT_SECRET_FILENAME')
        mysql_password = os.getenv('MYSQL_PASSWORD')
        call_chatgpt_api = os.getenv('CALL_CHATGPT_API', 'false').lower() == 'true'
        if not gmail_api_client_secret_filename or not mysql_password:
            raise ValueError("Missing environment variables in .env")
        return Secrets(gmail_api_client_secret_filename, mysql_password, call_chatgpt_api)
