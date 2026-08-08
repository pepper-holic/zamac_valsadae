import { useEffect, useRef, useState } from 'react'
import type { ReviewDiffEntry, Segment } from '../api/types'
import { detectFillerSegments, updateSegment } from '../api/client'
import { formatClock } from '../utils/time'

type Props = {
  projectId: string
  itemId: string
  segments: Segment[]
  selectedSegmentId: string | null
  currentTime: number
  diffs: ReviewDiffEntry[]
  onSelect: (segmentId: string) => void
  onSegmentSaved: (segment: Segment) => void
  onMergeSegments: (segmentIds: string[]) => Promise<void>
  onFindReplace: (field: 'text' | 'translation', find: string, replace: string) => Promise<void>
  onBulkDelete: (segmentIds: string[]) => Promise<void>
  onBulkMarkReviewed: (segmentIds: string[]) => Promise<void>
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
}

type FilterKey = 'all' | 'unreviewed' | 'needsCheck' | 'ok' | 'reviewed'

const PAGE_SIZE = 20

function countDiffsFor(segmentId: string, diffs: ReviewDiffEntry[]): number {
  return diffs.filter((diff) => diff.id === segmentId).length
}

function needsCheck(segment: Segment): boolean {
  return (
    !segment.reviewed &&
    (segment.transcription_quality === 'check' ||
      segment.translation_quality === 'check' ||
      segment.readability_flag === 'check')
  )
}

function isUnreviewed(segment: Segment): boolean {
  return !segment.reviewed
}

function isOk(segment: Segment): boolean {
  return isUnreviewed(segment) && !needsCheck(segment)
}

function qualityTip(segment: Segment): string | undefined {
  const reasons = [
    segment.transcription_quality_reason,
    segment.translation_quality_reason,
    segment.readability_reason,
  ].filter(Boolean)
  return reasons.length > 0 ? reasons.join(' / ') : undefined
}

export function SegmentList({
  projectId,
  itemId,
  segments,
  selectedSegmentId,
  currentTime,
  diffs,
  onSelect,
  onSegmentSaved,
  onMergeSegments,
  onFindReplace,
  onBulkDelete,
  onBulkMarkReviewed,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
}: Props) {
  const activeRowRef = useRef<HTMLLIElement>(null)
  const [page, setPage] = useState(0)
  const [filter, setFilter] = useState<FilterKey>('all')
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [isBulkBusy, setIsBulkBusy] = useState(false)
  const [findField, setFindField] = useState<'text' | 'translation'>('text')
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [isReplacing, setIsReplacing] = useState(false)
  const [fillerLanguage, setFillerLanguage] = useState<'ko' | 'en'>('ko')
  const [isDetectingFillers, setIsDetectingFillers] = useState(false)

  function toggleChecked(segmentId: string) {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(segmentId)) next.delete(segmentId)
      else next.add(segmentId)
      return next
    })
  }

  async function handleMerge() {
    setIsBulkBusy(true)
    try {
      await onMergeSegments([...checkedIds])
      setCheckedIds(new Set())
    } finally {
      setIsBulkBusy(false)
    }
  }

  async function handleBulkDeleteClick() {
    if (!window.confirm(`선택한 ${checkedIds.size}개 문장을 삭제할까요? 되돌릴 수 없습니다.`)) return
    setIsBulkBusy(true)
    try {
      await onBulkDelete([...checkedIds])
      setCheckedIds(new Set())
    } finally {
      setIsBulkBusy(false)
    }
  }

  async function handleBulkMarkReviewedClick() {
    setIsBulkBusy(true)
    try {
      await onBulkMarkReviewed([...checkedIds])
      setCheckedIds(new Set())
    } finally {
      setIsBulkBusy(false)
    }
  }

  async function handleFindReplaceClick() {
    if (!findText) return
    setIsReplacing(true)
    try {
      await onFindReplace(findField, findText, replaceText)
    } finally {
      setIsReplacing(false)
    }
  }

  async function handleDetectFillersClick() {
    setIsDetectingFillers(true)
    try {
      const fillerIds = await detectFillerSegments(projectId, itemId, fillerLanguage)
      setCheckedIds((prev) => new Set([...prev, ...fillerIds]))
    } finally {
      setIsDetectingFillers(false)
    }
  }

  const unreviewedCount = segments.filter(isUnreviewed).length
  const needsCheckCount = segments.filter(needsCheck).length
  const okCount = segments.filter(isOk).length
  const reviewedCount = segments.filter((s) => s.reviewed).length

  const filteredSegments = segments.filter((segment) => {
    if (filter === 'needsCheck') return needsCheck(segment)
    if (filter === 'reviewed') return segment.reviewed
    if (filter === 'unreviewed') return isUnreviewed(segment)
    if (filter === 'ok') return isOk(segment)
    return true
  })

  const totalPages = Math.max(1, Math.ceil(filteredSegments.length / PAGE_SIZE))

  useEffect(() => {
    setPage(0)
  }, [filter])

  useEffect(() => {
    if (!selectedSegmentId) return
    const index = filteredSegments.findIndex((segment) => segment.id === selectedSegmentId)
    if (index === -1) return
    const targetPage = Math.floor(index / PAGE_SIZE)
    setPage((prev) => (prev === targetPage ? prev : targetPage))
    // Only jump pages when the selection itself changes (click, prev/next nav).
    // `segments` gets a new array reference on every poll tick while
    // transcribing/translating, and must not fight manual pagination clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSegmentId])

  useEffect(() => {
    activeRowRef.current?.scrollIntoView({ block: 'nearest' })
  }, [selectedSegmentId, page])

  async function handleToggleReviewed(segment: Segment, event: React.MouseEvent) {
    event.stopPropagation()
    const updated = await updateSegment(projectId, itemId, segment.id, { reviewed: !segment.reviewed })
    onSegmentSaved(updated as Segment)
  }

  const startIndex = page * PAGE_SIZE
  const pageSegments = filteredSegments.slice(startIndex, startIndex + PAGE_SIZE)

  return (
    <section className="segment-list-panel">
      <div className="segment-list-header">
        <h2>검수 대상 문장 ({segments.length})</h2>
        <div className="segment-undo-redo">
          <button
            type="button"
            onClick={onUndo}
            disabled={!canUndo}
            data-tip="되돌리기 (Ctrl+Z)"
          >
            ↶ 되돌리기
          </button>
          <button
            type="button"
            onClick={onRedo}
            disabled={!canRedo}
            data-tip="다시 실행 (Ctrl+Shift+Z)"
          >
            ↷ 다시 실행
          </button>
        </div>
        {totalPages > 1 && (
          <div className="segment-list-pager">
            <button
              type="button"
              onClick={() => setPage((prev) => Math.max(prev - 1, 0))}
              disabled={page === 0}
              data-tip="이전 페이지 (20개씩)"
            >
              ◀
            </button>
            <span>
              {page + 1} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages - 1))}
              disabled={page === totalPages - 1}
              data-tip="다음 페이지 (20개씩)"
            >
              ▶
            </button>
          </div>
        )}
      </div>

      <div className="segment-find-replace">
        <select value={findField} onChange={(event) => setFindField(event.target.value as 'text' | 'translation')}>
          <option value="text">원문</option>
          <option value="translation">번역</option>
        </select>
        <input
          type="text"
          placeholder="찾기"
          value={findText}
          onChange={(event) => setFindText(event.target.value)}
        />
        <input
          type="text"
          placeholder="바꾸기"
          value={replaceText}
          onChange={(event) => setReplaceText(event.target.value)}
        />
        <button
          type="button"
          onClick={handleFindReplaceClick}
          disabled={!findText || isReplacing}
          data-tip="원문 또는 번역 전체에서 일치하는 텍스트를 한 번에 바꿉니다."
        >
          {isReplacing ? '바꾸는 중...' : '모두 바꾸기'}
        </button>
      </div>

      <div className="segment-filler-detect">
        <select value={fillerLanguage} onChange={(event) => setFillerLanguage(event.target.value as 'ko' | 'en')}>
          <option value="ko">한국어</option>
          <option value="en">영어</option>
        </select>
        <button
          type="button"
          onClick={handleDetectFillersClick}
          disabled={segments.length === 0 || isDetectingFillers}
          data-tip="'음', '어'처럼 문장 전체가 필러워드인 세그먼트를 찾아 선택 상태로 만듭니다. 삭제는 아래 선택 항목 삭제 버튼으로 직접 확인 후 실행하세요."
        >
          {isDetectingFillers ? '찾는 중...' : '필러워드 자동 찾기'}
        </button>
      </div>

      {checkedIds.size > 0 && (
        <div className="segment-bulk-actions">
          <span>{checkedIds.size}개 선택됨</span>
          <button type="button" onClick={handleBulkMarkReviewedClick} disabled={isBulkBusy}>
            검토완료로 표시
          </button>
          <button
            type="button"
            onClick={handleMerge}
            disabled={isBulkBusy || checkedIds.size < 2}
            data-tip="선택한 문장들을 시간 순서대로 하나로 합칩니다 (2개 이상 선택 필요)."
          >
            병합
          </button>
          <button type="button" className="danger-button" onClick={handleBulkDeleteClick} disabled={isBulkBusy}>
            삭제
          </button>
        </div>
      )}

      <div className="segment-filter-tabs">
        <span className="segment-filter-label">필터:</span>
        <button
          type="button"
          className={filter === 'all' ? 'segment-filter-tab active' : 'segment-filter-tab'}
          onClick={() => setFilter('all')}
        >
          전체
        </button>
        <button
          type="button"
          className={filter === 'unreviewed' ? 'segment-filter-tab active warn' : 'segment-filter-tab warn'}
          onClick={() => setFilter('unreviewed')}
          data-tip="아직 검토 표시가 없는 문장입니다."
        >
          미작업 ({unreviewedCount})
        </button>
        <button
          type="button"
          className={filter === 'needsCheck' ? 'segment-filter-tab active warn' : 'segment-filter-tab warn'}
          onClick={() => setFilter('needsCheck')}
          data-tip="전사/번역 신뢰도가 낮거나 자막 가독성 기준(초당 글자 수, 줄 길이, 지속시간)을 벗어나 사람이 확인해야 할 문장입니다."
        >
          검토 필요 ({needsCheckCount})
        </button>
        <button
          type="button"
          className={filter === 'ok' ? 'segment-filter-tab active' : 'segment-filter-tab'}
          onClick={() => setFilter('ok')}
        >
          괜찮음 ({okCount})
        </button>
        <button
          type="button"
          className={filter === 'reviewed' ? 'segment-filter-tab active ok' : 'segment-filter-tab ok'}
          onClick={() => setFilter('reviewed')}
          data-tip="사용자가 직접 검토 완료로 표시한 문장입니다."
        >
          완료 ({reviewedCount})
        </button>
      </div>

      {segments.length === 0 ? (
        <p className="hint-text">전사를 실행하면 이곳에 문장 목록이 표시됩니다.</p>
      ) : filteredSegments.length === 0 ? (
        <p className="hint-text">이 필터에 해당하는 문장이 없습니다.</p>
      ) : (
        <ul className="segment-list">
          {pageSegments.map((segment, indexInPage) => {
            const index = startIndex + indexInPage
            const isSelected = segment.id === selectedSegmentId
            const isPlaying = currentTime >= segment.start && currentTime < segment.end
            const pendingDiffs = countDiffsFor(segment.id, diffs)
            const flagged = needsCheck(segment)
            let rowClass = 'segment-list-item'
            if (isSelected) rowClass += ' selected'
            else if (isPlaying) rowClass += ' playing'
            if (segment.reviewed) rowClass += ' reviewed'
            return (
              <li key={segment.id} ref={isSelected ? activeRowRef : undefined}>
                <input
                  type="checkbox"
                  className="segment-select-checkbox"
                  checked={checkedIds.has(segment.id)}
                  onChange={() => toggleChecked(segment.id)}
                  onClick={(event) => event.stopPropagation()}
                  data-tip="병합/일괄 작업을 위해 이 문장을 선택합니다."
                />
                <button type="button" className={rowClass} onClick={() => onSelect(segment.id)}>
                  <span className="segment-index">{index + 1}</span>
                  <span className="segment-time">{formatClock(segment.start)}</span>
                  <span className="segment-text">
                    {segment.speaker && <span className="segment-speaker">{segment.speaker}</span>}
                    <span className="segment-text-original">{segment.text || '(빈 문장)'}</span>
                    {segment.translation && (
                      <span className="segment-text-translation">{segment.translation}</span>
                    )}
                  </span>
                  {flagged && (
                    <span className="quality-badge" data-tip={qualityTip(segment)}>
                      ⚠
                    </span>
                  )}
                  {pendingDiffs > 0 && <span className="segment-diff-badge">{pendingDiffs}</span>}
                  <span
                    className={segment.reviewed ? 'reviewed-toggle checked' : 'reviewed-toggle'}
                    onClick={(event) => handleToggleReviewed(segment, event)}
                    data-tip={segment.reviewed ? '검토 완료 표시 해제' : '검토 완료로 표시'}
                  >
                    {segment.reviewed ? '✓' : ''}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
