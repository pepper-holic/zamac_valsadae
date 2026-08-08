export type ProjectStatus =
  | 'uploaded'
  | 'transcribing'
  | 'transcribed'
  | 'translating'
  | 'translated'
  | 'error'

export type TranslationDirection = 'ko->en' | 'en->ko'
export type TranslationEngine = 'local' | 'api'
export type ExportFormat = 'srt' | 'vtt' | 'json' | 'ass' | 'ttml'

export type QualityFlag = 'good' | 'check'

export type ProgressStage = 'downloading_model' | 'processing' | 'diarizing'

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
  segments: Segment[]
}

export interface Project {
  id: string
  name: string
  items: MediaItem[]
  glossary: Record<string, string>
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

export const WHISPER_MODELS = [
  'tiny',
  'base',
  'small',
  'medium',
  'large',
  'large-v2',
  'large-v3',
] as const
