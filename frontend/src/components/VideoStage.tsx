import { useEffect, useRef, useState } from 'react'
import type { Segment, SubtitleStyle } from '../api/types'
import { formatClock, formatTimestamp } from '../utils/time'
import { wrapSubtitleText } from '../utils/subtitleWrap'
import {
  karaokeHighlightLength,
  subtitleContainerStyle,
  subtitleFadeOpacity,
  subtitleStyleToCss,
} from '../utils/subtitleStyle'

type Props = {
  videoRef: React.RefObject<HTMLVideoElement | null>
  src: string
  segments: Segment[]
  selectedSegmentId: string | null
  currentTime: number
  duration: number
  isPlaying: boolean
  playbackRate: number
  loopSegment: boolean
  subtitleStyle: SubtitleStyle
  onTimeUpdate: (time: number) => void
  onDurationChange: (duration: number) => void
  onPlayStateChange: (isPlaying: boolean) => void
  onSeek: (time: number) => void
  onRateChange: (rate: number) => void
  onLoopToggle: () => void
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

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]
const STEP_SECONDS = 1
const MIN_SEGMENT_DURATION = 0.2
const ZOOM_LEVELS = [1, 1.5, 2, 3, 4, 6, 8]
const MIN_ZOOM_INDEX = 0
const MAX_ZOOM_INDEX = ZOOM_LEVELS.length - 1
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

function renderSubtitleText(
  segment: Segment,
  text: string,
  currentTime: number,
  style: SubtitleStyle,
): React.ReactNode {
  if (!style.karaoke_highlight) {
    // 카라오케 강조는 원문 글자 위치 기준으로 계산되므로, 줄바꿈은 강조가
    // 꺼져 있을 때만 미리보기에 적용합니다 (렌더 결과와 다를 수 있는 트레이드오프).
    return style.auto_line_break ? wrapSubtitleText(text, style.max_line_chars) : text
  }
  const highlightLength = karaokeHighlightLength(segment, currentTime, text)
  return (
    <>
      <span className="subtitle-karaoke-highlight">{text.slice(0, highlightLength)}</span>
      {text.slice(highlightLength)}
    </>
  )
}

export function VideoStage({
  videoRef,
  src,
  segments,
  selectedSegmentId,
  currentTime,
  duration,
  isPlaying,
  playbackRate,
  loopSegment,
  subtitleStyle,
  onTimeUpdate,
  onDurationChange,
  onPlayStateChange,
  onSeek,
  onRateChange,
  onLoopToggle,
  onSelectSegment,
  onResizeSegment,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const detailTrackRef = useRef<HTMLDivElement>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)
  const [zoomIndex, setZoomIndex] = useState(MIN_ZOOM_INDEX)
  const zoom = ZOOM_LEVELS[zoomIndex]

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

  function togglePlay() {
    const video = videoRef.current
    if (!video) return
    if (video.paused) {
      video.play()
    } else {
      video.pause()
    }
  }

  function step(deltaSeconds: number) {
    const video = videoRef.current
    if (!video) return
    video.currentTime = Math.min(Math.max(video.currentTime + deltaSeconds, 0), duration)
  }

  function handleTrackClick(event: React.MouseEvent<HTMLDivElement>) {
    const track = trackRef.current
    if (!track || duration === 0) return
    const rect = track.getBoundingClientRect()
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
    onSeek(ratio * duration)
  }

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0
  const ticks = buildTicks(duration)
  const activeSegment = segments.find(
    (segment) => currentTime >= segment.start && currentTime < segment.end,
  )
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

  function handleDetailTrackClick(event: React.MouseEvent<HTMLDivElement>) {
    const track = detailTrackRef.current
    if (!track || !detailWindow || detailWindowDuration <= 0) return
    const rect = track.getBoundingClientRect()
    const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
    onSeek(detailWindow.windowStart + ratio * detailWindowDuration)
  }

  return (
    <section className="video-stage">
      <div className="video-frame">
        <video
          ref={videoRef}
          className="video-player"
          src={src}
          onTimeUpdate={(event) => onTimeUpdate(event.currentTarget.currentTime)}
          onDurationChange={(event) => onDurationChange(event.currentTarget.duration)}
          onPlay={() => onPlayStateChange(true)}
          onPause={() => onPlayStateChange(false)}
        />
        {activeSegment && (activeSegment.text || activeSegment.translation) && (
          <div
            className="subtitle-overlay"
            style={{
              ...subtitleContainerStyle(subtitleStyle),
              opacity: subtitleFadeOpacity(activeSegment, currentTime, subtitleStyle),
            }}
          >
            {activeSegment.translation && (
              <span
                className="subtitle-overlay-translation"
                style={{
                  ...subtitleStyleToCss(subtitleStyle),
                  fontSize: `${Math.round(subtitleStyle.font_size * 0.75)}px`,
                }}
              >
                {renderSubtitleText(activeSegment, activeSegment.translation, currentTime, subtitleStyle)}
              </span>
            )}
            <span className="subtitle-overlay-text" style={subtitleStyleToCss(subtitleStyle)}>
              {renderSubtitleText(activeSegment, activeSegment.text, currentTime, subtitleStyle)}
            </span>
          </div>
        )}
      </div>

      <div className="timecode">
        <span className="timecode-current">{formatTimestamp(currentTime)}</span>
        <span className="timecode-sep">/</span>
        <span className="timecode-total">{formatTimestamp(duration || 0)}</span>
        <div className="timeline-zoom-controls" data-tip="타임라인을 확대/축소합니다.">
          <button
            type="button"
            onClick={() => setZoomIndex((prev) => Math.max(prev - 1, MIN_ZOOM_INDEX))}
            disabled={zoomIndex === MIN_ZOOM_INDEX}
            aria-label="타임라인 축소"
          >
            −
          </button>
          <span className="timeline-zoom-level">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            onClick={() => setZoomIndex((prev) => Math.min(prev + 1, MAX_ZOOM_INDEX))}
            disabled={zoomIndex === MAX_ZOOM_INDEX}
            aria-label="타임라인 확대"
          >
            +
          </button>
        </div>
      </div>

      <div className="timeline-scroll" style={{ overflowX: zoom > 1 ? 'auto' : 'hidden' }}>
        <div
          className="timeline-track"
          ref={trackRef}
          onClick={handleTrackClick}
          style={{ width: `${zoom * 100}%` }}
          data-tip="클릭한 지점으로 이동합니다. 색칠된 구간은 인식된 문장이며, 클릭하면 선택됩니다."
        >
          {segments.map((segment) => (
            <div
              key={segment.id}
              role="button"
              tabIndex={0}
              className={segment.id === selectedSegmentId ? 'timeline-marker active' : 'timeline-marker'}
              style={{
                left: duration > 0 ? `${(segment.start / duration) * 100}%` : '0%',
                width:
                  duration > 0 ? `${Math.max(((segment.end - segment.start) / duration) * 100, 0.3)}%` : '0%',
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
          <div className="timeline-playhead" style={{ left: `${progressPercent}%` }} />
        </div>
        {ticks.length > 0 && (
          <div className="timeline-ticks" style={{ width: `${zoom * 100}%` }}>
            {ticks.map((time, index) => (
              <span
                key={index}
                className="timeline-tick"
                style={{ left: `${(time / duration) * 100}%` }}
              >
                {formatClock(time)}
              </span>
            ))}
          </div>
        )}
      </div>

      {selectedSegment && detailWindow && (
        <div className="timeline-detail">
          <div className="timeline-detail-label">
            선택한 문장 구간 조정 <span className="timeline-detail-range">{formatClock(detailStart)} – {formatClock(detailEnd)}</span>
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
                left: detailWindowDuration > 0 ? `${((detailStart - detailWindow.windowStart) / detailWindowDuration) * 100}%` : '0%',
                width: detailWindowDuration > 0 ? `${((detailEnd - detailStart) / detailWindowDuration) * 100}%` : '0%',
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

      <div className="transport-controls">
        <button type="button" onClick={() => step(-STEP_SECONDS)} data-tip="1초 뒤로 이동 (단축키: ←)">
          ◀◀ 1s
        </button>
        <button
          type="button"
          className="play-button"
          onClick={togglePlay}
          data-tip="재생/일시정지 (단축키: Space)"
        >
          {isPlaying ? '일시정지' : '재생'}
        </button>
        <button type="button" onClick={() => step(STEP_SECONDS)} data-tip="1초 앞으로 이동 (단축키: →)">
          1s ▶▶
        </button>

        <label className="rate-select" data-tip="재생 속도를 조절합니다.">
          속도
          <select
            value={playbackRate}
            onChange={(event) => onRateChange(Number(event.target.value))}
          >
            {PLAYBACK_RATES.map((rate) => (
              <option key={rate} value={rate}>
                {rate}x
              </option>
            ))}
          </select>
        </label>

        <label
          className="checkbox-label"
          data-tip="켜두면 선택한 문장의 시작~종료 구간을 자동으로 반복 재생합니다."
        >
          <input type="checkbox" checked={loopSegment} onChange={onLoopToggle} />
          현재 구간 반복
        </label>
      </div>

      <p className="keyboard-hint">
        단축키: Space 재생/일시정지 · ←/→ 1초 이동 · ↑/↓ 이전/다음 문장
      </p>
    </section>
  )
}
