import os
import random
from dns.tsig import BadSignature
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse

from Email import Email, Priority
from EmailAnalyzer import EmailAnalyzer
from EmailRetriever import EmailRetriever
from MySqlConnector import MySqlConnector
from Secrets import Secrets
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from redis import Redis
from itsdangerous import Signer
import uuid
import uvicorn

app = FastAPI()
secrets = Secrets.from_env()
secrets_file = secrets.gmail_api_client_secret_filename
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SIGNING_KEY = 'READ_THIS_FROM_DOTENV'
signer = Signer(SIGNING_KEY)
SESSION_COOKIE = 'session_id'
redis_client = Redis(host='localhost', port=6379, db=0, decode_responses=True)
app.mount('/public', StaticFiles(directory='public'), name='public')
templates = Jinja2Templates(directory='./public')


def run(request: Request) -> None:
    """
    1. Retrieve emails
    2. Analyze emails if necessary
    3. Update database with any new emails and/or priorities
    """
    mysql_password = secrets.mysql_password
    call_chatgpt_api = secrets.call_chatgpt_api
    credentials_json = retrieve_credentials(request)
    (username, emails) = fetch_emails(credentials_json)
    # TODO: remove this logic here. It's just for testing.
    for email in emails:
        email.priority = random.choice([Priority.LOW, Priority.MEDIUM, Priority.HIGH])
    with MySqlConnector(mysql_password, username) as mysql_connector:
        if call_chatgpt_api:
            evaluate_email_priorities_if_necessary(mysql_connector, emails)
        mysql_connector.sync_emails_to_db(emails)


def fetch_emails(credentials_json: str) -> tuple[str, list[Email]]:
    email_retriever = EmailRetriever(credentials_json, SCOPES)
    username = email_retriever.retrieve_username()
    emails = email_retriever.retrieve_emails()
    print('finished retrieving emails')
    return username, emails


def evaluate_email_priorities_if_necessary(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    email_analyzer = EmailAnalyzer()
    gmail_ids_without_priority = mysql_connector.get_gmail_ids_without_priority()
    emails_needing_priority = (email for email in emails if email.gmail_id in gmail_ids_without_priority)
    for email in emails_needing_priority:
        email.priority = email_analyzer.determine_email_priority(email)
    print('finished evaluating email priorities')


def create_session(response: Response) -> None:
    session_id = str(uuid.uuid4())
    signed_session_id = signer.sign(session_id).decode()
    redis_client.hset(f'session:{session_id}', mapping={'credentials': ''})
    response.set_cookie(key=SESSION_COOKIE, value=signed_session_id, httponly=True)


def set_credentials(request: Request, credentials_json: str) -> None:
    signed_session_id = request.cookies.get(SESSION_COOKIE)
    if not signed_session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        session_id = signer.unsign(signed_session_id).decode()
    except BadSignature:
        raise HTTPException(status_code=401, detail='Invalid session cookie')

    redis_client.hset(f'session:{session_id}', mapping={'credentials': credentials_json})


def retrieve_credentials(request: Request) -> str:
    signed_session_id = request.cookies.get(SESSION_COOKIE)
    if not signed_session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        session_id = signer.unsign(signed_session_id).decode()
    except BadSignature:
        raise HTTPException(status_code=401, detail='Invalid session cookie')
    credentials = redis_client.hget(f'session:{session_id}', 'credentials')
    if not credentials:
        raise HTTPException(status_code=401, detail='Session expired or invalid')
    return credentials


def prevent_pulling_emails(request: Request) -> None:
    signed_session_id = request.cookies.get(SESSION_COOKIE)
    if not signed_session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        session_id = signer.unsign(signed_session_id).decode()
    except BadSignature:
        raise HTTPException(status_code=401, detail='Invalid session cookie')

    hash_name = f'session:{session_id}'
    redis_client.hset(hash_name, mapping={'has_pulled_emails_recently': 'true'})
    redis_client.hexpire(hash_name, 5 * 60, 'has_pulled_emails_recently')


def get_should_pull_emails(request: Request) -> bool:
    signed_session_id = request.cookies.get(SESSION_COOKIE)
    if not signed_session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        session_id = signer.unsign(signed_session_id).decode()
    except BadSignature:
        raise HTTPException(status_code=401, detail='Invalid session cookie')

    existing_value = redis_client.hget(f'session:{session_id}', 'has_pulled_emails_recently')
    return existing_value is None


@app.get('/api/priorities/{priority}')
def get_emails_with_priority(request: Request, priority: str):
    if not priority in {'low', 'medium', 'high'}:
        raise HTTPException(status_code=400, detail='Invalid priority')
    mysql_password = secrets.mysql_password
    credentials_json = retrieve_credentials(request)
    email_retriever = EmailRetriever(credentials_json, SCOPES)
    username = email_retriever.retrieve_username()
    with MySqlConnector(mysql_password, username) as mysql_connector:
        if priority == Priority.LOW:
            return mysql_connector.retrieve_emails_with_priority(Priority.LOW)
        elif priority == Priority.MEDIUM:
            return mysql_connector.retrieve_emails_with_priority(Priority.MEDIUM)
        else:
            return mysql_connector.retrieve_emails_with_priority(Priority.HIGH)

@app.get('/callback')
def callback(request: Request):
    code = request.query_params.get('code')
    state = request.query_params.get('state')
    flow = Flow.from_client_secrets_file(secrets_file, scopes=SCOPES, state=state)
    flow.redirect_uri = 'http://localhost:8000/callback'
    flow.fetch_token(code=code)
    credentials = flow.credentials
    credentials_json = credentials.to_json()
    set_credentials(request, credentials_json)
    return RedirectResponse('http://localhost:8000/emails')


@app.get('/login')
def login():
    flow = Flow.from_client_secrets_file(secrets_file, scopes=SCOPES, redirect_uri='http://localhost:8000/callback')
    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)


@app.get('/emails')
def emails(request: Request, background_tasks: BackgroundTasks):
    try:
        retrieve_credentials(request)
    except HTTPException:
        return RedirectResponse('http://localhost:8000/')

    should_pull_emails = get_should_pull_emails(request)
    if should_pull_emails:
        background_tasks.add_task(run, request) # start expensive run(request) method in background. Let endpoint resolve without waiting on that task.
        prevent_pulling_emails(request)
        print('Pulling new emails')
    else:
        print('New emails will not be pulled.')
    # username = email_retriever.retrieve_username()
    # emails = email_retriever.retrieve_emails()
    return templates.TemplateResponse(request, 'index.html')


@app.get('/')
def main(request: Request, response: Response):
    create_session(response)
    return templates.TemplateResponse(request, 'index.html', headers=response.headers)


@app.get('/emails/priority/{priority}')
def serve_frontend_for_email_priorities(request: Request, response: Response):
    return templates.TemplateResponse(request, 'index.html', headers=response.headers)

# Note: this *must* be the last route defined since it's a catch-all route.
# Its purpose is to serve static files requested by frontend.
@app.get("/{full_path:path}")
async def serve_react_app(request: Request, full_path: str):
    path_to_file = os.path.join('./public', full_path)
    if 'assets' in path_to_file:
        return FileResponse(path_to_file)
    return {'message': 'failure'}

if __name__ == '__main__':
    """
    ORDER OF OPERATIONS:
    1. Navigate to http://localhost:8000. This will set the cookie
    2. Navigate to http://localhost:8000/login. This will start the authentication flow
    
    The frontend will bridge this gap, but if you're testing just using the backend you must visit the two endpoints separately.
    """
    uvicorn.run(app)
