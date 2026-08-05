from typing import Literal
from pydantic import BaseModel, Field

ProjectStatus = Literal[
    "uploaded",
    "transcribing",
    "transcribed",
    "translating",
    "translated",
    "error",
]

TranslationDirection = Literal["ko->en", "en->ko"]
TranslationEngine = Literal["local", "api"]
ExportFormat = Literal["srt", "vtt", "json"]
QualityFlag = Literal["good", "check"]


class Segment(BaseModel):
    id: str
    start: float = 0.0  # 기본값 설정으로 누락 시 에러 방지
    end: float = 0.0    # 기본값 설정으로 누락 시 에러 방지
    text: str = ""      # 기본값 설정으로 누락 시 에러 방지
    translation: str | None = None
    transcription_quality: QualityFlag | None = None
    transcription_quality_reason: str | None = None
    translation_quality: QualityFlag | None = None
    translation_quality_reason: str | None = None
    reviewed: bool = False


class Project(BaseModel):
    id: str
    filename: str = ""       # 하위 호환성을 위해 기본값 추가
    media_path: str = ""     # 하위 호환성을 위해 기본값 추가
    status: ProjectStatus = "uploaded"
    whisper_model: str | None = None
    error: str | None = None
    progress: float | None = None
    segments: list[Segment] = Field(default_factory=list)


class TranscribeRequest(BaseModel):
    model: str = "small"


class TranslateRequest(BaseModel):
    direction: TranslationDirection
    engine: TranslationEngine = "local"


class SegmentUpdate(BaseModel):
    text: str | None = None
    translation: str | None = None
    start: float | None = None
    end: float | None = None
    reviewed: bool | None = None


class ReviewSegment(BaseModel):
    id: str
    start: float = 0.0
    end: float = 0.0
    text: str = ""
    translation: str | None = None


class ReviewPackage(BaseModel):
    project_id: str
    media_filename: str
    instructions: str
    segments: list[ReviewSegment] = Field(default_factory=list)


class ReviewDiffEntry(BaseModel):
    id: str
    field: str  # Literal 제약 완화로 동적 필드 지원 및 파싱 실패 방지
    old_value: str | float | None = None
    new_value: str | float | None = None


class ReviewImportResult(BaseModel):
    diffs: list[ReviewDiffEntry] = Field(default_factory=list)
    unknown_segment_ids: list[str] = Field(default_factory=list)