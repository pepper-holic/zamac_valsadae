import json
import shutil
import uuid
from pathlib import Path
from pydantic import ValidationError

from app.models.schemas import MediaItem, Project, Segment


class ProjectNotFoundError(Exception):
    """프로젝트가 존재하지 않을 때 발생하는 예외"""
    pass


class ItemNotFoundError(Exception):
    """프로젝트 안에 해당 파일(아이템)이 존재하지 않을 때 발생하는 예외"""
    pass


class ProjectCorruptedError(Exception):
    """JSON 파일이 깨졌거나 Pydantic 모델 스키마와 일치하지 않을 때 발생하는 예외"""
    pass


MAX_HISTORY_SIZE = 20


class ProjectStore:
    def __init__(self, root_dir: Path):
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        # 아이템별 세그먼트 undo/redo 스택 - 프로세스 메모리에만 유지(재시작 시 초기화).
        self._history: dict[str, list[list[Segment]]] = {}
        self._redo: dict[str, list[list[Segment]]] = {}

    def _project_dir(self, project_id: str) -> Path:
        return self._root_dir / project_id

    def _metadata_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def media_path(self, project_id: str, item_id: str) -> Path:
        return self._project_dir(project_id) / f"media_{item_id}"

    def rendered_media_path(self, project_id: str, item_id: str) -> Path:
        return self._project_dir(project_id) / f"rendered_{item_id}.mp4"

    def render_ass_path(self, project_id: str, item_id: str) -> Path:
        return self._project_dir(project_id) / f"render_{item_id}.ass"

    def create_project(self, name: str = "") -> Project:
        project = Project(id=uuid.uuid4().hex, name=name)
        self.save(project)
        return project

    def add_item(self, project_id: str, filename: str, media_bytes: bytes) -> MediaItem:
        project = self.get(project_id)
        item_id = uuid.uuid4().hex
        media_file = self.media_path(project_id, item_id)
        media_file.parent.mkdir(parents=True, exist_ok=True)
        media_file.write_bytes(media_bytes)

        item = MediaItem(
            id=item_id, filename=filename, media_path=str(media_file), status="uploaded"
        )
        project.items.append(item)
        self.save(project)
        return item

    def remove_item(self, project_id: str, item_id: str) -> None:
        project = self.get(project_id)
        remaining = [item for item in project.items if item.id != item_id]
        if len(remaining) == len(project.items):
            raise ItemNotFoundError(item_id)

        media_file = self.media_path(project_id, item_id)
        media_file.unlink(missing_ok=True)
        project.items = remaining
        self.save(project)
        self._discard_history(item_id)

    def get(self, project_id: str) -> Project:
        metadata_path = self._metadata_path(project_id)
        if not metadata_path.exists():
            raise ProjectNotFoundError(project_id)

        try:
            return Project.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except (ValidationError, Exception) as e:
            raise ProjectCorruptedError(f"프로젝트 메타데이터를 파싱할 수 없습니다: {project_id}") from e

    def get_item(self, project_id: str, item_id: str) -> MediaItem:
        project = self.get(project_id)
        for item in project.items:
            if item.id == item_id:
                return item
        raise ItemNotFoundError(item_id)

    def save(self, project: Project) -> None:
        metadata_path = self._metadata_path(project.id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")

    def delete(self, project_id: str) -> None:
        project_dir = self._project_dir(project_id)
        if not self._metadata_path(project_id).exists():
            raise ProjectNotFoundError(project_id)
        project = self.get(project_id)
        shutil.rmtree(project_dir)
        for item in project.items:
            self._discard_history(item.id)

    def _discard_history(self, item_id: str) -> None:
        self._history.pop(item_id, None)
        self._redo.pop(item_id, None)

    def push_history(self, item_id: str, segments: list[Segment]) -> None:
        stack = self._history.setdefault(item_id, [])
        stack.append(list(segments))
        if len(stack) > MAX_HISTORY_SIZE:
            del stack[0]
        self._redo[item_id] = []

    def undo(self, item_id: str, current_segments: list[Segment]) -> list[Segment] | None:
        stack = self._history.get(item_id, [])
        if not stack:
            return None
        previous = stack.pop()
        self._redo.setdefault(item_id, []).append(list(current_segments))
        return previous

    def redo(self, item_id: str, current_segments: list[Segment]) -> list[Segment] | None:
        stack = self._redo.get(item_id, [])
        if not stack:
            return None
        next_state = stack.pop()
        self._history.setdefault(item_id, []).append(list(current_segments))
        return next_state

    def can_undo(self, item_id: str) -> bool:
        return bool(self._history.get(item_id))

    def can_redo(self, item_id: str) -> bool:
        return bool(self._redo.get(item_id))

    def _translation_memory_path(self, project_id: str, direction: str) -> Path:
        safe_direction = direction.replace("->", "_to_")
        return self._project_dir(project_id) / f"tm_{safe_direction}.json"

    def load_translation_memory(self, project_id: str, direction: str) -> dict[str, str]:
        tm_path = self._translation_memory_path(project_id, direction)
        if not tm_path.exists():
            return {}
        try:
            return json.loads(tm_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 손상된 TM 파일이 번역 자체를 막지 않도록 빈 메모리로 취급
            return {}

    def save_translation_memory(
        self, project_id: str, direction: str, entries: dict[str, str]
    ) -> None:
        tm_path = self._translation_memory_path(project_id, direction)
        existing = self.load_translation_memory(project_id, direction)
        merged = {**existing, **entries}
        tm_path.parent.mkdir(parents=True, exist_ok=True)
        tm_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    def list(self) -> list[Project]:
        if not self._root_dir.exists():
            return []
        projects = []
        for entry in self._root_dir.iterdir():
            metadata_path = entry / "project.json"
            if metadata_path.exists():
                try:
                    projects.append(Project.model_validate_json(metadata_path.read_text(encoding="utf-8")))
                except Exception:
                    # 손상된 project.json 파일이 있더라도 전체 목록 조회가 멈추지 않도록 스킵
                    continue
        return projects
