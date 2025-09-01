from collections.abc import Callable
from src.services import system_service
from src.routers.api import router
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()


@app.middleware('http')
def remove_trailing_slash(request: Request, call_next: Callable):
    return system_service.remove_trailing_slash(request, call_next)


if __name__ == '__main__':
    app.include_router(router)
    uvicorn.run(app)
