from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_store
from app.models.schemas import Segment, SegmentUpdate
from app.services.project_store import ProjectNotFoundError, ProjectStore

router = APIRouter(prefix="/projects", tags=["segments"])


@router.patch("/{project_id}/segments/{segment_id}", response_model=Segment)
async def update_segment(
    project_id: str,
    segment_id: str,
    update: SegmentUpdate,
    store: ProjectStore = Depends(get_store),
) -> Segment:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc

    for index, segment in enumerate(project.segments):
        if segment.id == segment_id:
            updated = segment.model_copy(
                update=update.model_dump(exclude_unset=True, exclude_none=True)
            )
            if updated.start >= updated.end:
                raise HTTPException(
                    status_code=400, detail="시작 시간은 종료 시간보다 빨라야 합니다."
                )
            project.segments[index] = updated
            store.save(project)
            return updated

    raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")


@router.delete("/{project_id}/segments/{segment_id}", status_code=204)
async def delete_segment(
    project_id: str,
    segment_id: str,
    store: ProjectStore = Depends(get_store),
) -> Response:
    try:
        project = store.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc

    remaining = [segment for segment in project.segments if segment.id != segment_id]
    if len(remaining) == len(project.segments):
        raise HTTPException(status_code=404, detail="세그먼트를 찾을 수 없습니다.")

    project.segments = remaining
    store.save(project)
    return Response(status_code=204)
