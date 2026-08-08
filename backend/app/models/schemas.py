from typing import Literal
from pydantic import BaseModel, Field

ProjectStatus = Literal[
    "uploaded",
    "transcribing",
    "transcribed",
    "translating",
    "translated",
    "rendering",
    "rendered",
    "error",
]

TranslationDirection = Literal["ko->en", "en->ko"]
TranslationEngine = Literal["local", "api"]
ExportFormat = Literal["srt", "vtt", "json", "ass", "ttml"]
QualityFlag = Literal["good", "check"]
ProgressStage = Literal["downloading_model", "processing", "diarizing", "rendering"]


class Segment(BaseModel):
    id: str
    start: float = 0.0  # 기본값 설정으로 누락 시 에러 방지
    end: float = 0.0    # 기본값 설정으로 누락 시 에러 방지
    text: str = ""      # 기본값 설정으로 누락 시 에러 방지
    speaker: str | None = None
    translation: str | None = None
    transcription_quality: QualityFlag | None = None
    transcription_quality_reason: str | None = None
    translation_quality: QualityFlag | None = None
    translation_quality_reason: str | None = None
    readability_flag: QualityFlag | None = None
    readability_reason: str | None = None
    reviewed: bool = False


class SubtitleStyle(BaseModel):
    font_family: str = "Pretendard"
    font_size: int = 32
    font_weight: Literal["normal", "bold"] = "bold"
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 2
    background: str | None = None
    position: Literal["bottom", "top", "custom"] = "bottom"
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    karaoke_highlight: bool = False


class NamedSubtitleStyle(BaseModel):
    name: str
    style: SubtitleStyle = Field(default_factory=SubtitleStyle)


class MediaItem(BaseModel):
    """One uploaded video/audio file and its transcription/translation state.

    A Project groups multiple MediaItems (e.g. an interview series or lecture
    set) that share a glossary and translation memory, while each item's
    transcript, segments, and processing status stay independent.
    """

    id: str
    filename: str = ""
    media_path: str = ""
    status: ProjectStatus = "uploaded"
    whisper_model: str | None = None
    error: str | None = None
    progress: float | None = None
    stage: ProgressStage | None = None
    segments: list[Segment] = Field(default_factory=list)
    rendered_path: str | None = None


class Project(BaseModel):
    id: str
    name: str = ""
    items: list[MediaItem] = Field(default_factory=list)
    glossary: dict[str, str] = Field(default_factory=dict)
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)
    style_presets: list[NamedSubtitleStyle] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    name: str = ""


class RenderRequest(BaseModel):
    use_translation: bool = False


class TranscribeRequest(BaseModel):
    model: str = "small"
    diarize: bool = False


class TranslateRequest(BaseModel):
    direction: TranslationDirection
    engine: TranslationEngine = "local"


class GlossaryUpdate(BaseModel):
    glossary: dict[str, str] = Field(default_factory=dict)


class StylePresetCreate(BaseModel):
    name: str
    style: SubtitleStyle


class SegmentSplitRequest(BaseModel):
    split_at: float


class SegmentMergeRequest(BaseModel):
    segment_ids: list[str]


class SegmentFindReplaceRequest(BaseModel):
    field: Literal["text", "translation"]
    find: str
    replace: str = ""


class SegmentDetectFillersRequest(BaseModel):
    language: Literal["ko", "en"] = "ko"


class UndoRedoResult(BaseModel):
    segments: list[Segment] = Field(default_factory=list)
    can_undo: bool = False
    can_redo: bool = False


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
    item_id: str
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


class ModelStatus(BaseModel):
    whisper: dict[str, bool] = Field(default_factory=dict)
    translation: dict[str, bool] = Field(default_factory=dict)