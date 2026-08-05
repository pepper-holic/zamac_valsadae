from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import export, projects, review, segments, transcribe, translate

FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Subtitle Sync & Review Tool")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router)
    app.include_router(transcribe.router)
    app.include_router(translate.router)
    app.include_router(segments.router)
    app.include_router(export.router)
    app.include_router(review.router)

    # In production the built frontend (frontend/dist) is served from the
    # same origin as the API, so users only need to run one process and
    # visit one URL. During `npm run dev` this directory doesn't exist and
    # the routers above are hit directly from the Vite dev server instead.
    if FRONTEND_DIST_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")

    return app


app = create_app()
