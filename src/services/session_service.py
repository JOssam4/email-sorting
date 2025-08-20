import uuid
from datetime import timedelta

from fastapi import Request, Response, HTTPException
from itsdangerous import Signer, BadSignature
from redis import Redis

from src.model.secrets import Secrets

secrets = Secrets.from_env()
SIGNING_KEY = secrets.signing_key
SESSION_COOKIE = 'session_id'
signer = Signer(SIGNING_KEY)


class SessionService:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def create_session(self, response: Response) -> None:
        session_id = str(uuid.uuid4())
        signed_session_id = signer.sign(session_id).decode()
        self.redis_client.hset(f'session:{session_id}', mapping={'credentials': ''})
        response.set_cookie(key=SESSION_COOKIE, value=signed_session_id, httponly=True, max_age=3600)

    def retrieve_credentials(self, request: Request) -> str:
        signed_session_id = request.cookies.get(SESSION_COOKIE)
        if not signed_session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            session_id = signer.unsign(signed_session_id).decode()
        except BadSignature:
            raise HTTPException(status_code=401, detail='Invalid session cookie')
        credentials = self.redis_client.hget(f'session:{session_id}', 'credentials')
        if not credentials:
            raise HTTPException(status_code=401, detail='Session expired or invalid')
        return credentials

    def set_credentials(self, request: Request, credentials_json: str) -> None:
        signed_session_id = request.cookies.get(SESSION_COOKIE)
        if not signed_session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            session_id = signer.unsign(signed_session_id).decode()
        except BadSignature:
            raise HTTPException(status_code=401, detail='Invalid session cookie')

        hash_name = f'session:{session_id}'
        self.redis_client.hset(hash_name, mapping={'credentials': credentials_json})
        self.redis_client.expire(hash_name, timedelta(hours=1))
