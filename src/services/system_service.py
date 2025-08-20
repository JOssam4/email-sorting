import os
from typing import Callable, Any

from fastapi import Request, HTTPException, BackgroundTasks, Response
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from google_auth_oauthlib.flow import Flow
from redis import Redis

from src.model.email import Priority, EmailMetadata
from src.model.secrets import Secrets
from src.services.email_retriever_service import EmailRetriever
from src.services.email_service import EmailService
from src.services.mysql_connector_service import MySqlConnector
from src.services.session_service import SessionService

secrets = Secrets.from_env()
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
redis_client = Redis(host='localhost', port=6379, db=0, decode_responses=True)
templates = Jinja2Templates(directory='./public')
session_service = SessionService(redis_client)
email_service = EmailService(SCOPES, secrets, redis_client)


async def run(request: Request) -> None:
    """
    1. Retrieve emails
    2. Analyze emails if necessary
    3. Update database with any new emails and/or priorities
    """
    mysql_password = secrets.mysql_password
    call_chatgpt_api = secrets.call_chatgpt_api
    credentials_json = session_service.retrieve_credentials(request)
    username, emails = email_service.fetch_emails(credentials_json)
    with MySqlConnector(mysql_password, username) as mysql_connector:
        mysql_connector.sync_emails_to_db_with_deletion(emails)
    emails_needing_priority = email_service.get_emails_needing_priority(mysql_password, username, emails)
    if call_chatgpt_api:
        emails_to_update = await email_service.evaluate_email_priorities(emails_needing_priority)
    else:
        emails_to_update = []
    with MySqlConnector(mysql_password, username) as mysql_connector:
        mysql_connector.sync_emails_to_db_without_deletion(emails_to_update)


async def remove_trailing_slash(request: Request, call_next: Callable) -> RedirectResponse | Any:
    # Usually defining the app like app = FastAPI() is enough to do this by default.
    # However, we have defined a catch-all route (for serving the frontend) which supersedes the redirect,
    # so the purpose of this middleware is the hacky workaround to remove trailing slashes.
    if request.url.path != "/" and request.url.path.endswith("/"):
        url = request.url.path.rstrip("/")
        if request.url.query:
            url += "?" + request.url.query
        return RedirectResponse(url)
    return await call_next(request)


def get_emails_with_priority(request: Request, priority: str) -> list[EmailMetadata]:
    # check if session is valid. Credentials aren't actually used here though
    session_service.retrieve_credentials(request)
    if priority not in {'low', 'medium', 'high'}:
        raise HTTPException(status_code=400, detail='Invalid priority')
    mysql_password = secrets.mysql_password
    credentials_json = session_service.retrieve_credentials(request)
    email_retriever = EmailRetriever(credentials_json, SCOPES)
    username = email_retriever.retrieve_username()
    with MySqlConnector(mysql_password, username) as mysql_connector:
        if priority == Priority.LOW:
            return mysql_connector.retrieve_emails_with_priority(Priority.LOW)
        elif priority == Priority.MEDIUM:
            return mysql_connector.retrieve_emails_with_priority(Priority.MEDIUM)
        else:
            return mysql_connector.retrieve_emails_with_priority(Priority.HIGH)


def callback(request: Request) -> RedirectResponse:
    code = request.query_params.get('code')
    state = request.query_params.get('state')
    flow = Flow.from_client_secrets_file(secrets.gmail_api_client_secret_filename, scopes=SCOPES, state=state)
    flow.redirect_uri = 'http://localhost:8000/callback'
    flow.fetch_token(code=code)
    credentials = flow.credentials
    credentials_json = credentials.to_json()
    session_service.set_credentials(request, credentials_json)
    return RedirectResponse('/emails')


def login() -> RedirectResponse:
    flow = Flow.from_client_secrets_file(secrets.gmail_api_client_secret_filename, scopes=SCOPES,
                                         redirect_uri='http://localhost:8000/callback')
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)


def get_emails(request: Request, background_tasks: BackgroundTasks) -> Response:
    try:
        session_service.retrieve_credentials(request, )
    except HTTPException:
        return RedirectResponse('/')

    should_pull_emails = email_service.get_should_pull_emails(request)
    if should_pull_emails:
        # start expensive run(request) method in background. Let endpoint resolve without waiting on that task.
        background_tasks.add_task(run, request)
        email_service.prevent_pulling_emails(request)
        print('Pulling new emails')
    else:
        print('New emails will not be pulled.')
    # username = email_retriever.retrieve_username()
    # emails = email_retriever.retrieve_emails()
    return templates.TemplateResponse(request, 'index.html')


def root(request: Request, response: Response) -> Response:
    try:
        session_service.retrieve_credentials(request)
    except HTTPException:
        session_service.create_session(response)
        return templates.TemplateResponse(request, 'index.html', headers=response.headers)

    # If session already exists, go redirect to emails page
    return RedirectResponse('/emails')


def serve_frontend_for_email_priorities(request: Request, response: Response) -> Response:
    return templates.TemplateResponse(request, 'index.html', headers=response.headers)


async def serve_frontend(full_path: str) -> Response | dict[str, str]:
    path_to_file = os.path.join('./public', full_path)
    if 'assets' in path_to_file:
        return FileResponse(path_to_file)
    return {'message': 'failure'}
