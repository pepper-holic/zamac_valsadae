import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.deps import get_store
from app.models.schemas import ReviewImportResult
from app.services.project_store import ProjectNotFoundError, ProjectStore
from app.services.review_service import build_review_package, diff_review_import

router = APIRouter(prefix="/projects", tags=["review"])


@router.get("/{project_id}/review-package")
async def get_review_package(project_id: str, store: ProjectStore = Depends(get_store)) -> Response:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc

    package = build_review_package(
        project_id=project.id, media_filename=project.filename, segments=project.segments
    )
    body = package.model_dump_json(indent=2)
    filename = f"{project.filename.rsplit('.', 1)[0]}-review.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/review-import", response_model=ReviewImportResult)
async def import_review_package(
    project_id: str, file: UploadFile, store: ProjectStore = Depends(get_store)
) -> ReviewImportResult:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc

    raw_bytes = await file.read()
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="유효한 JSON 파일이 아닙니다.") from exc

    imported_segments = payload.get("segments", payload if isinstance(payload, list) else [])
    return diff_review_import(project.segments, imported_segments)
