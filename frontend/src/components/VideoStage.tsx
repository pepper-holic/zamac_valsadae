import type { Segment, SubtitleStyle } from '../api/types'
import { formatTimestamp } from '../utils/time'
import { wrapSubtitleText } from '../utils/subtitleWrap'
import {
  karaokeHighlightLength,
  subtitleContainerStyle,
  subtitleFadeOpacity,
  subtitleStyleToCss,
} from '../utils/subtitleStyle'
import { ASPECT_OPTIONS, useVideoAspectRatio } from '../hooks/useVideoAspectRatio'
import { useTimelineZoom } from '../hooks/useTimelineZoom'
import { Timeline } from './Timeline'
import { TransportControls } from './TransportControls'

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
  const { aspectRatioId, setAspectRatioId, videoFrameStyle, handleLoadedMetadata } = useVideoAspectRatio(src)
  const { zoom, zoomIn, zoomOut, atMin, atMax } = useTimelineZoom()

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

  const activeSegment = segments.find(
    (segment) => currentTime >= segment.start && currentTime < segment.end,
  )

  return (
    <section className="video-stage">
      <div className="video-frame-controls">
        <label
          className="aspect-ratio-select"
          data-tip="플랫폼에 맞춰 미리보기 화면비를 바꿉니다. 원본과 비율이 다르면 남는 영역은 검정으로 채워집니다."
        >
          화면비율
          <select value={aspectRatioId} onChange={(event) => setAspectRatioId(event.target.value)}>
            {ASPECT_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="video-frame" style={videoFrameStyle}>
        <video
          ref={videoRef}
          className="video-player"
          src={src}
          onTimeUpdate={(event) => onTimeUpdate(event.currentTarget.currentTime)}
          onDurationChange={(event) => onDurationChange(event.currentTarget.duration)}
          onLoadedMetadata={handleLoadedMetadata}
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
          <button type="button" onClick={zoomOut} disabled={atMin} aria-label="타임라인 축소">
            −
          </button>
          <span className="timeline-zoom-level">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={zoomIn} disabled={atMax} aria-label="타임라인 확대">
            +
          </button>
        </div>
      </div>

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

      <TransportControls
        isPlaying={isPlaying}
        playbackRate={playbackRate}
        loopSegment={loopSegment}
        onTogglePlay={togglePlay}
        onStep={step}
        onRateChange={(rate) => onRateChange(rate)}
        onLoopToggle={onLoopToggle}
      />

      <p className="keyboard-hint">단축키: Space 재생/일시정지 · ←/→ 1초 이동 · ↑/↓ 이전/다음 문장</p>
    </section>
  )
}
