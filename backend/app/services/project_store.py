import shutil
import uuid
from pathlib import Path
from pydantic import ValidationError

from app.models.schemas import Project


class ProjectNotFoundError(Exception):
    """프로젝트가 존재하지 않을 때 발생하는 예외"""
    pass


class ProjectCorruptedError(Exception):
    """JSON 파일이 깨졌거나 Pydantic 모델 스키마와 일치하지 않을 때 발생하는 예외"""
    pass


class ProjectStore:
    def __init__(self, root_dir: Path):
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        return self._root_dir / project_id

    def _metadata_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def media_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "media"

    def create(self, filename: str, media_bytes: bytes) -> Project:
        project_id = uuid.uuid4().hex
        project_dir = self._project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        media_file = self.media_path(project_id)
        media_file.write_bytes(media_bytes)

        project = Project(
            id=project_id,
            filename=filename,
            media_path=str(media_file),
            status="uploaded",
        )
        self.save(project)
        return project

    def get(self, project_id: str) -> Project:
        metadata_path = self._metadata_path(project_id)
        if not metadata_path.exists():
            raise ProjectNotFoundError(project_id)

        try:
            return Project.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        except (ValidationError, Exception) as e:
            raise ProjectCorruptedError(f"프로젝트 메타데이터를 파싱할 수 없습니다: {project_id}") from e

    def save(self, project: Project) -> None:
        metadata_path = self._metadata_path(project.id)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")

    def delete(self, project_id: str) -> None:
        project_dir = self._project_dir(project_id)
        if not self._metadata_path(project_id).exists():
            raise ProjectNotFoundError(project_id)
        shutil.rmtree(project_dir)

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