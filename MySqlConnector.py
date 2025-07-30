from typing import Any
from mysql import connector
from Email import Email, Priority


class MySqlConnector:
    def __init__(self, password: str, schema: str):
        self.connection_failed = False
        # Assume database name 'emails' already exists. Each user will have their own schema
        try:
            self.mydb = connector.connect(
                host='localhost',
                user='root',
                password=password,
            )
            print(f'Creating schema {schema} if it does not already exist...')
            self.__create_schema_if_not_exist(schema)
            print(f'Creating table if it does not already exist...')
            self.__create_table_if_not_exists()
            print('Successfully connected to MySql!')
        except connector.Error as err:
            print(f'Error connecting to MySql: {err}')
            self.connection_failed = True

    def retrieve_emails(self, select_fields: set[str] = None) -> list[Any]:
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')
        with self.mydb.cursor() as cursor:
            selected_fields = '*' if select_fields is None or len(select_fields) == 0 else ', '.join(select_fields)
            cursor.execute(f"SELECT {selected_fields} FROM emails")
            results = cursor.fetchall()
        return results

    def insert_emails(self, emails: list[Email]) -> None:
        """
        :param emails: List of emails to add to the database.
        If an email already exists, it will be ignored.
        """
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')
        sql = """INSERT IGNORE INTO emails (gmail_id, link, time_sent, sent_from, priority) VALUES (%s, %s, %s, %s, %s)"""
        data = [(email.gmail_id, email.link, email.time_sent, email.sent_from, email.priority) for email in emails]
        with self.mydb.cursor() as cursor:
            cursor.executemany(sql, data)
        self.mydb.commit()

    def update_priorities(self, emails: list[Email]) -> None:
        if not self.mydb.is_connected():
            raise ConnectionError('Connection to MySql closed')
        low_priority_email_ids = [(email.gmail_id,) for email in emails if email.priority == Priority.LOW]
        medium_priority_emails_ids = [(email.gmail_id,) for email in emails if email.priority == Priority.MEDIUM]
        high_priority_emails_ids = [(email.gmail_id,) for email in emails if email.priority == Priority.HIGH]
        set_low_priority_sql = f"UPDATE emails SET priority = 'low' WHERE gmail_id IN ({', '.join(['%s'] * len(low_priority_email_ids))})"
        set_medium_priority_sql = f"UPDATE emails SET priority = 'medium' WHERE gmail_id IN ({', '.join(['%s'] * len(medium_priority_emails_ids))})"
        set_high_priority_sql = f"UPDATE emails SET priority = 'high' WHERE gmail_id IN ({', '.join(['%s'] * len(high_priority_emails_ids))})"
        with self.mydb.cursor() as cursor:
            if len(low_priority_email_ids) > 0:
                cursor.executemany(set_low_priority_sql, low_priority_email_ids)
            if len(medium_priority_emails_ids) > 0:
                cursor.executemany(set_medium_priority_sql, medium_priority_emails_ids)
            if len(high_priority_emails_ids) > 0:
                cursor.executemany(set_high_priority_sql, high_priority_emails_ids)
        self.mydb.commit()

    def close_connection(self) -> None:
        if self.mydb.is_connected():
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