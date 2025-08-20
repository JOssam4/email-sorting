from fastapi import APIRouter, Request, BackgroundTasks, Response
from fastapi.staticfiles import StaticFiles
from src.services import SystemService

router = APIRouter(tags=['system'])
router.mount('/public', StaticFiles(directory='public'), name='public')

@router.get('/api/priorities/{priority}')
def get_emails_with_priority(request: Request, priority: str):
    return SystemService.get_emails_with_priority(request, priority)

@router.get('/callback')
def callback(request: Request):
    return SystemService.callback(request)


@router.get('/login')
def login():
    return SystemService.login()


@router.get('/emails')
def emails_page(request: Request, background_tasks: BackgroundTasks):
    return SystemService.get_emails(request, background_tasks)


@router.get('/')
def main(request: Request, response: Response):
    return SystemService.root(request, response)


@router.get('/emails/priority/{priority}')
def serve_frontend_for_email_priorities(request: Request, response: Response):
    return SystemService.serve_frontend_for_email_priorities(request, response)

# Note: this *must* be the last route defined since it's a catch-all route.
# Its purpose is to serve static files requested by frontend.
@router.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    return SystemService.serve_frontend(full_path)