import type {
  ExportFormat,
  Project,
  ReviewImportResult,
  Segment,
  TranslationDirection,
  TranslationEngine,
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

export async function uploadProject(file: File): Promise<Project> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/projects`, { method: 'POST', body: formData })
  return parseOrThrow<Project>(response)
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE}/projects`)
  return parseOrThrow<Project[]>(response)
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`)
  return parseOrThrow<Project>(response)
}

export function mediaUrl(projectId: string): string {
  return `${API_BASE}/projects/${projectId}/media`
}

export async function transcribeProject(projectId: string, model: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/transcribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
  return parseOrThrow<Project>(response)
}

export async function translateProject(
  projectId: string,
  direction: TranslationDirection,
  engine: TranslationEngine,
): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction, engine }),
  })
  return parseOrThrow<Project>(response)
}

export async function updateSegment(
  projectId: string,
  segmentId: string,
  update: Partial<{
    text: string
    translation: string
    start: number
    end: number
    reviewed: boolean
  }>,
) {
  const response = await fetch(`${API_BASE}/projects/${projectId}/segments/${segmentId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  })
  return parseOrThrow<Segment>(response)
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}`, { method: 'DELETE' })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export async function deleteSegment(projectId: string, segmentId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${projectId}/segments/${segmentId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API 오류 (${response.status}): ${body}`)
  }
}

export function exportUrl(projectId: string, format: ExportFormat, useTranslation: boolean): string {
  return `${API_BASE}/projects/${projectId}/export?format=${format}&use_translation=${useTranslation}`
}

export function reviewPackageUrl(projectId: string): string {
  return `${API_BASE}/projects/${projectId}/review-package`
}

export async function importReviewPackage(
  projectId: string,
  file: File,
): Promise<ReviewImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/projects/${projectId}/review-import`, {
    method: 'POST',
    body: formData,
  })
  return parseOrThrow<ReviewImportResult>(response)
}
