import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import get_store
from app.models.schemas import ExportFormat
from app.services.project_store import ProjectNotFoundError, ProjectStore
from app.services.subtitle_format import to_ass, to_json, to_srt, to_ttml, to_vtt

router = APIRouter(prefix="/projects", tags=["export"])

_CONTENT_TYPES = {
    "srt": "application/x-subrip",
    "vtt": "text/vtt",
    "json": "application/json",
    "ass": "text/x-ssa",
    "ttml": "application/ttml+xml",
}


@router.get("/{project_id}/items/{item_id}/export")
async def export_item(
    project_id: str,
    item_id: str,
    format: ExportFormat = Query("srt"),
    use_translation: bool = Query(False),
    store: ProjectStore = Depends(get_store),
) -> Response:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

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
