from fastapi import FastAPI

from app.api import chat, health


def create_app() -> FastAPI:
    app = FastAPI(title="Zamac Valsadae Relay")
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


app = create_app()
