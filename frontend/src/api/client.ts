import type {
  AuthStatus,
  ExportFormat,
  ExportTextMode,
  MediaItem,
  ModelStatus,
  Project,
  ProjectStatusSummary,
  ReviewImportResult,
  Segment,
  SubtitleStyle,
  UndoRedoResult,
} from './types'

// Empty string means "same origin" - correct for production, where the
// backend serves this built frontend itself. Local dev (`npm run dev`)
// overrides this via .env.development since Vite (5173) and the API
// (8000) run as separate servers there.
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

// Most calls here just kick off a background job on the backend (transcribe/
// translate/render all return immediately via FastAPI BackgroundTasks) or
// hit a small JSON endpoint, so 30s is generous. File uploads get their own
// longer budget below since a large video over a slow disk can legitimately
// take longer to write.
const DEFAULT_TIMEOUT_MS = 30_000
const UPLOAD_TIMEOUT_MS = 10 * 60_000

// Plain fetch() has no timeout: if the backend hangs (e.g. stuck behind a
// slow/unreachable cloud relay call), the UI would wait forever with no
// feedback. This wraps every call with an AbortController-based timeout so
// a hung request surfaces as an error instead.
async function apiFetch(
  input: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await globalThis.fetch(input, { ...init, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(`요청이 ${Math.round(timeoutMs / 1000)}초 안에 응답하지 않았습니다.`)
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
  return response.json() as Promise<T>
}

export async function createProject(name: string = ''): Promise<Project> {
  const response = await apiFetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return parseOrThrow<Project>(response)
}

export async function addItem(projectId: string, file: File): Promise<MediaItem> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiFetch(
    `${API_BASE}/projects/${projectId}/items`,
    { method: 'POST', body: formData },
    UPLOAD_TIMEOUT_MS,
  )
  return parseOrThrow<MediaItem>(response)
}

export async function deleteItem(projectId: string, itemId: string): Promise<void> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export async function listProjects(): Promise<Project[]> {
  const response = await apiFetch(`${API_BASE}/projects`)
  return parseOrThrow<Project[]>(response)
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}`)
  return parseOrThrow<Project>(response)
}

// Lightweight polling target - status/progress/stage per item, no
// segments/words. Used to refresh progress bars without re-fetching (and
// re-rendering) a whole potentially-large transcript every tick.
export async function getProjectStatus(projectId: string): Promise<ProjectStatusSummary> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/status`)
  return parseOrThrow<ProjectStatusSummary>(response)
}

export function mediaUrl(projectId: string, itemId: string): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/media`
}

export async function getModelStatus(): Promise<ModelStatus> {
  const response = await apiFetch(`${API_BASE}/models/status`)
  return parseOrThrow<ModelStatus>(response)
}

export async function transcribeItem(
  projectId: string,
  itemId: string,
  model: string,
  diarize: boolean = false,
  multilingual: boolean = false,
): Promise<MediaItem> {
  const response = await apiFetch(
    `${API_BASE}/projects/${projectId}/items/${itemId}/transcribe`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, diarize, multilingual }),
    },
  )
  return parseOrThrow<MediaItem>(response)
}

export async function translateItem(projectId: string, itemId: string): Promise<MediaItem> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}/translate`, {
    method: 'POST',
  })
  return parseOrThrow<MediaItem>(response)
}

export async function updateGlossary(
  projectId: string,
  glossary: Record<string, string>,
): Promise<Project> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/glossary`, {
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
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/${segmentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
  return parseOrThrow<Segment>(response)
}

export async function cancelItem(projectId: string, itemId: string): Promise<MediaItem> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}/cancel`, {
    method: 'POST',
  })
  return parseOrThrow<MediaItem>(response)
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}`, { method: 'DELETE' })
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
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/${segmentId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

type SegmentFieldUpdate = Partial<{
  text: string
  translation: string
  start: number
  end: number
  reviewed: boolean
}>

export async function bulkUpdateSegments(
  projectId: string,
  itemId: string,
  updates: { id: string; update: SegmentFieldUpdate }[],
): Promise<Segment[]> {
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/bulk-update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  })
  return parseOrThrow<Segment[]>(response)
}

export async function bulkDeleteSegments(
  projectId: string,
  itemId: string,
  segmentIds: string[],
): Promise<Segment[]> {
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/bulk-delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ segment_ids: segmentIds }),
  })
  return parseOrThrow<Segment[]>(response)
}

export async function splitSegment(
  projectId: string,
  itemId: string,
  segmentId: string,
  splitAt: number,
): Promise<Segment[]> {
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/${segmentId}/split`, {
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
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/merge`, {
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
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/find-replace`, {
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
  const response = await apiFetch(`${segmentsBase(projectId, itemId)}/detect-fillers`, {
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
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/style`, {
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
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/style/presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, style }),
  })
  return parseOrThrow<Project>(response)
}

export async function deleteStylePreset(projectId: string, name: string): Promise<Project> {
  const response = await apiFetch(
    `${API_BASE}/projects/${projectId}/style/presets/${encodeURIComponent(name)}`,
    { method: 'DELETE' },
  )
  return parseOrThrow<Project>(response)
}

export async function undoItem(projectId: string, itemId: string): Promise<UndoRedoResult> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}/undo`, {
    method: 'POST',
  })
  return parseOrThrow<UndoRedoResult>(response)
}

export async function redoItem(projectId: string, itemId: string): Promise<UndoRedoResult> {
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}/redo`, {
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
  const response = await apiFetch(`${API_BASE}/projects/${projectId}/items/${itemId}/render`, {
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
  mode: ExportTextMode = 'original',
): string {
  return `${API_BASE}/projects/${projectId}/items/${itemId}/export?format=${format}&mode=${mode}`
}

export function reviewPackageUrl(projectId: string, itemId: string, compact = false): string {
  const query = compact ? '?compact=true' : ''
  return `${API_BASE}/projects/${projectId}/items/${itemId}/review-package${query}`
}

export async function importReviewPackage(
  projectId: string,
  itemId: string,
  file: File,
): Promise<ReviewImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiFetch(
    `${API_BASE}/projects/${projectId}/items/${itemId}/review-import`,
    { method: 'POST', body: formData },
    UPLOAD_TIMEOUT_MS,
  )
  return parseOrThrow<ReviewImportResult>(response)
}

export async function postAuthSession(accessToken: string, email: string): Promise<AuthStatus> {
  const response = await apiFetch(`${API_BASE}/auth/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: accessToken, email }),
  })
  return parseOrThrow<AuthStatus>(response)
}

export async function clearAuthSession(): Promise<AuthStatus> {
  const response = await apiFetch(`${API_BASE}/auth/session`, { method: 'DELETE' })
  return parseOrThrow<AuthStatus>(response)
}
