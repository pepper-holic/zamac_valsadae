import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, export, models, projects, review, segments, transcribe, translate
from app.api.deps import get_store
from app.services.project_store import ProjectStore

# Nothing else in the app configures logging, so app.* loggers (whisper_service's
# per-region transcription progress, etc.) fall through to Python's WARNING-level
# "handler of last resort" and never show up - INFO-level progress needs an
# explicit level+handler to actually reach it. The desktop build
# (app/desktop.py) runs under pythonw.exe with no console at all, so
# sys.stderr is None there and a console-only handler would silently produce
# nothing visible - a file next to desktop_error.log is what actually lets
# the user open and read it regardless of how the app was launched.
LOG_FILE_PATH = Path(__file__).resolve().parents[1] / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")],
)
logger = logging.getLogger(__name__)

FRONTEND_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

_INTERRUPTED_STATUSES = ("queued", "transcribing", "translating", "rendering")
_INTERRUPTED_MESSAGE = "서버가 재시작되어 작업이 중단되었습니다. 다시 시도해주세요."


def recover_interrupted_projects(store: ProjectStore) -> None:
    """Background tasks (transcribe/translate) run in-process, so a server
    restart silently kills whatever was running - the item's status stays
    stuck at "transcribing"/"translating" forever with no process left to
    finish it. Mark those as failed on startup so the user sees a clear
    error and can retry, instead of a progress bar that never moves again.
    """
    for project in store.list():
        changed = False
        for item in project.items:
            if item.status in _INTERRUPTED_STATUSES:
                item.status = "error"
                item.stage = None
                item.progress = None
                item.started_at = None
                item.error = _INTERRUPTED_MESSAGE
                changed = True
        if changed:
            store.save(project)


def create_app() -> FastAPI:
    app = FastAPI(title="Subtitle Sync & Review Tool")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # FastAPI's default handlers already cover HTTPException/validation
        # errors with proper 4xx bodies - this only fires for genuinely
        # unhandled exceptions, which would otherwise surface to the browser
        # as a bare, unlogged 500 with no JSON body (and, under pythonw.exe's
        # headless desktop build, easy to miss entirely without app.log).
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다."})

    @app.on_event("startup")
    async def _recover_interrupted_projects_on_startup() -> None:
        recover_interrupted_projects(get_store())

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(models.router)
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
