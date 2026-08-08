from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_store
from app.models.schemas import (
    GlossaryUpdate,
    MediaItem,
    NamedSubtitleStyle,
    Project,
    ProjectCreate,
    StylePresetCreate,
    SubtitleStyle,
)
from app.services import cancellation
from app.services.project_store import (
    ItemNotFoundError,
    ProjectCorruptedError,
    ProjectNotFoundError,
    ProjectStore,
)

_CANCELLABLE_STATUSES = ("transcribing", "translating", "rendering")

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project)
async def create_project(
    request: ProjectCreate = ProjectCreate(), store: ProjectStore = Depends(get_store)
) -> Project:
    return store.create_project(name=request.name)


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


@router.put("/{project_id}/glossary", response_model=Project)
async def update_glossary(
    project_id: str, request: GlossaryUpdate, store: ProjectStore = Depends(get_store)
) -> Project:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    project.glossary = request.glossary
    store.save(project)
    return project


@router.put("/{project_id}/style", response_model=Project)
async def update_style(
    project_id: str, style: SubtitleStyle, store: ProjectStore = Depends(get_store)
) -> Project:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    project.subtitle_style = style
    store.save(project)
    return project


@router.post("/{project_id}/style/presets", response_model=Project)
async def create_style_preset(
    project_id: str, request: StylePresetCreate, store: ProjectStore = Depends(get_store)
) -> Project:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    preset = NamedSubtitleStyle(name=request.name, style=request.style)
    project.style_presets = [p for p in project.style_presets if p.name != request.name] + [preset]
    store.save(project)
    return project


@router.delete("/{project_id}/style/presets/{name}", response_model=Project)
async def delete_style_preset(
    project_id: str, name: str, store: ProjectStore = Depends(get_store)
) -> Project:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    remaining = [p for p in project.style_presets if p.name != name]
    if len(remaining) == len(project.style_presets):
        raise HTTPException(status_code=404, detail="프리셋을 찾을 수 없습니다.")
    project.style_presets = remaining
    store.save(project)
    return project


@router.post("/{project_id}/items", response_model=MediaItem)
async def add_item(
    project_id: str, file: UploadFile, store: ProjectStore = Depends(get_store)
) -> MediaItem:
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 필요합니다.")
    media_bytes = await file.read()
    try:
        return store.add_item(project_id, filename=file.filename, media_bytes=media_bytes)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc


@router.delete("/{project_id}/items/{item_id}", status_code=204)
async def delete_item(
    project_id: str, item_id: str, store: ProjectStore = Depends(get_store)
) -> Response:
    try:
        store.remove_item(project_id, item_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.") from exc
    return Response(status_code=204)


@router.post("/{project_id}/items/{item_id}/cancel", response_model=MediaItem)
async def cancel_item_operation(
    project_id: str, item_id: str, store: ProjectStore = Depends(get_store)
) -> MediaItem:
    try:
        item = store.get_item(project_id, item_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.") from exc
    if item.status not in _CANCELLABLE_STATUSES:
        raise HTTPException(status_code=400, detail="현재 진행 중인 작업이 없습니다.")
    cancellation.request_cancel(item_id)
    return item


@router.get("/{project_id}/items/{item_id}/media")
async def get_item_media(
    project_id: str, item_id: str, store: ProjectStore = Depends(get_store)
) -> FileResponse:
    try:
        item = store.get_item(project_id, item_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.") from exc
    return FileResponse(store.media_path(project_id, item_id), filename=item.filename)
