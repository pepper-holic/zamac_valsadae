export type ProjectStatus =
  | 'uploaded'
  | 'queued'
  | 'transcribing'
  | 'transcribed'
  | 'translating'
  | 'translated'
  | 'rendering'
  | 'rendered'
  | 'error'

export type TranslationDirection = 'ko->en' | 'en->ko'
export type TranslationEngine = 'local' | 'api'
export type ExportFormat = 'srt' | 'vtt' | 'json' | 'ass' | 'ttml'

export type QualityFlag = 'good' | 'check'

export type ProgressStage = 'downloading_model' | 'processing' | 'diarizing' | 'rendering'

export interface Word {
  text: string
  start: number
  end: number
}

export interface Segment {
  id: string
  start: number
  end: number
  text: string
  speaker: string | null
  translation: string | null
  transcription_quality: QualityFlag | null
  transcription_quality_reason: string | null
  translation_quality: QualityFlag | null
  translation_quality_reason: string | null
  readability_flag: QualityFlag | null
  readability_reason: string | null
  reviewed: boolean
  words: Word[]
}

export interface MediaItem {
  id: string
  filename: string
  media_path: string
  status: ProjectStatus
  whisper_model: string | null
  error: string | null
  progress: number | null
  stage: ProgressStage | null
  started_at: number | null
  segments: Segment[]
  rendered_path: string | null
}

export interface SubtitleStyle {
  font_family: string
  font_size: number
  font_weight: 'normal' | 'bold'
  color: string
  outline_color: string
  outline_width: number
  background: string | null
  position: 'bottom' | 'top' | 'custom'
  fade_in_ms: number
  fade_out_ms: number
  karaoke_highlight: boolean
  auto_line_break: boolean
  max_line_chars: number
}

export interface NamedSubtitleStyle {
  name: string
  style: SubtitleStyle
}

export interface Project {
  id: string
  name: string
  items: MediaItem[]
  glossary: Record<string, string>
  subtitle_style: SubtitleStyle
  style_presets: NamedSubtitleStyle[]
}

export interface ReviewDiffEntry {
  id: string
  field: 'text' | 'translation' | 'start' | 'end'
  old_value: string | number | null
  new_value: string | number | null
}

export interface ReviewImportResult {
  diffs: ReviewDiffEntry[]
  unknown_segment_ids: string[]
}

export interface ModelStatus {
  whisper: Record<string, boolean>
  translation: Record<string, boolean>
}

export interface UndoRedoResult {
  segments: Segment[]
  can_undo: boolean
  can_redo: boolean
}

export interface AuthStatus {
  logged_in: boolean
  email: string | null
}

export const WHISPER_MODELS = [
  'tiny',
  'base',
  'small',
  'medium',
  'large',
  'large-v2',
  'large-v3',
  'large-v3-turbo',
] as const
