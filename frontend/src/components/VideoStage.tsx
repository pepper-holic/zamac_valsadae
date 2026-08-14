import { useState } from 'react'
import type { Segment, SubtitleStyle } from '../api/types'
import { wrapSubtitleText } from '../utils/subtitleWrap'
import {
  karaokeHighlightLength,
  subtitleContainerStyle,
  subtitleFadeOpacity,
  subtitleStyleToCss,
} from '../utils/subtitleStyle'
import { ASPECT_OPTIONS, useVideoAspectRatio } from '../hooks/useVideoAspectRatio'
import { TransportControls } from './TransportControls'

type SubtitleDisplayMode = 'both' | 'original' | 'translation'

const SUBTITLE_DISPLAY_OPTIONS: { id: SubtitleDisplayMode; label: string }[] = [
  { id: 'both', label: '원문+번역' },
  { id: 'original', label: '원문만' },
  { id: 'translation', label: '번역만' },
]

type Props = {
  videoRef: React.RefObject<HTMLVideoElement | null>
  src: string
  segments: Segment[]
  currentTime: number
  duration: number
  isPlaying: boolean
  playbackRate: number
  loopSegment: boolean
  subtitleStyle: SubtitleStyle
  onTimeUpdate: (time: number) => void
  onDurationChange: (duration: number) => void
  onPlayStateChange: (isPlaying: boolean) => void
  onRateChange: (rate: number) => void
  onLoopToggle: () => void
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
  currentTime,
  duration,
  isPlaying,
  playbackRate,
  loopSegment,
  subtitleStyle,
  onTimeUpdate,
  onDurationChange,
  onPlayStateChange,
  onRateChange,
  onLoopToggle,
}: Props) {
  const { aspectRatioId, setAspectRatioId, outerFrameStyle, innerFrameStyle, handleLoadedMetadata } =
    useVideoAspectRatio(src)
  const [subtitleDisplayMode, setSubtitleDisplayMode] = useState<SubtitleDisplayMode>('both')

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
      <div className="video-frame" style={outerFrameStyle}>
        <div className="video-frame-inner" style={innerFrameStyle}>
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
          {activeSegment && (() => {
            const showOriginal = subtitleDisplayMode !== 'translation' && activeSegment.text
            const showTranslation = subtitleDisplayMode !== 'original' && activeSegment.translation
            if (!showOriginal && !showTranslation) return null
            return (
              <div
                className="subtitle-overlay"
                style={{
                  ...subtitleContainerStyle(subtitleStyle),
                  opacity: subtitleFadeOpacity(activeSegment, currentTime, subtitleStyle),
                }}
              >
                {showTranslation && (
                  <span
                    className="subtitle-overlay-translation"
                    style={{
                      ...subtitleStyleToCss(subtitleStyle),
                      fontSize: `${Math.round(subtitleStyle.font_size * 0.75)}px`,
                    }}
                  >
                    {renderSubtitleText(activeSegment, showTranslation, currentTime, subtitleStyle)}
                  </span>
                )}
                {showOriginal && (
                  <span className="subtitle-overlay-text" style={subtitleStyleToCss(subtitleStyle)}>
                    {renderSubtitleText(activeSegment, showOriginal, currentTime, subtitleStyle)}
                  </span>
                )}
              </div>
            )
          })()}
        </div>
      </div>

      <div className="video-controls-row">
        <TransportControls
          isPlaying={isPlaying}
          playbackRate={playbackRate}
          loopSegment={loopSegment}
          onTogglePlay={togglePlay}
          onStep={step}
          onRateChange={(rate) => onRateChange(rate)}
          onLoopToggle={onLoopToggle}
        />

        <div className="video-frame-controls">
          <label
            className="aspect-ratio-select"
            data-tip="플랫폼에 맞춰 미리보기 화면비를 바꿉니다. 원본과 비율이 다르면 남는 영역은 검정으로 채워집니다."
          >
            비율
            <select value={aspectRatioId} onChange={(event) => setAspectRatioId(event.target.value)}>
              {ASPECT_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label
            className="subtitle-display-select"
            data-tip="미리보기에 표시할 자막 종류를 선택합니다."
          >
            자막
            <select
              value={subtitleDisplayMode}
              onChange={(event) => setSubtitleDisplayMode(event.target.value as SubtitleDisplayMode)}
            >
              {SUBTITLE_DISPLAY_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <p className="keyboard-hint">단축키: Space 재생/일시정지 · ←/→ 1초 이동 · ↑/↓ 이전/다음 문장</p>
    </section>
  )
}
