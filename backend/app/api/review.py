import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.deps import get_store
from app.models.schemas import ReviewImportResult
from app.services.project_store import ProjectNotFoundError, ProjectStore
from app.services.review_service import (
    build_compact_review_package,
    build_review_package,
    diff_compact_review_import,
    diff_review_import,
)

router = APIRouter(prefix="/projects", tags=["review"])


@router.get("/{project_id}/items/{item_id}/review-package")
async def get_review_package(
    project_id: str, item_id: str, compact: bool = False, store: ProjectStore = Depends(get_store)
) -> Response:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    if compact:
        package = build_compact_review_package(
            item_id=item.id, media_filename=item.filename, segments=item.segments
        )
        filename = f"{item.filename.rsplit('.', 1)[0]}-review-compact.json"
    else:
        package = build_review_package(
            item_id=item.id, media_filename=item.filename, segments=item.segments
        )
        filename = f"{item.filename.rsplit('.', 1)[0]}-review.json"

    body = package.model_dump_json(indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/items/{item_id}/review-import", response_model=ReviewImportResult)
async def import_review_package(
    project_id: str, item_id: str, file: UploadFile, store: ProjectStore = Depends(get_store)
) -> ReviewImportResult:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    raw_bytes = await file.read()
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="유효한 JSON 파일이 아닙니다.") from exc

    imported_groups = payload.get("groups")
    if imported_groups is not None:
        return diff_compact_review_import(item.segments, imported_groups)

    imported_segments = payload.get("segments", payload if isinstance(payload, list) else [])
    return diff_review_import(item.segments, imported_segments)
