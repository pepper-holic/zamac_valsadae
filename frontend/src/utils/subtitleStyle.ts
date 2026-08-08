import type { CSSProperties } from 'react'
import type { Segment, SubtitleStyle, Word } from '../api/types'

function hexToRgba(hex: string, alpha: number): string {
  const normalized = hex.replace('#', '')
  const bigint = Number.parseInt(normalized, 16)
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function subtitleStyleToCss(style: SubtitleStyle): CSSProperties {
  const outline = `${style.outline_width}px`
  return {
    fontFamily: style.font_family,
    fontSize: `${style.font_size}px`,
    fontWeight: style.font_weight === 'bold' ? 700 : 400,
    color: style.color,
    backgroundColor: style.background ? hexToRgba(style.background, 0.72) : 'transparent',
    textShadow:
      style.outline_width > 0
        ? [
            `-${outline} -${outline} 0 ${style.outline_color}`,
            `${outline} -${outline} 0 ${style.outline_color}`,
            `-${outline} ${outline} 0 ${style.outline_color}`,
            `${outline} ${outline} 0 ${style.outline_color}`,
          ].join(', ')
        : undefined,
  }
}

export function subtitleContainerStyle(style: SubtitleStyle): CSSProperties {
  if (style.position === 'top') {
    return { top: '20px', bottom: 'auto' }
  }
  // 'custom' 위치는 별도 좌표 저장이 없으므로 하단 배치로 대체합니다.
  return { bottom: '20px', top: 'auto' }
}

// fade_in_ms/fade_out_ms를 세그먼트 진입/이탈 시점 기준 opacity로 환산합니다.
export function subtitleFadeOpacity(
  segment: Segment,
  currentTime: number,
  style: SubtitleStyle,
): number {
  const elapsedMs = (currentTime - segment.start) * 1000
  const remainingMs = (segment.end - currentTime) * 1000

  if (style.fade_in_ms > 0 && elapsedMs < style.fade_in_ms) {
    return Math.max(elapsedMs / style.fade_in_ms, 0)
  }
  if (style.fade_out_ms > 0 && remainingMs < style.fade_out_ms) {
    return Math.max(remainingMs / style.fade_out_ms, 0)
  }
  return 1
}

// word.text는 앞뒤 공백이 제거된 상태로 저장되므로, 단순히 word 길이를 더하면
// 단어 사이 공백/구두점만큼 실제 text 위치보다 뒤처집니다. text 안에서 각
// word의 실제 위치를 순서대로 찾아 그 위치를 기준으로 강조 길이를 계산합니다.
function karaokeHighlightLengthFromWords(words: Word[], currentTime: number, text: string): number {
  let searchFrom = 0
  let highlightEnd = 0
  for (const word of words) {
    const wordStart = text.indexOf(word.text, searchFrom)
    if (wordStart === -1) break
    const wordEnd = wordStart + word.text.length
    searchFrom = wordEnd

    if (currentTime >= word.end) {
      highlightEnd = wordEnd
      continue
    }
    if (currentTime > word.start) {
      const wordDuration = Math.max(word.end - word.start, 0.001)
      const ratio = (currentTime - word.start) / wordDuration
      highlightEnd = wordStart + Math.round(word.text.length * ratio)
    }
    break
  }
  return Math.min(highlightEnd, text.length)
}

// 재생 경과 비율만큼 텍스트 앞부분을 강조하는 근사 방식 - 단어별 타임스탬프가
// 없는 세그먼트(또는 번역문처럼 word 정렬이 없는 텍스트)의 폴백입니다.
function karaokeHighlightLengthApprox(segment: Segment, currentTime: number, text: string): number {
  const duration = segment.end - segment.start
  if (duration <= 0) return text.length
  const ratio = Math.min(Math.max((currentTime - segment.start) / duration, 0), 1)
  return Math.round(text.length * ratio)
}

export function karaokeHighlightLength(segment: Segment, currentTime: number, text: string): number {
  if (segment.words.length > 0 && text === segment.text) {
    return karaokeHighlightLengthFromWords(segment.words, currentTime, text)
  }
  return karaokeHighlightLengthApprox(segment, currentTime, text)
}
