import { useEffect, useRef } from 'react'
import type { Segment } from '../api/types'
import { formatTimestamp } from '../utils/time'
import { useTimelineZoom } from '../hooks/useTimelineZoom'
import { Timeline } from './Timeline'

type Props = {
  duration: number
  currentTime: number
  segments: Segment[]
  selectedSegmentId: string | null
  onSeek: (time: number) => void
  onSelectSegment: (segmentId: string) => void
  onResizeSegment: (segmentId: string, edge: 'start' | 'end', time: number) => Promise<void>
}

export function ReviewTimeline({
  duration,
  currentTime,
  segments,
  selectedSegmentId,
  onSeek,
  onSelectSegment,
  onResizeSegment,
}: Props) {
  const { zoom, zoomIn, zoomOut, atMin, atMax } = useTimelineZoom()
  const scrubberRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrubberRef.current
    if (!el) return
    function handleWheel(event: WheelEvent) {
      if (!event.ctrlKey) return
      event.preventDefault()
      if (event.deltaY < 0) zoomIn()
      else if (event.deltaY > 0) zoomOut()
    }
    el.addEventListener('wheel', handleWheel, { passive: false })
    return () => el.removeEventListener('wheel', handleWheel)
  }, [zoomIn, zoomOut])

  return (
    <div className="review-timeline">
      <div className="timecode">
        <span className="timecode-current">{formatTimestamp(currentTime)}</span>
        <span className="timecode-sep">/</span>
        <span className="timecode-total">{formatTimestamp(duration || 0)}</span>
        <div className="timeline-zoom-controls" data-tip="타임라인을 확대/축소합니다.">
          <button type="button" onClick={zoomOut} disabled={atMin} aria-label="타임라인 축소">
            −
          </button>
          <span className="timeline-zoom-level">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={zoomIn} disabled={atMax} aria-label="타임라인 확대">
            +
          </button>
        </div>
      </div>

      <div className="review-timeline-scrubber" ref={scrubberRef} data-tip="Ctrl + 스크롤로 타임라인을 확대/축소합니다.">
        <Timeline
          duration={duration}
          currentTime={currentTime}
          segments={segments}
          selectedSegmentId={selectedSegmentId}
          zoom={zoom}
          onSeek={onSeek}
          onSelectSegment={onSelectSegment}
          onResizeSegment={onResizeSegment}
        />
      </div>
    </div>
  )
}
