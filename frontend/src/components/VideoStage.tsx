import { useEffect, useRef, useState } from 'react'
import type { Segment } from '../api/types'
import { formatTimestamp } from '../utils/time'
import { computeWaveformPeaks } from '../utils/waveform'

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
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]
const STEP_SECONDS = 1
const WAVEFORM_POINTS = 300
const MIN_SEGMENT_DURATION = 0.2

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
  const [waveformPeaks, setWaveformPeaks] = useState<number[] | null>(null)
  const [dragState, setDragState] = useState<DragState | null>(null)

  useEffect(() => {
    let cancelled = false
    setWaveformPeaks(null)
    computeWaveformPeaks(src, WAVEFORM_POINTS)
      .then((peaks) => {
        if (!cancelled) setWaveformPeaks(peaks)
      })
      .catch(() => {
        // 브라우저가 이 미디어의 오디오 트랙을 디코딩하지 못하면(코덱 등) 파형 없이
        // 진행합니다 - 타임라인 클릭/드래그 편집은 파형 없이도 그대로 동작합니다.
      })
    return () => {
      cancelled = true
    }
  }, [src])

  useEffect(() => {
    if (!dragState) return

    function handlePointerMove(event: PointerEvent) {
      const track = trackRef.current
      if (!track || duration === 0 || !dragState) return
      const rect = track.getBoundingClientRect()
      const ratio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1)
      const time = ratio * duration
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
    // dragState.segmentId/edge don't change mid-drag, only previewTime does (updated via setDragState
    // functional updater above) - re-subscribing per-move would be wasteful.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragState?.segmentId, dragState?.edge, duration, onResizeSegment])

  function startDrag(segmentId: string, edge: DragEdge, currentValue: number) {
    return (event: React.PointerEvent) => {
      event.stopPropagation()
      event.preventDefault()
      setDragState({ segmentId, edge, previewTime: currentValue })
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
  const activeSegment = segments.find(
    (segment) => currentTime >= segment.start && currentTime < segment.end,
  )

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
          <div className="subtitle-overlay">
            {activeSegment.translation && (
              <span className="subtitle-overlay-translation">{activeSegment.translation}</span>
            )}
            <span className="subtitle-overlay-text">{activeSegment.text}</span>
          </div>
        )}
      </div>

      <div className="timecode">
        <span className="timecode-current">{formatTimestamp(currentTime)}</span>
        <span className="timecode-sep">/</span>
        <span className="timecode-total">{formatTimestamp(duration || 0)}</span>
      </div>

      <div
        className="timeline-track"
        ref={trackRef}
        onClick={handleTrackClick}
        data-tip="클릭한 지점으로 이동합니다. 색칠된 구간은 인식된 문장이며, 양 끝을 드래그해 시간을 조절할 수 있습니다."
      >
        {waveformPeaks && (
          <div className="timeline-waveform">
            {waveformPeaks.map((peak, index) => (
              <span key={index} className="timeline-waveform-bar" style={{ height: `${Math.max(peak * 100, 2)}%` }} />
            ))}
          </div>
        )}
        {segments.map((segment) => {
          const isDraggingThis = dragState?.segmentId === segment.id
          const start =
            isDraggingThis && dragState.edge === 'start'
              ? Math.min(dragState.previewTime, segment.end - MIN_SEGMENT_DURATION)
              : segment.start
          const end =
            isDraggingThis && dragState.edge === 'end'
              ? Math.max(dragState.previewTime, segment.start + MIN_SEGMENT_DURATION)
              : segment.end
          return (
            <div
              key={segment.id}
              role="button"
              tabIndex={0}
              className={segment.id === selectedSegmentId ? 'timeline-marker active' : 'timeline-marker'}
              style={{
                left: duration > 0 ? `${(start / duration) * 100}%` : '0%',
                width: duration > 0 ? `${Math.max(((end - start) / duration) * 100, 0.3)}%` : '0%',
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
            >
              <span
                className="timeline-marker-handle left"
                onPointerDown={startDrag(segment.id, 'start', segment.start)}
                data-tip="드래그해서 시작 시간을 조절합니다."
              />
              <span
                className="timeline-marker-handle right"
                onPointerDown={startDrag(segment.id, 'end', segment.end)}
                data-tip="드래그해서 종료 시간을 조절합니다."
              />
            </div>
          )
        })}
        <div className="timeline-playhead" style={{ left: `${progressPercent}%` }} />
      </div>

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
