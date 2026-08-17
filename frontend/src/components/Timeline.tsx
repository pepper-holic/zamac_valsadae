import { memo, useEffect, useRef, useState } from 'react'
import type { Segment } from '../api/types'
import { formatClock } from '../utils/time'

type Props = {
  duration: number
  currentTime: number
  segments: Segment[]
  selectedSegmentId: string | null
  zoom: number
  onSeek: (time: number) => void
  onSelectSegment: (segmentId: string) => void
  onResizeSegment: (segmentId: string, edge: 'start' | 'end', time: number) => Promise<void>
}

type DragEdge = 'start' | 'end'

type DragState = {
  segmentId: string
  edge: DragEdge
  previewTime: number
  windowStart: number
  windowEnd: number
}

const MIN_SEGMENT_DURATION = 0.2
const TICK_COUNT = 6
const DETAIL_PADDING_RATIO = 0.5
const MIN_DETAIL_PADDING = 1

function buildTicks(duration: number): number[] {
  if (duration <= 0) return []
  return Array.from({ length: TICK_COUNT }, (_, i) => (duration * i) / (TICK_COUNT - 1))
}

function getDetailWindow(segment: Segment, duration: number): { windowStart: number; windowEnd: number } {
  const length = segment.end - segment.start
  const padding = Math.max(length * DETAIL_PADDING_RATIO, MIN_DETAIL_PADDING)
  return {
    windowStart: Math.max(0, segment.start - padding),
    windowEnd: Math.min(duration, segment.end + padding),
  }
}

type MarkersProps = {
  segments: Segment[]
  duration: number
  selectedSegmentId: string | null
  onSelectSegment: (segmentId: string) => void
  onSeek: (time: number) => void
}

// currentTime (which changes many times a second during playback) never
// affects a marker's own position/label - only the separate playhead div
// does. Without this memo boundary, every timeupdate re-renders one
// element per segment regardless, which is the whole file's transcript on
// a long recording.
const TimelineMarkers = memo(function TimelineMarkers({
  segments,
  duration,
  selectedSegmentId,
  onSelectSegment,
  onSeek,
}: MarkersProps) {
  return (
    <>
      {segments.map((segment) => (
        <div
          key={segment.id}
          role="button"
          tabIndex={0}
          className={segment.id === selectedSegmentId ? 'timeline-marker active' : 'timeline-marker'}
          style={{
            left: duration > 0 ? `${(segment.start / duration) * 100}%` : '0%',
            width: duration > 0 ? `${Math.max(((segment.end - segment.start) / duration) * 100, 0.3)}%` : '0%',
          }}
          title={segment.text}
          onClick={(event) => {
            event.stopPropagation()
            onSelectSegment(segment.id)
            onSeek(segment.start)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              onSelectSegment(segment.id)
              onSeek(segment.start)
            }
          }}
        />
      ))}
    </>
  )
})

export function Timeline({
  duration,
  currentTime,
  segments,
  selectedSegmentId,
  zoom,
  onSeek,
  onSelectSegment,
  onResizeSegment,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const detailTrackRef = useRef<HTMLDivElement>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)

  useEffect(() => {
    if (!dragState) return

    function handlePointerMove(event: PointerEvent) {
      const track = detailTrackRef.current
      if (!track || !dragState) return
      const windowDuration = dragState.windowEnd - dragState.windowStart
      if (windowDuration <= 0) return
      const rect = track.getBoundingClientRect()
      const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
      const time = dragState.windowStart + ratio * windowDuration
      setDragState((prev) => (prev ? { ...prev, previewTime: time } : prev))
    }

    function handlePointerUp() {
      setDragState((prev) => {
        if (prev) {
          onResizeSegment(prev.segmentId, prev.edge, prev.previewTime)
        }
        return null
      })
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
    // dragState.windowStart/windowEnd/edge don't change mid-drag, only previewTime does (updated via
    // setDragState functional updater above) - re-subscribing per-move would be wasteful.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragState?.segmentId, dragState?.edge, dragState?.windowStart, dragState?.windowEnd, onResizeSegment])

  function startDrag(segment: Segment, edge: DragEdge) {
    return (event: React.PointerEvent) => {
      event.stopPropagation()
      event.preventDefault()
      const { windowStart, windowEnd } = getDetailWindow(segment, duration)
      setDragState({
        segmentId: segment.id,
        edge,
        previewTime: edge === 'start' ? segment.start : segment.end,
        windowStart,
        windowEnd,
      })
    }
  }

  function handleTrackClick(event: React.MouseEvent<HTMLDivElement>) {
    const track = trackRef.current
    if (!track || duration === 0) return
    const rect = track.getBoundingClientRect()
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
    onSeek(ratio * duration)
  }

  function handleDetailTrackClick(event: React.MouseEvent<HTMLDivElement>) {
    const track = detailTrackRef.current
    if (!track || !detailWindow || detailWindowDuration <= 0) return
    const rect = track.getBoundingClientRect()
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
    onSeek(detailWindow.windowStart + ratio * detailWindowDuration)
  }

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0
  const ticks = buildTicks(duration)
  const selectedSegment = segments.find((segment) => segment.id === selectedSegmentId) ?? null
  const detailWindow = selectedSegment ? getDetailWindow(selectedSegment, duration) : null
  const detailWindowDuration = detailWindow ? detailWindow.windowEnd - detailWindow.windowStart : 0
  const isDraggingSelected = selectedSegment ? dragState?.segmentId === selectedSegment.id : false
  const detailStart =
    selectedSegment && isDraggingSelected && dragState?.edge === 'start'
      ? Math.min(dragState.previewTime, selectedSegment.end - MIN_SEGMENT_DURATION)
      : selectedSegment?.start ?? 0
  const detailEnd =
    selectedSegment && isDraggingSelected && dragState?.edge === 'end'
      ? Math.max(dragState.previewTime, selectedSegment.start + MIN_SEGMENT_DURATION)
      : selectedSegment?.end ?? 0

  return (
    <>
      <div className="timeline-scroll" style={{ overflowX: zoom > 1 ? 'auto' : 'hidden' }}>
        <div
          className="timeline-track"
          ref={trackRef}
          onClick={handleTrackClick}
          style={{ width: `${zoom * 100}%` }}
          data-tip="클릭한 지점으로 이동합니다. 색칠된 구간은 인식된 문장이며, 클릭하면 선택됩니다."
        >
          <TimelineMarkers
            segments={segments}
            duration={duration}
            selectedSegmentId={selectedSegmentId}
            onSelectSegment={onSelectSegment}
            onSeek={onSeek}
          />
          <div className="timeline-playhead" style={{ left: `${progressPercent}%` }} />
        </div>
        {ticks.length > 0 && (
          <div className="timeline-ticks" style={{ width: `${zoom * 100}%` }}>
            {ticks.map((time, index) => (
              <span key={index} className="timeline-tick" style={{ left: `${(time / duration) * 100}%` }}>
                {formatClock(time)}
              </span>
            ))}
          </div>
        )}
      </div>

      {selectedSegment && detailWindow && (
        <div className="timeline-detail">
          <div className="timeline-detail-label">
            선택한 문장 구간 조정{' '}
            <span className="timeline-detail-range">
              {formatClock(detailStart)} – {formatClock(detailEnd)}
            </span>
          </div>
          <div
            className="timeline-detail-track"
            ref={detailTrackRef}
            onClick={handleDetailTrackClick}
            data-tip="클릭한 지점으로 이동합니다. 양 끝을 드래그해 구간 시간을 조절합니다."
          >
            <div
              className="timeline-marker active"
              style={{
                left:
                  detailWindowDuration > 0
                    ? `${((detailStart - detailWindow.windowStart) / detailWindowDuration) * 100}%`
                    : '0%',
                width:
                  detailWindowDuration > 0
                    ? `${((detailEnd - detailStart) / detailWindowDuration) * 100}%`
                    : '0%',
              }}
            >
              <span
                className="timeline-marker-handle left"
                onPointerDown={startDrag(selectedSegment, 'start')}
                data-tip="드래그해서 시작 시간을 조절합니다."
              />
              <span
                className="timeline-marker-handle right"
                onPointerDown={startDrag(selectedSegment, 'end')}
                data-tip="드래그해서 종료 시간을 조절합니다."
              />
            </div>
            {currentTime >= detailWindow.windowStart && currentTime <= detailWindow.windowEnd && (
              <div
                className="timeline-playhead"
                style={{ left: `${((currentTime - detailWindow.windowStart) / detailWindowDuration) * 100}%` }}
              />
            )}
          </div>
        </div>
      )}
    </>
  )
}
