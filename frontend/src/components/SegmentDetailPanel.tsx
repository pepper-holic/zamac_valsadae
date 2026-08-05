import { useRef, useState } from 'react'
import type { Project, ReviewDiffEntry, Segment } from '../api/types'
import { deleteSegment, updateSegment } from '../api/client'
import { formatTimestamp, parseTimestamp } from '../utils/time'

type Props = {
  project: Project
  segment: Segment | null
  segmentPosition: string
  currentTime: number
  segmentDiffs: ReviewDiffEntry[]
  onSegmentSaved: (segment: Segment) => void
  onSegmentDeleted: (segmentId: string) => void
  onNavigate: (direction: 'prev' | 'next') => void
  onSeek: (time: number) => void
  onPlaySegment: () => void
  onAcceptDiff: (diff: ReviewDiffEntry) => void
  onRejectDiff: (diff: ReviewDiffEntry) => void
}

type EditableField = 'start' | 'end' | 'text' | 'translation'

const FIELD_LABELS: Record<ReviewDiffEntry['field'], string> = {
  text: '원문',
  translation: '번역',
  start: '시작 시간',
  end: '종료 시간',
}

const SAVED_FLASH_MS = 1500

export function SegmentDetailPanel({
  project,
  segment,
  segmentPosition,
  currentTime,
  segmentDiffs,
  onSegmentSaved,
  onSegmentDeleted,
  onNavigate,
  onSeek,
  onPlaySegment,
  onAcceptDiff,
  onRejectDiff,
}: Props) {
  const [isSaving, setIsSaving] = useState(false)
  const [justSaved, setJustSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  if (!segment) {
    return (
      <section className="detail-panel">
        <h2>상세 검수</h2>
        <p className="hint-text">가운데 목록에서 문장을 선택하면 상세 편집 도구가 표시됩니다.</p>
      </section>
    )
  }

  async function handleSave(field: EditableField, rawValue: string) {
    if (!segment) return
    let value: string | number = rawValue
    if (field === 'start' || field === 'end') {
      const parsed = parseTimestamp(rawValue)
      if (parsed === null) return
      value = parsed
    }
    setIsSaving(true)
    setError(null)
    try {
      const updated = await updateSegment(project.id, segment.id, { [field]: value })
      onSegmentSaved(updated as Segment)
      setJustSaved(true)
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current)
      savedTimerRef.current = setTimeout(() => setJustSaved(false), SAVED_FLASH_MS)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsSaving(false)
    }
  }

  async function handleDelete() {
    if (!segment) return
    if (!window.confirm('이 문장을 삭제할까요? 되돌릴 수 없습니다.')) return
    await deleteSegment(project.id, segment.id)
    onSegmentDeleted(segment.id)
  }

  async function handleToggleReviewed() {
    if (!segment) return
    const updated = await updateSegment(project.id, segment.id, { reviewed: !segment.reviewed })
    onSegmentSaved(updated as Segment)
  }

  return (
    <section className="detail-panel">
      <div className="detail-header">
        <h2>상세 검수</h2>
        <div className="detail-nav">
          <button
            type="button"
            onClick={() => onNavigate('prev')}
            data-tip="이전 문장으로 이동 (단축키: ↑)"
          >
            ◀ 이전
          </button>
          <span className="segment-position">{segmentPosition}</span>
          <button
            type="button"
            onClick={() => onNavigate('next')}
            data-tip="다음 문장으로 이동 (단축키: ↓)"
          >
            다음 ▶
          </button>
        </div>
      </div>

      <button
        type="button"
        className={segment.reviewed ? 'reviewed-button checked' : 'reviewed-button'}
        onClick={handleToggleReviewed}
        data-tip={segment.reviewed ? '검토 완료 표시를 해제합니다.' : '이 문장을 검토 완료로 표시합니다.'}
      >
        {segment.reviewed ? '✓ 검토 완료' : '검토 완료로 표시'}
      </button>

      {(segment.transcription_quality === 'check' || segment.translation_quality === 'check') && (
        <div className="quality-callout">
          <span className="quality-callout-icon">⚠</span>
          <div>
            {segment.transcription_quality === 'check' && (
              <p>전사 확인 필요: {segment.transcription_quality_reason}</p>
            )}
            {segment.translation_quality === 'check' && (
              <p>번역 확인 필요: {segment.translation_quality_reason}</p>
            )}
          </div>
        </div>
      )}

      <div className="detail-timing">
        <div className="timing-field">
          <label>시작</label>
          <input
            className="time-input"
            defaultValue={formatTimestamp(segment.start)}
            key={`start-${segment.id}`}
            onBlur={(event) => handleSave('start', event.target.value)}
            data-tip="문장이 시작되는 시간(hh:mm:ss.mmm). 직접 입력해 수정할 수 있습니다."
          />
          <button
            type="button"
            onClick={() => handleSave('start', formatTimestamp(currentTime))}
            data-tip="영상의 현재 재생 위치를 시작 시간으로 지정합니다."
          >
            현재 위치로 설정
          </button>
        </div>
        <div className="timing-field">
          <label>종료</label>
          <input
            className="time-input"
            defaultValue={formatTimestamp(segment.end)}
            key={`end-${segment.id}`}
            onBlur={(event) => handleSave('end', event.target.value)}
            data-tip="문장이 끝나는 시간(hh:mm:ss.mmm). 직접 입력해 수정할 수 있습니다."
          />
          <button
            type="button"
            onClick={() => handleSave('end', formatTimestamp(currentTime))}
            data-tip="영상의 현재 재생 위치를 종료 시간으로 지정합니다."
          >
            현재 위치로 설정
          </button>
        </div>
        <div className="timing-actions">
          <button
            type="button"
            onClick={() => onSeek(segment.start)}
            data-tip="영상 재생 위치를 이 문장의 시작 지점으로 옮깁니다."
          >
            시작 지점으로 이동
          </button>
          <button
            type="button"
            className="play-button"
            onClick={onPlaySegment}
            data-tip="시작 지점부터 재생을 시작합니다."
          >
            이 구간 재생
          </button>
          <button
            type="button"
            className="danger-button"
            onClick={handleDelete}
            data-tip="이 문장을 목록에서 삭제합니다 (오인식된 문장 정리용, 되돌릴 수 없음)."
          >
            문장 삭제
          </button>
          {isSaving && <span className="saving-dot" title="저장 중" />}
          {!isSaving && justSaved && <span className="saved-check">저장됨 ✓</span>}
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      <label className="detail-label" htmlFor="detail-text">
        원문
      </label>
      <textarea
        id="detail-text"
        className="detail-textarea"
        defaultValue={segment.text}
        key={`text-${segment.id}`}
        onBlur={(event) => handleSave('text', event.target.value)}
      />

      <label className="detail-label" htmlFor="detail-translation">
        번역
      </label>
      <textarea
        id="detail-translation"
        className="detail-textarea translation"
        defaultValue={segment.translation ?? ''}
        placeholder="번역 없음"
        key={`translation-${segment.id}`}
        onBlur={(event) => handleSave('translation', event.target.value)}
      />

      {segmentDiffs.length > 0 && (
        <div className="detail-diffs">
          <h3>AI 검수 제안</h3>
          <ul className="diff-list">
            {segmentDiffs.map((diff, index) => (
              <li key={`${diff.field}-${index}`} className="diff-item">
                <div className="diff-meta">
                  <span className="diff-field">{FIELD_LABELS[diff.field]}</span>
                  <span className="diff-old">{String(diff.old_value)}</span>
                  <span className="diff-arrow">→</span>
                  <span className="diff-new">{String(diff.new_value)}</span>
                </div>
                <div className="diff-actions">
                  <button
                    type="button"
                    onClick={() => onAcceptDiff(diff)}
                    data-tip="AI가 제안한 값으로 이 항목을 교체합니다."
                  >
                    반영
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => onRejectDiff(diff)}
                    data-tip="이 제안을 무시하고 기존 값을 유지합니다."
                  >
                    무시
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
