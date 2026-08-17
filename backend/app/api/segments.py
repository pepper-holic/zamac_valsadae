from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_store
from app.models.schemas import (
    MediaItem,
    Project,
    Segment,
    SegmentBulkDeleteRequest,
    SegmentBulkUpdateRequest,
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


def _find_item(project: Project, item_id: str) -> MediaItem:
    item = next((i for i in project.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return item


def _get_project_and_item(project_id: str, item_id: str, store: ProjectStore) -> tuple[Project, MediaItem]:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    return project, _find_item(project, item_id)


def _mutate_item(
    store: ProjectStore, project_id: str, item_id: str, apply: Callable[[MediaItem], object]
) -> object:
    """Routes a segment mutation through store.update() so a segment edit
    can't race the transcription queue worker (or another edit) saving the
    same project.json concurrently and silently dropping one side's change -
    store.save() called directly, outside store.update()'s per-project
    lock, doesn't have that protection. `apply` mutates the found MediaItem
    in place and returns whatever the route should respond with.
    """
    result: list[object] = []

    def mutate(project: Project) -> None:
        item = _find_item(project, item_id)
        result.append(apply(item))

    try:
        store.update(project_id, mutate)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    return result[0]


def _apply_segment_update(segment: Segment, update: SegmentUpdate) -> Segment:
    changes = update.model_dump(exclude_unset=True, exclude_none=True)
    if "text" in changes and changes["text"] != segment.text:
        # 원문이 바뀌면 단어별 타임스탬프 정렬이 깨지므로 비운다
        # (부정확한 카라오케 강조보다 강조 없음이 안전).
        changes["words"] = []
    updated = segment.model_copy(update=changes)
    if updated.start >= updated.end:
        raise HTTPException(status_code=400, detail="시작 시간은 종료 시간보다 빨라야 합니다.")
    return updated


@router.patch("/{project_id}/items/{item_id}/segments/{segment_id}", response_model=Segment)
async def update_segment(
    project_id: str,
    item_id: str,
    segment_id: str,
    update: SegmentUpdate,
    store: ProjectStore = Depends(get_store),
) -> Segment:
    def apply(item: MediaItem) -> Segment:
        for index, segment in enumerate(item.segments):
            if segment.id == segment_id:
                updated = _apply_segment_update(segment, update)
                store.push_history(item_id, item.segments)
                item.segments[index] = updated
                return updated
        raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")

    return _mutate_item(store, project_id, item_id, apply)


@router.post("/{project_id}/items/{item_id}/segments/bulk-update", response_model=list[Segment])
async def bulk_update_segments(
    project_id: str,
    item_id: str,
    request: SegmentBulkUpdateRequest,
    store: ProjectStore = Depends(get_store),
) -> list[Segment]:
    def apply(item: MediaItem) -> list[Segment]:
        updates_by_id = {entry.id: entry.update for entry in request.updates}
        missing = updates_by_id.keys() - {segment.id for segment in item.segments}
        if missing:
            raise HTTPException(status_code=404, detail=f"세그먼트를 찾을 수 없습니다: {', '.join(missing)}")

        # Compute every new segment before mutating anything, so a validation
        # failure partway through (e.g. bad start/end) leaves item.segments and
        # the undo history untouched instead of applying half the batch.
        new_segments = [
            _apply_segment_update(segment, updates_by_id[segment.id]) if segment.id in updates_by_id else segment
            for segment in item.segments
        ]

        store.push_history(item_id, item.segments)
        item.segments = new_segments
        return [segment for segment in new_segments if segment.id in updates_by_id]

    return _mutate_item(store, project_id, item_id, apply)


@router.post("/{project_id}/items/{item_id}/segments/bulk-delete", response_model=list[Segment])
async def bulk_delete_segments(
    project_id: str,
    item_id: str,
    request: SegmentBulkDeleteRequest,
    store: ProjectStore = Depends(get_store),
) -> list[Segment]:
    def apply(item: MediaItem) -> list[Segment]:
        ids_to_delete = set(request.segment_ids)
        remaining = [segment for segment in item.segments if segment.id not in ids_to_delete]
        if len(remaining) == len(item.segments):
            raise HTTPException(status_code=404, detail="삭제할 세그먼트를 찾을 수 없습니다.")

        store.push_history(item_id, item.segments)
        item.segments = remaining
        return remaining

    return _mutate_item(store, project_id, item_id, apply)


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
    def apply(item: MediaItem) -> list[Segment]:
        for index, segment in enumerate(item.segments):
            if segment.id == segment_id:
                try:
                    first, second = segment_edit_service.split_segment(segment, request.split_at)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                store.push_history(item_id, item.segments)
                item.segments[index : index + 1] = [first, second]
                return [first, second]
        raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")

    return _mutate_item(store, project_id, item_id, apply)


@router.post("/{project_id}/items/{item_id}/segments/merge", response_model=Segment)
async def merge_segments(
    project_id: str,
    item_id: str,
    request: SegmentMergeRequest,
    store: ProjectStore = Depends(get_store),
) -> Segment:
    def apply(item: MediaItem) -> Segment:
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
        return merged

    return _mutate_item(store, project_id, item_id, apply)


@router.post("/{project_id}/items/{item_id}/segments/find-replace", response_model=list[Segment])
async def find_replace_segments(
    project_id: str,
    item_id: str,
    request: SegmentFindReplaceRequest,
    store: ProjectStore = Depends(get_store),
) -> list[Segment]:
    def apply(item: MediaItem) -> list[Segment]:
        store.push_history(item_id, item.segments)
        item.segments = segment_edit_service.find_replace(
            item.segments, field=request.field, find=request.find, replace=request.replace
        )
        return item.segments

    return _mutate_item(store, project_id, item_id, apply)


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
    def apply(item: MediaItem) -> None:
        remaining = [segment for segment in item.segments if segment.id != segment_id]
        if len(remaining) == len(item.segments):
            raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")

        store.push_history(item_id, item.segments)
        item.segments = remaining

    _mutate_item(store, project_id, item_id, apply)
    return Response(status_code=204)


@router.post("/{project_id}/items/{item_id}/undo", response_model=UndoRedoResult)
async def undo_segments(
    project_id: str,
    item_id: str,
    store: ProjectStore = Depends(get_store),
) -> UndoRedoResult:
    def apply(item: MediaItem) -> UndoRedoResult:
        previous = store.undo(item_id, item.segments)
        if previous is None:
            raise HTTPException(status_code=400, detail="되돌릴 변경사항이 없습니다.")
        item.segments = previous
        return UndoRedoResult(
            segments=previous, can_undo=store.can_undo(item_id), can_redo=store.can_redo(item_id)
        )

    return _mutate_item(store, project_id, item_id, apply)


@router.post("/{project_id}/items/{item_id}/redo", response_model=UndoRedoResult)
async def redo_segments(
    project_id: str,
    item_id: str,
    store: ProjectStore = Depends(get_store),
) -> UndoRedoResult:
    def apply(item: MediaItem) -> UndoRedoResult:
        next_state = store.redo(item_id, item.segments)
        if next_state is None:
            raise HTTPException(status_code=400, detail="다시 실행할 변경사항이 없습니다.")
        item.segments = next_state
        return UndoRedoResult(
            segments=next_state, can_undo=store.can_undo(item_id), can_redo=store.can_redo(item_id)
        )

    return _mutate_item(store, project_id, item_id, apply)
