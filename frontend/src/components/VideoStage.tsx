import { useRef } from 'react'
import type { Segment } from '../api/types'
import { formatTimestamp } from '../utils/time'

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
}

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]
const STEP_SECONDS = 1

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
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null)

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

  return (
    <section className="video-stage">
      <video
        ref={videoRef}
        className="video-player"
        src={src}
        onTimeUpdate={(event) => onTimeUpdate(event.currentTarget.currentTime)}
        onDurationChange={(event) => onDurationChange(event.currentTarget.duration)}
        onPlay={() => onPlayStateChange(true)}
        onPause={() => onPlayStateChange(false)}
      />

      <div className="timecode">
        <span className="timecode-current">{formatTimestamp(currentTime)}</span>
        <span className="timecode-sep">/</span>
        <span className="timecode-total">{formatTimestamp(duration || 0)}</span>
      </div>

      <div
        className="timeline-track"
        ref={trackRef}
        onClick={handleTrackClick}
        data-tip="클릭한 지점으로 이동합니다. 색칠된 구간은 인식된 문장입니다."
      >
        {segments.map((segment) => (
          <button
            key={segment.id}
            type="button"
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
          />
        ))}
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
