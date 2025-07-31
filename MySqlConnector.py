import hashlib
from typing import Any
from mysql import connector
from Email import Email


class MySqlConnector:
    def __init__(self, password: str, username: str):
        self.connection_failed = False
        self.mydb = None
        try:
            self.mydb = connector.connect(
                host='localhost',
                user='root',
                password=password,
            )
            schema_name = self.__get_hashed_schema_name(username)
            print(f'Creating schema {schema_name} if it does not already exist...')
            self.__create_schema_if_not_exist(schema_name)
            print(f'Creating table if it does not already exist...')
            self.__create_table_if_not_exists()
            print('Successfully connected to MySql!')
        except connector.Error as err:
            print(f'Error connecting to MySql: {err}')
            self.connection_failed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()

    def get_gmail_ids_without_priority(self) -> set[str]:
        """
        Retrieves all gmail_ids where priority is NULL.
        """
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')

        query = "SELECT gmail_id FROM emails WHERE priority IS NULL"
        with self.mydb.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
        return {row[0] for row in results}

    def retrieve_emails(self, select_fields: set[str] = None) -> list[Any]:
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')
        with self.mydb.cursor() as cursor:
            selected_fields = '*' if select_fields is None or len(select_fields) == 0 else ', '.join(select_fields)
            cursor.execute(f"SELECT {selected_fields} FROM emails")
            results = cursor.fetchall()
        return results

    def sync_emails_to_db(self, emails: list[Email]) -> None:
        """
        Insert new emails and update the priority for existing ones.
        Emails are matched by gmail_id (which must be unique).
        """
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')

        sql = """
        INSERT INTO emails (gmail_id, link, time_sent, sent_from, priority)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            priority = VALUES(priority)
        """
        data = [
            (email.gmail_id, email.link, email.time_sent, email.sent_from, email.priority)
            for email in emails
        ]
        with self.mydb.cursor() as cursor:
            cursor.executemany(sql, data)
        self.mydb.commit()
        print('finished adding emails to database')

    def close_connection(self) -> None:
        if self.mydb and self.mydb.is_connected():
            self.mydb.close()
            print('MySql connection closed')

    def __create_schema_if_not_exist(self, schema: str) -> None:
        with self.mydb.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS {schema}')
            cursor.execute(f'USE {schema}')

    def __create_table_if_not_exists(self) -> None:
        sql = '''CREATE TABLE IF NOT EXISTS emails(
            id        int auto_increment
                primary key,
            gmail_id  varchar(16)                    not null,
            link      tinytext                       null,
            time_sent datetime                       null,
            sent_from text                           null,
            priority  enum ('low', 'medium', 'high') null,
            constraint gmail_id
                unique (gmail_id)
        );'''
        with self.mydb.cursor() as cursor:
            cursor.execute(sql)

    @staticmethod
    def __get_hashed_schema_name(username: str) -> str:
        """Generate a valid and unique schema name using a hash of the username."""
        hashed = hashlib.sha256(username.encode('utf-8')).hexdigest()[:32]
        return f'user_{hashed}_emails'
