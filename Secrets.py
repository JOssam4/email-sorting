from dataclasses import dataclass

@dataclass()
class Secrets:
    gmail_api_client_secret_filename: str
    mysql_password: str