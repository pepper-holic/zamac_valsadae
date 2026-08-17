import { useState } from 'react'
import type { MediaItem, Project } from '../api/types'
import { cancelItem, translateItem, updateGlossary } from '../api/client'
import { PanelHint } from './PanelHint'
import { formatClock } from '../utils/time'
import { useElapsedSeconds } from '../utils/useElapsedSeconds'

type Props = {
  project: Project
  item: MediaItem
  onStarted: (item: MediaItem) => void
  onGlossaryUpdated: (project: Project) => void
}

export function TranslationPanel({ project, item, onStarted, onGlossaryUpdated }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [newTerm, setNewTerm] = useState('')
  const [newTranslation, setNewTranslation] = useState('')

  const hasSegments = item.segments.length > 0
  const isBusy = item.status === 'translating' || item.status === 'transcribing'
  const elapsedSeconds = useElapsedSeconds(item.status === 'translating' ? item.started_at : null)

  async function handleTranslate() {
    setError(null)
    try {
      const updated = await translateItem(project.id, item.id)
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
      <h2>
        2. 번역
        <PanelHint tip="인식된 자막을 한↔영으로 번역합니다. 언어는 자동으로 감지됩니다. 용어집을 등록하면 특정 단어/표현을 원하는 대로 고정할 수 있습니다." />
      </h2>
      <div className="panel-row">
        <button
          type="button"
          onClick={handleTranslate}
          disabled={!hasSegments || isBusy}
          data-tip="번역을 시작합니다. 언어를 자동으로 감지해 원문 교정과 번역을 함께 받습니다."
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
      {item.status === 'translating' && (
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
