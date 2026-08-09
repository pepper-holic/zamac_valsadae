import { describe, expect, it } from 'vitest'
import type { Segment, SubtitleStyle } from '../api/types'
import { karaokeHighlightLength, subtitleFadeOpacity } from './subtitleStyle'

function makeStyle(overrides: Partial<SubtitleStyle> = {}): SubtitleStyle {
  return {
    font_family: 'Pretendard',
    font_size: 32,
    font_weight: 'bold',
    color: '#FFFFFF',
    outline_color: '#000000',
    outline_width: 2,
    background: null,
    position: 'bottom',
    fade_in_ms: 0,
    fade_out_ms: 0,
    karaoke_highlight: false,
    auto_line_break: false,
    max_line_chars: 42,
    ...overrides,
  }
}

function makeSegment(overrides: Partial<Segment> = {}): Segment {
  return {
    id: 'seg-1',
    start: 10,
    end: 12,
    text: 'hello world',
    speaker: null,
    translation: null,
    transcription_quality: null,
    transcription_quality_reason: null,
    translation_quality: null,
    translation_quality_reason: null,
    readability_flag: null,
    readability_reason: null,
    reviewed: false,
    words: [],
    ...overrides,
  }
}

describe('subtitleFadeOpacity', () => {
  it('returns full opacity when no fade is configured', () => {
    const segment = makeSegment({ start: 0, end: 2 })
    expect(subtitleFadeOpacity(segment, 1, makeStyle())).toBe(1)
  })

  it('ramps up opacity during fade-in', () => {
    const segment = makeSegment({ start: 10, end: 12 })
    const style = makeStyle({ fade_in_ms: 500 })
    // 250ms into a 500ms fade-in -> 50%
    expect(subtitleFadeOpacity(segment, 10.25, style)).toBeCloseTo(0.5)
  })

  it('is fully visible once fade-in completes', () => {
    const segment = makeSegment({ start: 10, end: 12 })
    const style = makeStyle({ fade_in_ms: 500 })
    expect(subtitleFadeOpacity(segment, 10.6, style)).toBe(1)
  })

  it('ramps down opacity during fade-out', () => {
    const segment = makeSegment({ start: 10, end: 12 })
    const style = makeStyle({ fade_out_ms: 500 })
    // 250ms before the end of a 500ms fade-out -> 50%
    expect(subtitleFadeOpacity(segment, 11.75, style)).toBeCloseTo(0.5)
  })

  it('never goes negative past the segment end', () => {
    const segment = makeSegment({ start: 10, end: 12 })
    const style = makeStyle({ fade_out_ms: 500 })
    expect(subtitleFadeOpacity(segment, 13, style)).toBe(0)
  })
})

describe('karaokeHighlightLength', () => {
  it('falls back to a duration-ratio approximation when there are no words', () => {
    const segment = makeSegment({ start: 0, end: 4, text: 'abcdefgh', words: [] })
    // halfway through the segment -> half the text highlighted
    expect(karaokeHighlightLength(segment, 2, 'abcdefgh')).toBe(4)
  })

  it('uses word-level timestamps when available and the text matches the segment', () => {
    const segment = makeSegment({
      start: 0,
      end: 2,
      text: 'hi there',
      words: [
        { text: 'hi', start: 0, end: 0.5 },
        { text: 'there', start: 0.5, end: 1.5 },
      ],
    })
    // fully past the first word, 20% into the second word ("there")
    expect(karaokeHighlightLength(segment, 0.7, 'hi there')).toBe(4)
    // fully past both words
    expect(karaokeHighlightLength(segment, 1.6, 'hi there')).toBe('hi there'.length)
  })

  it('falls back to the approximation when the text differs from the segment (e.g. a translation)', () => {
    const segment = makeSegment({
      start: 0,
      end: 2,
      text: 'hi there',
      translation: '안녕하세요',
      words: [{ text: 'hi', start: 0, end: 0.5 }],
    })
    // translation text isn't the word-aligned segment.text, so this should use the ratio fallback
    const result = karaokeHighlightLength(segment, 1, '안녕하세요')
    expect(result).toBe(Math.round('안녕하세요'.length * 0.5))
  })
})
