import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.api.deps import get_store
from app.models.schemas import ExportFormat, MediaItem, Project, RenderRequest
from app.services import cancellation, render_service
from app.services.progress_reporter import make_progress_reporter
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
            on_progress=make_progress_reporter(project, item, store),
            should_cancel=lambda: cancellation.is_cancelled(item_id),
            cut_list=cut_list,
        )
        item.rendered_path = str(output_path)
        item.status = "rendered"
        item.progress = 1.0
        item.stage = None
        item.error = None
    except render_service.RenderCancelled:
        item.status = "error"
        item.stage = None
        item.progress = None
        item.error = "사용자가 렌더링을 취소했습니다."
    except Exception as exc:  # pragma: no cover - depends on ffmpeg availability
        logger.exception("Render failed for item %s", item_id)
        item.status = "error"
        item.stage = None
        item.error = str(exc)
    finally:
        cancellation.clear_cancel(item_id)
        ass_path.unlink(missing_ok=True)
    store.save(project)


@router.post("/{project_id}/items/{item_id}/render", response_model=MediaItem)
async def render_item(
    project_id: str,
    item_id: str,
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    store: ProjectStore = Depends(get_store),
) -> MediaItem:
    project, item = _get_project_and_item(project_id, item_id, store)
    if not item.segments:
        raise HTTPException(status_code=400, detail="자막이 없어 렌더링할 수 없습니다.")

    cancellation.clear_cancel(item_id)
    item.status = "rendering"
    item.stage = "rendering"
    item.progress = 0.0
    item.error = None
    store.save(project)

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
    use_translation: bool = Query(False),
    store: ProjectStore = Depends(get_store),
) -> Response:
    _project, item = _get_project_and_item(project_id, item_id, store)

    if format == "srt":
        body = to_srt(item.segments, use_translation=use_translation)
    elif format == "vtt":
        body = to_vtt(item.segments, use_translation=use_translation)
    elif format == "ass":
        body = to_ass(item.segments, use_translation=use_translation)
    elif format == "ttml":
        body = to_ttml(item.segments, use_translation=use_translation)
    else:
        body = json.dumps(to_json(item.segments), ensure_ascii=False, indent=2)

    filename = f"{item.filename.rsplit('.', 1)[0]}.{format}"
    return Response(
        content=body,
        media_type=_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
