import { useEffect, useState } from 'react'
import type { Project, TranslationDirection, TranslationEngine } from '../api/types'
import { getModelStatus, translateProject } from '../api/client'

type Props = {
  project: Project
  onStarted: (project: Project) => void
}

export function TranslationPanel({ project, onStarted }: Props) {
  const [direction, setDirection] = useState<TranslationDirection>('en->ko')
  const [engine, setEngine] = useState<TranslationEngine>('local')
  const [error, setError] = useState<string | null>(null)
  const [translationCacheStatus, setTranslationCacheStatus] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let cancelled = false
    getModelStatus()
      .then((status) => {
        if (!cancelled) setTranslationCacheStatus(status.translation)
      })
      .catch(() => {
        // best-effort only - selectors just skip the download badge on failure
      })
    return () => {
      cancelled = true
    }
  }, [])

  const hasSegments = project.segments.length > 0
  const isBusy = project.status === 'translating' || project.status === 'transcribing'
  const isModelCached = translationCacheStatus[direction]
  const isDownloadingModel = project.status === 'translating' && project.stage === 'downloading_model'

  async function handleTranslate() {
    setError(null)
    try {
      const updated = await translateProject(project.id, direction, engine)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <section className="panel">
      <h2>2. 번역</h2>
      <div className="panel-row">
        <label htmlFor="direction-select">방향</label>
        <select
          id="direction-select"
          value={direction}
          onChange={(event) => setDirection(event.target.value as TranslationDirection)}
          disabled={isBusy}
          data-tip="번역 방향을 고릅니다. 이미 목표 언어로 되어 있는 문장은 자동으로 건너뜁니다."
        >
          <option value="en->ko">영어 → 한국어</option>
          <option value="ko->en">한국어 → 영어</option>
        </select>
        <label htmlFor="engine-select">엔진</label>
        <select
          id="engine-select"
          value={engine}
          onChange={(event) => setEngine(event.target.value as TranslationEngine)}
          disabled={isBusy}
          data-tip="로컬은 무료·오프라인, API는 별도 키가 필요하지만 품질이 더 좋을 수 있습니다."
        >
          <option value="local">로컬 모델 (무료, API 키 불필요)</option>
          <option value="api">API 번역 (설정에 키 필요)</option>
        </select>
        <button
          type="button"
          onClick={handleTranslate}
          disabled={!hasSegments || isBusy}
          data-tip="선택한 방향/엔진으로 번역을 시작합니다."
        >
          {project.status === 'translating' ? '번역 중...' : '번역 시작'}
        </button>
      </div>
      {!hasSegments && <p className="hint-text">먼저 전사를 완료해야 번역할 수 있습니다.</p>}
      {!isBusy && engine === 'local' && isModelCached === false && (
        <p className="hint-text">⬇ 이 방향의 번역 모델은 아직 다운로드되지 않았습니다. 번역 시작 시 최초 1회 자동으로 다운로드됩니다.</p>
      )}
      {!isBusy && engine === 'local' && isModelCached && (
        <p className="hint-text">✓ 번역 모델이 이미 다운로드되어 있습니다.</p>
      )}
      {project.status === 'translating' && isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar progress-bar-indeterminate" />
          <p className="hint-text">
            번역 모델 다운로드 중입니다 — 인터넷 연결이 필요하며 수 분 정도 걸릴 수 있습니다. (최초
            1회만 필요)
          </p>
        </div>
      )}
      {project.status === 'translating' && !isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((project.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            {Math.round((project.progress ?? 0) * 100)}% 처리 중 — 문장 수에 따라 시간이 걸릴 수
            있습니다.
          </p>
        </div>
      )}
      {project.status === 'error' && project.error && <p className="error-text">{project.error}</p>}
      {error && <p className="error-text">{error}</p>}
    </section>
  )
}
