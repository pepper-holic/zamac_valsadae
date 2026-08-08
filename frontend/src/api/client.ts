import type {
  ExportFormat,
  MediaItem,
  ModelStatus,
  Project,
  ReviewImportResult,
  Segment,
  SubtitleStyle,
  TranslationDirection,
  TranslationEngine,
  UndoRedoResult,
} from './types'

// Empty string means "same origin" - correct for production, where the
// backend serves this built frontend itself. Local dev (`npm run dev`)
// overrides this via .env.development since Vite (5173) and the API
// (8000) run as separate servers there.
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
  return response.json() as Promise<T>
}

export async function createProject(name: string = ''): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return parseOrThrow<Project>(response)
}

export async function addItem(projectId: string, file: File): Promise<MediaItem> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/projects/${projectId}/items`, {
    method: 'POST',
    body: formData,
  })
  return parseOrThrow<MediaItem>(response)
}

export async function deleteItem(projectId: string, itemId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE}/projects`)
  return parseOrThrow<Project[]>(response)
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`)
  return parseOrThrow<Project>(response)
}

export function mediaUrl(projectId: string, itemId: string): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/media`
}

export async function getModelStatus(): Promise<ModelStatus> {
  const response = await fetch(`${API_BASE}/models/status`)
  return parseOrThrow<ModelStatus>(response)
}

export async function transcribeItem(
  projectId: string,
  itemId: string,
  model: string,
  diarize: boolean = false,
): Promise<MediaItem> {
  const response = await fetch(
    `${API_BASE}/projects/${projectId}/items/${itemId}/transcribe`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, diarize }),
    },
  )
  return parseOrThrow<MediaItem>(response)
}

export async function translateItem(
  projectId: string,
  itemId: string,
  direction: TranslationDirection,
  engine: TranslationEngine,
): Promise<MediaItem> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction, engine }),
  })
  return parseOrThrow<MediaItem>(response)
}

export async function updateGlossary(
  projectId: string,
  glossary: Record<string, string>,
): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/glossary`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ glossary }),
  })
  return parseOrThrow<Project>(response)
}

function segmentsBase(projectId: string, itemId: string): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/segments`
}

export async function updateSegment(
  projectId: string,
  itemId: string,
  segmentId: string,
  update: Partial<{
    text: string
    translation: string
    start: number
    end: number
    reviewed: boolean
  }>,
) {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/${segmentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
  return parseOrThrow<Segment>(response)
}

export async function cancelItem(projectId: string, itemId: string): Promise<MediaItem> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/cancel`, {
    method: 'POST',
  })
  return parseOrThrow<MediaItem>(response)
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`, { method: 'DELETE' })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export async function deleteSegment(
  projectId: string,
  itemId: string,
  segmentId: string,
): Promise<void> {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/${segmentId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export async function splitSegment(
  projectId: string,
  itemId: string,
  segmentId: string,
  splitAt: number,
): Promise<Segment[]> {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/${segmentId}/split`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ split_at: splitAt }),
  })
  return parseOrThrow<Segment[]>(response)
}

export async function mergeSegments(
  projectId: string,
  itemId: string,
  segmentIds: string[],
): Promise<Segment> {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segment_ids: segmentIds }),
  })
  return parseOrThrow<Segment>(response)
}

export async function findReplaceSegments(
  projectId: string,
  itemId: string,
  field: 'text' | 'translation',
  find: string,
  replace: string,
): Promise<Segment[]> {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/find-replace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ field, find, replace }),
  })
  return parseOrThrow<Segment[]>(response)
}

export async function detectFillerSegments(
  projectId: string,
  itemId: string,
  language: 'ko' | 'en' = 'ko',
): Promise<string[]> {
  const response = await fetch(`${segmentsBase(projectId, itemId)}/detect-fillers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language }),
  })
  return parseOrThrow<string[]>(response)
}

export async function updateSubtitleStyle(
  projectId: string,
  style: SubtitleStyle,
): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/style`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(style),
  })
  return parseOrThrow<Project>(response)
}

export async function saveStylePreset(
  projectId: string,
  name: string,
  style: SubtitleStyle,
): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/style/presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, style }),
  })
  return parseOrThrow<Project>(response)
}

export async function deleteStylePreset(projectId: string, name: string): Promise<Project> {
  const response = await fetch(
    `${API_BASE}/projects/${projectId}/style/presets/${encodeURIComponent(name)}`,
    { method: 'DELETE' },
  )
  return parseOrThrow<Project>(response)
}

export async function undoItem(projectId: string, itemId: string): Promise<UndoRedoResult> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/undo`, {
    method: 'POST',
  })
  return parseOrThrow<UndoRedoResult>(response)
}

export async function redoItem(projectId: string, itemId: string): Promise<UndoRedoResult> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/redo`, {
    method: 'POST',
  })
  return parseOrThrow<UndoRedoResult>(response)
}

export async function renderItem(
  projectId: string,
  itemId: string,
  useTranslation: boolean,
  cutDeleted: boolean = false,
): Promise<MediaItem> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_translation: useTranslation, cut_deleted: cutDeleted }),
  })
  return parseOrThrow<MediaItem>(response)
}

export function renderedVideoUrl(projectId: string, itemId: string): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/rendered`
}

export function exportUrl(
  projectId: string,
  itemId: string,
  format: ExportFormat,
  useTranslation: boolean,
): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/export?format=${format}&use_translation=${useTranslation}`
}

export function reviewPackageUrl(projectId: string, itemId: string): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/review-package`
}

export async function importReviewPackage(
  projectId: string,
  itemId: string,
  file: File,
): Promise<ReviewImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/projects/${projectId}/items/${itemId}/review-import`, {
    method: 'POST',
    body: formData,
  })
  return parseOrThrow<ReviewImportResult>(response)
}
