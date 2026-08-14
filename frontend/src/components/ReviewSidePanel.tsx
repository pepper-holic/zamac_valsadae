import { useState } from 'react'
import type { MediaItem, Project, ReviewDiffEntry, Segment } from '../api/types'
import { SegmentDetailPanel } from './SegmentDetailPanel'
import { SubtitleStylePanel } from './SubtitleStylePanel'

type Tab = 'detail' | 'style'

const TABS: { key: Tab; label: string }[] = [
  { key: 'detail', label: '상세 검수' },
  { key: 'style', label: '스타일' },
]

type Props = {
  project: Project
  item: MediaItem
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
  onSplitSegment: (splitAt: number) => Promise<void>
  onStyleUpdated: (project: Project) => void
}

export function ReviewSidePanel({
  project,
  item,
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
  onSplitSegment,
  onStyleUpdated,
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('detail')

  return (
    <div className="review-side-panel">
      <div className="review-side-panel-tabs" role="tablist" aria-label="스타일/상세검수 전환">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={activeTab === tab.key ? 'review-side-panel-tab active' : 'review-side-panel-tab'}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="review-side-panel-body">
        {activeTab === 'detail' ? (
          <SegmentDetailPanel
            project={project}
            item={item}
            segment={segment}
            segmentPosition={segmentPosition}
            currentTime={currentTime}
            segmentDiffs={segmentDiffs}
            onSegmentSaved={onSegmentSaved}
            onSegmentDeleted={onSegmentDeleted}
            onNavigate={onNavigate}
            onSeek={onSeek}
            onPlaySegment={onPlaySegment}
            onAcceptDiff={onAcceptDiff}
            onRejectDiff={onRejectDiff}
            onSplitSegment={onSplitSegment}
          />
        ) : (
          <SubtitleStylePanel project={project} onStyleUpdated={onStyleUpdated} />
        )}
      </div>
    </div>
  )
}
