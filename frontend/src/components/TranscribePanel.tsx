import { useState } from 'react'
import type { Project } from '../api/types'
import { WHISPER_MODELS } from '../api/types'
import { transcribeProject } from '../api/client'

type Props = {
  project: Project
  onStarted: (project: Project) => void
}

const isBusy = (status: Project['status']) => status === 'transcribing' || status === 'translating'

const MODEL_NOTES: Record<string, string> = {
  tiny: '매우 빠름 · 정확도 낮음 — 빠른 테스트용',
  base: '빠름 · 정확도 낮음~보통',
  small: '보통 속도 · 정확도 보통~좋음 — 기본 권장',
  medium: '느림 · 정확도 좋음 — 소음/사투리에 강함',
  large: '매우 느림(CPU) · 정확도 최고',
  'large-v2': '매우 느림(CPU) · 정확도 최고',
  'large-v3': '매우 느림(CPU) · 정확도 최고',
}

export function TranscribePanel({ project, onStarted }: Props) {
  const [model, setModel] = useState(project.whisper_model ?? 'small')
  const [error, setError] = useState<string | null>(null)

  async function handleTranscribe() {
    setError(null)
    try {
      const updated = await transcribeProject(project.id, model)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <section className="panel">
      <h2>1. 전사 (Whisper)</h2>
      <div className="panel-row">
        <label htmlFor="model-select">모델 크기</label>
        <select
          id="model-select"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          disabled={isBusy(project.status)}
          data-tip="클수록 정확하지만 GPU 없이는 훨씬 느려집니다. small을 기본으로 추천합니다."
        >
          {WHISPER_MODELS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleTranscribe}
          disabled={isBusy(project.status)}
          data-tip="선택한 모델로 음성 인식을 시작합니다."
        >
          {project.status === 'transcribing' ? '전사 중...' : '전사 시작'}
        </button>
      </div>
      <p className="hint-text">{MODEL_NOTES[model]}</p>
      {project.status === 'transcribing' && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((project.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            {Math.round((project.progress ?? 0) * 100)}% 처리 중 — 모델을 로드하고 음성을 인식하는
            중입니다. 모델 크기에 따라 수 분이 걸릴 수 있습니다.
          </p>
        </div>
      )}
      {project.status === 'error' && project.error && <p className="error-text">{project.error}</p>}
      {error && <p className="error-text">{error}</p>}
    </section>
  )
}
