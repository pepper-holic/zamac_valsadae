from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_store
from app.models.schemas import Project
from app.services.project_store import (
    ProjectCorruptedError,
    ProjectNotFoundError,
    ProjectStore,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project)
async def create_project(file: UploadFile, store: ProjectStore = Depends(get_store)) -> Project:
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 필요합니다.")
    media_bytes = await file.read()
    return store.create(filename=file.filename, media_bytes=media_bytes)


@router.get("", response_model=list[Project])
async def list_projects(store: ProjectStore = Depends(get_store)) -> list[Project]:
    return store.list()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, store: ProjectStore = Depends(get_store)) -> Project:
    try:
        return store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ProjectCorruptedError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, store: ProjectStore = Depends(get_store)) -> Response:
    try:
        store.delete(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    return Response(status_code=204)


@router.get("/{project_id}/media")
async def get_project_media(project_id: str, store: ProjectStore = Depends(get_store)) -> FileResponse:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ProjectCorruptedError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(store.media_path(project_id), filename=project.filename)