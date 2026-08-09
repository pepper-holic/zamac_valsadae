import { useEffect, useState } from 'react'
import type { MediaItem, Project, TranslationDirection, TranslationEngine } from '../api/types'
import { cancelItem, getModelStatus, translateItem, updateGlossary } from '../api/client'
import { formatClock } from '../utils/time'
import { useElapsedSeconds } from '../utils/useElapsedSeconds'

type Props = {
  project: Project
  item: MediaItem
  onStarted: (item: MediaItem) => void
  onGlossaryUpdated: (project: Project) => void
}

export function TranslationPanel({ project, item, onStarted, onGlossaryUpdated }: Props) {
  const [direction, setDirection] = useState<TranslationDirection>('en->ko')
  const [engine, setEngine] = useState<TranslationEngine>('local')
  const [error, setError] = useState<string | null>(null)
  const [translationCacheStatus, setTranslationCacheStatus] = useState<Record<string, boolean>>({})
  const [newTerm, setNewTerm] = useState('')
  const [newTranslation, setNewTranslation] = useState('')

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

  const hasSegments = item.segments.length > 0
  const isBusy = item.status === 'translating' || item.status === 'transcribing'
  const isModelCached = translationCacheStatus[direction]
  const isDownloadingModel = item.status === 'translating' && item.stage === 'downloading_model'
  const elapsedSeconds = useElapsedSeconds(item.status === 'translating' ? item.started_at : null)

  async function handleTranslate() {
    setError(null)
    try {
      const updated = await translateItem(project.id, item.id, direction, engine)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleCancel() {
    setError(null)
    try {
      const updated = await cancelItem(project.id, item.id)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleAddGlossaryTerm() {
    const term = newTerm.trim()
    const translation = newTranslation.trim()
    if (!term || !translation) return
    try {
      const updated = await updateGlossary(project.id, { ...project.glossary, [term]: translation })
      onGlossaryUpdated(updated)
      setNewTerm('')
      setNewTranslation('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleRemoveGlossaryTerm(term: string) {
    const { [term]: _removed, ...rest } = project.glossary
    try {
      const updated = await updateGlossary(project.id, rest)
      onGlossaryUpdated(updated)
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
          {item.status === 'translating' ? '번역 중...' : '번역 시작'}
        </button>
        {item.status === 'translating' && (
          <button type="button" onClick={handleCancel} data-tip="진행 중인 번역을 중단합니다.">
            취소
          </button>
        )}
      </div>
      {!hasSegments && <p className="hint-text">먼저 전사를 완료해야 번역할 수 있습니다.</p>}
      {!isBusy && engine === 'local' && isModelCached === false && (
        <p className="hint-text">⬇ 이 방향의 번역 모델은 아직 다운로드되지 않았습니다. 번역 시작 시 최초 1회 자동으로 다운로드됩니다.</p>
      )}
      {!isBusy && engine === 'local' && isModelCached && (
        <p className="hint-text">✓ 번역 모델이 이미 다운로드되어 있습니다.</p>
      )}
      {item.status === 'translating' && isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar progress-bar-indeterminate" />
          <p className="hint-text">
            번역 모델 다운로드 중입니다 (경과 {elapsedSeconds != null ? formatClock(elapsedSeconds) : '0:00'}
            ) — 인터넷 연결이 필요하며 수 분 정도 걸릴 수 있습니다. (최초 1회만 필요)
          </p>
        </div>
      )}
      {item.status === 'translating' && !isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((item.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            {Math.round((item.progress ?? 0) * 100)}% 처리 중 (경과{' '}
            {elapsedSeconds != null ? formatClock(elapsedSeconds) : '0:00'}) — 문장 수에 따라 시간이
            걸릴 수 있습니다.
          </p>
        </div>
      )}
      {item.status === 'error' && item.error && <p className="error-text">{item.error}</p>}
      {error && <p className="error-text">{error}</p>}

      <div className="glossary-block">
        <h3>용어집 (프로젝트 전체 공유)</h3>
        <p className="hint-text">
          등록한 용어는 이 프로젝트 안의 모든 파일에서 번역 결과에 항상 지정한 번역으로 강제
          치환됩니다.
        </p>
        {Object.keys(project.glossary).length > 0 && (
          <ul className="glossary-list">
            {Object.entries(project.glossary).map(([term, translation]) => (
              <li key={term}>
                <span>
                  {term} → {translation}
                </span>
                <button type="button" onClick={() => handleRemoveGlossaryTerm(term)}>
                  삭제
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="panel-row">
          <input
            type="text"
            placeholder="원문 용어"
            value={newTerm}
            onChange={(event) => setNewTerm(event.target.value)}
          />
          <input
            type="text"
            placeholder="지정 번역"
            value={newTranslation}
            onChange={(event) => setNewTranslation(event.target.value)}
          />
          <button type="button" onClick={handleAddGlossaryTerm}>
            추가
          </button>
        </div>
      </div>
    </section>
  )
}
