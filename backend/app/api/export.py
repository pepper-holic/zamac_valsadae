import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.deps import get_store
from app.models.schemas import ExportFormat, ExportTextMode, MediaItem, Project, RenderRequest
from app.services import cancellation, render_service
from app.services.progress_reporter import make_progress_reporter
from app.services.http_headers import content_disposition_attachment
from app.services.project_store import ProjectNotFoundError, ProjectStore
from app.services.subtitle_format import to_ass, to_json, to_srt, to_ttml, to_vtt

router = APIRouter(prefix="/projects", tags=["export"])
logger = logging.getLogger(__name__)

_CONTENT_TYPES = {
    "srt": "application/x-subrip",
    "vtt": "text/vtt",
    "json": "application/json",
    "ass": "text/x-ssa",
    "ttml": "application/ttml+xml",
}

_FILENAME_SUFFIXES: dict[ExportTextMode, str] = {
    "original": "",
    "translation": "_translated",
    "combined": "_combined",
}


def _get_project_and_item(
    project_id: str, item_id: str, store: ProjectStore
) -> tuple[Project, MediaItem]:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return project, item


def _run_render(
    project_id: str, item_id: str, use_translation: bool, cut_deleted: bool, store: ProjectStore
) -> None:
    # Read once to build the .ass file and probe duration - safe, since
    # neither depends on edits made to the project while rendering runs.
    # The *write-back* below must not reuse this snapshot (see
    # ProjectStore.update_item docstring) or a segment edit made during the
    # render would be silently discarded when this finishes.
    project = store.get(project_id)
    item = next(i for i in project.items if i.id == item_id)
    ass_path = store.render_ass_path(project_id, item_id)
    output_path = store.rendered_media_path(project_id, item_id)
    try:
        cut_list = render_service.build_cut_list(item.segments) if cut_deleted else None
        if cut_list is not None:
            duration = sum(end - start for start, end in cut_list)
        else:
            duration = render_service.probe_duration_seconds(Path(item.media_path))
        ass_content = render_service.build_ass(
            item.segments,
            project.subtitle_style,
            use_translation=use_translation,
            cut_list=cut_list,
        )
        ass_path.write_text(ass_content, encoding="utf-8")
        render_service.render(
            media_path=Path(item.media_path),
            ass_path=ass_path,
            output_path=output_path,
            duration_seconds=duration,
            on_progress=make_progress_reporter(project_id, item_id, store),
            should_cancel=lambda: cancellation.is_cancelled(item_id),
            cut_list=cut_list,
        )

        def _mark_rendered(target: MediaItem) -> None:
            target.rendered_path = str(output_path)
            target.status = "rendered"
            target.progress = 1.0
            target.stage = None
            target.started_at = None
            target.error = None

        store.update_item(project_id, item_id, _mark_rendered)
    except render_service.RenderCancelled:

        def _mark_cancelled(target: MediaItem) -> None:
            target.status = "error"
            target.stage = None
            target.started_at = None
            target.progress = None
            target.error = "사용자가 렌더링을 취소했습니다."

        store.update_item(project_id, item_id, _mark_cancelled)
    except Exception as exc:  # pragma: no cover - depends on ffmpeg availability
        logger.exception("Render failed for item %s", item_id)

        def _mark_failed(target: MediaItem) -> None:
            target.status = "error"
            target.stage = None
            target.started_at = None
            target.error = str(exc)

        store.update_item(project_id, item_id, _mark_failed)
    finally:
        cancellation.clear_cancel(item_id)
        ass_path.unlink(missing_ok=True)


@router.post("/{project_id}/items/{item_id}/render", response_model=MediaItem)
async def render_item(
    project_id: str,
    item_id: str,
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> MediaItem:
    _project, item = _get_project_and_item(project_id, item_id, store)
    if not item.segments:
        raise HTTPException(status_code=400, detail="자막이 없어 렌더링할 수 없습니다.")

    cancellation.clear_cancel(item_id)

    def _mark_rendering(target: MediaItem) -> None:
        target.status = "rendering"
        target.stage = "rendering"
        target.progress = 0.0
        target.started_at = time.time()
        target.error = None

    item = store.update_item(project_id, item_id, _mark_rendering) or item

    background_tasks.add_task(
        _run_render, project_id, item_id, request.use_translation, request.cut_deleted, store
    )
    return item


@router.get("/{project_id}/items/{item_id}/rendered")
async def download_rendered_video(
    project_id: str, item_id: str, store: ProjectStore = Depends(get_store)
) -> FileResponse:
    project, item = _get_project_and_item(project_id, item_id, store)
    if not item.rendered_path:
        raise HTTPException(status_code=404, detail="렌더링된 영상이 없습니다.")
    filename = f"{item.filename.rsplit('.', 1)[0]}_burned.mp4"
    return FileResponse(item.rendered_path, filename=filename)


@router.get("/{project_id}/items/{item_id}/export")
async def export_item(
    project_id: str,
    item_id: str,
    format: ExportFormat = Query("srt"),
    mode: ExportTextMode = Query("original"),
    store: ProjectStore = Depends(get_store),
) -> Response:
    project, item = _get_project_and_item(project_id, item_id, store)
    use_translation = mode == "translation"
    combined = mode == "combined"

    if format == "srt":
        body = to_srt(
            item.segments, use_translation=use_translation, style=project.subtitle_style, combined=combined
        )
    elif format == "vtt":
        body = to_vtt(
            item.segments, use_translation=use_translation, style=project.subtitle_style, combined=combined
        )
    elif format == "ass":
        body = to_ass(
            item.segments, use_translation=use_translation, style=project.subtitle_style, combined=combined
        )
    elif format == "ttml":
        body = to_ttml(
            item.segments, use_translation=use_translation, style=project.subtitle_style, combined=combined
        )
    else:
        body = json.dumps(to_json(item.segments), ensure_ascii=False, indent=2)

    suffix = _FILENAME_SUFFIXES[mode] if format != "json" else ""
    filename = f"{item.filename.rsplit('.', 1)[0]}{suffix}.{format}"
    return Response(
        content=body,
        media_type=_CONTENT_TYPES[format],
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )
