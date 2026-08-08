from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_store
from app.models.schemas import (
    MediaItem,
    Project,
    Segment,
    SegmentDetectFillersRequest,
    SegmentFindReplaceRequest,
    SegmentMergeRequest,
    SegmentSplitRequest,
    SegmentUpdate,
    UndoRedoResult,
)
from app.services import segment_edit_service
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["segments"])


def _get_project_and_item(project_id: str, item_id: str, store: ProjectStore) -> tuple[Project, MediaItem]:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return project, item


@router.patch("/{project_id}/items/{item_id}/segments/{segment_id}", response_model=Segment)
async def update_segment(
    project_id: str,
    item_id: str,
    segment_id: str,
    update: SegmentUpdate,
    store: ProjectStore = Depends(get_store),
) -> Segment:
    project, item = _get_project_and_item(project_id, item_id, store)

    for index, segment in enumerate(item.segments):
        if segment.id == segment_id:
            updated = segment.model_copy(
                update=update.model_dump(exclude_unset=True, exclude_none=True)
            )
            if updated.start >= updated.end:
                raise HTTPException(
                    status_code=400, detail="시작 시간은 종료 시간보다 빨라야 합니다."
                )
            store.push_history(item_id, item.segments)
            item.segments[index] = updated
            store.save(project)
            return updated

    raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")


@router.post(
    "/{project_id}/items/{item_id}/segments/{segment_id}/split", response_model=list[Segment]
)
async def split_segment(
    project_id: str,
    item_id: str,
    segment_id: str,
    request: SegmentSplitRequest,
    store: ProjectStore = Depends(get_store),
) -> list[Segment]:
    project, item = _get_project_and_item(project_id, item_id, store)

    for index, segment in enumerate(item.segments):
        if segment.id == segment_id:
            try:
                first, second = segment_edit_service.split_segment(segment, request.split_at)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            store.push_history(item_id, item.segments)
            item.segments[index : index + 1] = [first, second]
            store.save(project)
            return [first, second]

    raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")


@router.post("/{project_id}/items/{item_id}/segments/merge", response_model=Segment)
async def merge_segments(
    project_id: str,
    item_id: str,
    request: SegmentMergeRequest,
    store: ProjectStore = Depends(get_store),
) -> Segment:
    project, item = _get_project_and_item(project_id, item_id, store)

    to_merge = [segment for segment in item.segments if segment.id in request.segment_ids]
    if len(to_merge) != len(request.segment_ids):
        raise HTTPException(status_code=404, detail="일부 세그먼트를 찾을 수 없습니다.")

    try:
        merged = segment_edit_service.merge_segments(to_merge)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    insert_at = min(
        index for index, segment in enumerate(item.segments) if segment.id in request.segment_ids
    )
    store.push_history(item_id, item.segments)
    item.segments = [
        segment for segment in item.segments if segment.id not in request.segment_ids
    ]
    item.segments.insert(insert_at, merged)
    store.save(project)
    return merged


@router.post("/{project_id}/items/{item_id}/segments/find-replace", response_model=list[Segment])
async def find_replace_segments(
    project_id: str,
    item_id: str,
    request: SegmentFindReplaceRequest,
    store: ProjectStore = Depends(get_store),
) -> list[Segment]:
    project, item = _get_project_and_item(project_id, item_id, store)

    store.push_history(item_id, item.segments)
    item.segments = segment_edit_service.find_replace(
        item.segments, field=request.field, find=request.find, replace=request.replace
    )
    store.save(project)
    return item.segments


@router.post("/{project_id}/items/{item_id}/segments/detect-fillers", response_model=list[str])
async def detect_filler_segments(
    project_id: str,
    item_id: str,
    request: SegmentDetectFillersRequest,
    store: ProjectStore = Depends(get_store),
) -> list[str]:
    _, item = _get_project_and_item(project_id, item_id, store)

    return segment_edit_service.find_filler_segments(item.segments, language=request.language)


@router.delete("/{project_id}/items/{item_id}/segments/{segment_id}", status_code=204)
async def delete_segment(
    project_id: str,
    item_id: str,
    segment_id: str,
    store: ProjectStore = Depends(get_store),
) -> Response:
    project, item = _get_project_and_item(project_id, item_id, store)

    remaining = [segment for segment in item.segments if segment.id != segment_id]
    if len(remaining) == len(item.segments):
        raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")

    store.push_history(item_id, item.segments)
    item.segments = remaining
    store.save(project)
    return Response(status_code=204)


@router.post("/{project_id}/items/{item_id}/undo", response_model=UndoRedoResult)
async def undo_segments(
    project_id: str,
    item_id: str,
    store: ProjectStore = Depends(get_store),
) -> UndoRedoResult:
    project, item = _get_project_and_item(project_id, item_id, store)

    previous = store.undo(item_id, item.segments)
    if previous is None:
        raise HTTPException(status_code=400, detail="되돌릴 변경사항이 없습니다.")

    item.segments = previous
    store.save(project)
    return UndoRedoResult(
        segments=previous, can_undo=store.can_undo(item_id), can_redo=store.can_redo(item_id)
    )


@router.post("/{project_id}/items/{item_id}/redo", response_model=UndoRedoResult)
async def redo_segments(
    project_id: str,
    item_id: str,
    store: ProjectStore = Depends(get_store),
) -> UndoRedoResult:
    project, item = _get_project_and_item(project_id, item_id, store)

    next_state = store.redo(item_id, item.segments)
    if next_state is None:
        raise HTTPException(status_code=400, detail="다시 실행할 변경사항이 없습니다.")

    item.segments = next_state
    store.save(project)
    return UndoRedoResult(
        segments=next_state, can_undo=store.can_undo(item_id), can_redo=store.can_redo(item_id)
    )
