import os
from http.client import HTTPException
from dns.tsig import BadSignature
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse

from Email import Email, EmailWithoutBody
from EmailAnalyzer import EmailAnalyzer
from EmailRetriever import EmailRetriever
from MySqlConnector import MySqlConnector
from Secrets import Secrets
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from redis import Redis
from itsdangerous import Signer
import uuid
import json
import uvicorn


def read_secrets_from_json() -> Secrets:
    with open('secrets.json', 'r') as f:
        secrets = json.load(f)
        gmail_api_client_secret_filename = secrets['gmail_api_client_secret_filename']
        mysql_password = secrets['mysql_password']
        return Secrets(gmail_api_client_secret_filename, mysql_password)


app = FastAPI()
secrets = read_secrets_from_json()
secrets_file = secrets.gmail_api_client_secret_filename
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SIGNING_KEY = 'READ_THIS_FROM_DOTENV'
signer = Signer(SIGNING_KEY)
SESSION_COOKIE = 'session_id'
redis_client = Redis(host='localhost', port=6379, db=0, decode_responses=True)
app.mount('/public', StaticFiles(directory='public'), name='public')
templates = Jinja2Templates(directory='./public')

def run(mysql_password: str) -> list[EmailWithoutBody]:
    """
    1. Retrieve emails
    2. Put emails in database
    3. Analyze emails
    4. Put the analysis into the database
    """
    username = email_retriever.retrieve_username()
    emails = email_retriever.retrieve_emails()

    schema_name = f'{username}_emails'
    mysql_connector = MySqlConnector(mysql_password, schema_name)
    store_emails_in_database(mysql_connector, emails)
    analyze_emails(emails)
    update_priorities_in_database(mysql_connector, emails)
    return [EmailWithoutBody(email.gmail_id, email.link, email.time_sent, email.sent_from, email.subject, email.priority) for email in emails]


def fetch_emails(gmail_api_client_secret_filename: str) -> list[Email]:
    email_retriever = EmailRetriever(gmail_api_client_secret_filename)
    emails = email_retriever.retrieve_emails()
    print('finished retrieving emails')
    return emails


def store_emails_in_database(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    mysql_connector.insert_emails(emails)
    print('finished adding emails to database')


def update_priorities_in_database(mysql_connector: MySqlConnector, emails: list[Email]) -> None:
    mysql_connector.update_priorities(emails)
    print('finished setting priorities')


def analyze_emails(emails: list[Email]) -> None:
    email_analyzer = EmailAnalyzer()
    for email in emails:
        analysis = email_analyzer.analyze_email(email)
        priority = EmailAnalyzer.get_email_priority(analysis)
        email.priority = priority


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


@app.get('/analyze_emails')
def read_analyzed_emails():
    print('ACTUALLY HIT ENDPOINT')
    # return run(secrets_filename)


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
def emails(request: Request):
    credentials_json = retrieve_credentials(request)
    email_retriever = EmailRetriever(credentials_json, SCOPES)
    username = email_retriever.retrieve_username()
    emails = email_retriever.retrieve_emails()
    return templates.TemplateResponse(request, 'index.html')


@app.get('/')
def main(request: Request, response: Response):
    create_session(response)
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
    # read_analyzed_emails()
    # secrets = read_secrets_from_json()
    # run(secrets.gmail_api_client_secret_filename, secrets.mysql_password)
    """
    ORDER OF OPERATIONS:
    1. Navigate to http://localhost:8000. This will set the cookie
    2. Navigate to http://localhost:8000/login. This will start the authentication flow
    
    The frontend will be responsible for bridging this gap, but for now you must visit the two endpoints separately.
    """
    uvicorn.run(app)
