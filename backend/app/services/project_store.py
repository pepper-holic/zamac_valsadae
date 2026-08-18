import json
import os
import re
import shutil
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.schemas import MediaItem, MediaItemStatus, Project, ProjectStatusSummary, Segment

_UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024

# project_id/item_id are always generated server-side as uuid.uuid4().hex
# (see create_project/add_item below), so this is the only shape a
# legitimate id ever takes. Enforcing it where ids are turned into
# filesystem paths closes off path traversal via a crafted id (e.g. one
# containing "../") coming from a URL path parameter - FastAPI's router
# does not otherwise constrain that value.
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _is_valid_id(value: str) -> bool:
    return bool(_ID_RE.match(value))


class ProjectNotFoundError(Exception):
    """프로젝트가 존재하지 않을 때 발생하는 예외"""
    pass


class ItemNotFoundError(Exception):
    """프로젝트 안에 해당 파일(아이템)이 존재하지 않을 때 발생하는 예외"""
    pass


class ProjectCorruptedError(Exception):
    """JSON 파일이 깨졌거나 Pydantic 모델 스키마와 일치하지 않을 때 발생하는 예외"""
    pass


class UploadTooLargeError(Exception):
    """업로드된 파일이 허용 최대 크기를 초과했을 때 발생하는 예외"""
    pass


MAX_HISTORY_SIZE = 20


class ProjectStore:
    def __init__(self, root_dir: Path):
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        # 아이템별 세그먼트 undo/redo 스택 - 프로세스 메모리에만 유지(재시작 시 초기화).
        self._history: dict[str, list[list[Segment]]] = {}
        self._redo: dict[str, list[list[Segment]]] = {}
        # 프로젝트별 락 - 백그라운드 전사 큐 워커와 API 요청이 같은 project.json을
        # 동시에 읽고 써서 서로의 변경을 덮어쓰지 않도록 한다 (update() 참고).
        self._project_locks: dict[str, threading.Lock] = {}
        self._project_locks_guard = threading.Lock()

    def _project_dir(self, project_id: str) -> Path:
        if not _is_valid_id(project_id):
            raise ProjectNotFoundError(project_id)
        return self._root_dir / project_id

    def _metadata_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def media_path(self, project_id: str, item_id: str) -> Path:
        if not _is_valid_id(item_id):
            raise ItemNotFoundError(item_id)
        return self._project_dir(project_id) / f"media_{item_id}"

    def rendered_media_path(self, project_id: str, item_id: str) -> Path:
        if not _is_valid_id(item_id):
            raise ItemNotFoundError(item_id)
        return self._project_dir(project_id) / f"rendered_{item_id}.mp4"

    def render_ass_path(self, project_id: str, item_id: str) -> Path:
        if not _is_valid_id(item_id):
            raise ItemNotFoundError(item_id)
        return self._project_dir(project_id) / f"render_{item_id}.ass"

    def create_project(self, name: str = "") -> Project:
        project = Project(id=uuid.uuid4().hex, name=name)
        self.save(project)
        return project

    def add_item(self, project_id: str, filename: str, media_bytes: bytes | BinaryIO) -> MediaItem:
        """Accepts either raw bytes (tests, small in-memory payloads) or a
        binary file-like object (the real upload path) - a stream is
        copied to disk in chunks via shutil.copyfileobj instead of being
        fully buffered in memory first, which matters once uploads reach
        video-file sizes (hundreds of MB to a few GB).
        """
        project = self.get(project_id)
        item_id = uuid.uuid4().hex
        media_file = self.media_path(project_id, item_id)
        media_file.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = get_settings().max_upload_bytes
        if isinstance(media_bytes, bytes):
            if len(media_bytes) > max_bytes:
                raise UploadTooLargeError(filename)
            media_file.write_bytes(media_bytes)
        else:
            written = 0
            try:
                with media_file.open("wb") as destination:
                    while chunk := media_bytes.read(_UPLOAD_CHUNK_SIZE):
                        written += len(chunk)
                        if written > max_bytes:
                            raise UploadTooLargeError(filename)
                        destination.write(chunk)
            except UploadTooLargeError:
                media_file.unlink(missing_ok=True)
                raise

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

    def get_status(self, project_id: str) -> ProjectStatusSummary:
        """Cheap alternative to get() for polling during a long-running job -
        parses the raw JSON directly and picks out only the status fields,
        skipping Pydantic's per-Segment/per-Word validation (the dominant
        cost once a file has any real transcript, since a poll runs every
        ~1.5s for the whole duration of a transcription/translation/render).
        """
        metadata_path = self._metadata_path(project_id)
        if not metadata_path.exists():
            raise ProjectNotFoundError(project_id)

        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            return ProjectStatusSummary(
                id=project_id,
                items=[
                    MediaItemStatus(
                        id=item.get("id", ""),
                        status=item.get("status", "uploaded"),
                        error=item.get("error"),
                        progress=item.get("progress"),
                        stage=item.get("stage"),
                        started_at=item.get("started_at"),
                    )
                    for item in raw.get("items", [])
                ],
            )
        except (json.JSONDecodeError, ValidationError, AttributeError) as e:
            raise ProjectCorruptedError(f"프로젝트 메타데이터를 파싱할 수 없습니다: {project_id}") from e

    def save(self, project: Project) -> None:
        """Writes project.json atomically (write to a temp file, then
        rename over the target). A crash or power loss mid-write can no
        longer leave a truncated/corrupted project.json - the rename either
        lands the old content or the new content, never a half-written
        file. Plain write_text() would truncate the file first and could
        leave it empty/partial if interrupted mid-write.
        """
        metadata_path = self._metadata_path(project.id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = metadata_path.with_name(f".{metadata_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp_path, metadata_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _lock_for(self, project_id: str) -> threading.Lock:
        with self._project_locks_guard:
            return self._project_locks.setdefault(project_id, threading.Lock())

    def update(self, project_id: str, mutate: Callable[[Project], None]) -> Project:
        """Atomically read-modify-write a project under a per-project lock.

        Plain get()-then-save() call sites race when two threads touch the
        same project around the same time (e.g. a "전사 시작" request and the
        transcription queue worker updating a sibling item) - whichever saves
        last silently overwrites the other's change. Routing a mutation
        through here serializes it against every other update() caller for
        that project. If `mutate` raises, nothing is saved.
        """
        with self._lock_for(project_id):
            project = self.get(project_id)
            mutate(project)
            self.save(project)
            return project

    def update_item(
        self, project_id: str, item_id: str, mutate: Callable[[MediaItem], None]
    ) -> MediaItem | None:
        """Like update(), but scoped to one item inside the project.

        Looks the item up fresh under the same per-project lock instead of
        mutating a long-held item reference from an earlier get() - callers
        with a long-running background job (rendering, transcription) must
        use this instead of holding onto a `Project`/`MediaItem` snapshot
        and calling save() at the end, which would silently overwrite any
        other change made to the project while the job was running.
        """

        def mutate_project(project: Project) -> None:
            item = next((i for i in project.items if i.id == item_id), None)
            if item is not None:
                mutate(item)

        project = self.update(project_id, mutate_project)
        return next((i for i in project.items if i.id == item_id), None)

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

    def _translation_memory_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "tm.json"

    def _legacy_translation_memory_paths(self, project_id: str) -> list[Path]:
        # 방향별(ko->en / en->ko)로 나뉘어 있던 이전 캐시 파일 - 번역이 언어를
        # 자동 감지하는 방식으로 바뀌면서 방향 구분이 없어졌으므로, 처음
        # 읽을 때 하나로 합쳐서 새 tm.json으로 옮긴다.
        project_dir = self._project_dir(project_id)
        return [project_dir / "tm_ko_to_en.json", project_dir / "tm_en_to_ko.json"]

    def load_translation_memory(self, project_id: str) -> dict[str, str]:
        tm_path = self._translation_memory_path(project_id)
        if not tm_path.exists():
            merged: dict[str, str] = {}
            for legacy_path in self._legacy_translation_memory_paths(project_id):
                if not legacy_path.exists():
                    continue
                try:
                    merged.update(json.loads(legacy_path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
            if merged:
                self.save_translation_memory(project_id, merged)
                return merged
            return {}
        try:
            return json.loads(tm_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # 손상된 TM 파일이 번역 자체를 막지 않도록 빈 메모리로 취급
            return {}

    def save_translation_memory(self, project_id: str, entries: dict[str, str]) -> None:
        tm_path = self._translation_memory_path(project_id)
        existing = json.loads(tm_path.read_text(encoding="utf-8")) if tm_path.exists() else {}
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
