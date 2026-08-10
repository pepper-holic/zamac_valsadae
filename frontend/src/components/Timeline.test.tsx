import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Segment } from '../api/types'
import { Timeline } from './Timeline'

function makeSegment(overrides: Partial<Segment> = {}): Segment {
  return {
    id: 'seg-1',
    start: 0,
    end: 2,
    text: 'hello',
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

function makeProps(overrides: Partial<Parameters<typeof Timeline>[0]> = {}) {
  return {
    duration: 10,
    currentTime: 0,
    segments: [] as Segment[],
    selectedSegmentId: null,
    zoom: 1,
    onSeek: vi.fn(),
    onSelectSegment: vi.fn(),
    onResizeSegment: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('Timeline', () => {
  it('renders one marker per segment, positioned by start/duration', () => {
    const segments = [
      makeSegment({ id: 'a', start: 0, end: 2 }),
      makeSegment({ id: 'b', start: 5, end: 7 }),
    ]
    render(<Timeline {...makeProps({ segments, duration: 10 })} />)

    const markers = document.querySelectorAll('.timeline-marker')
    expect(markers).toHaveLength(2)
    expect((markers[1] as HTMLElement).style.left).toBe('50%')
  })

  it('marks the selected segment with the active class', () => {
    const segments = [makeSegment({ id: 'a' }), makeSegment({ id: 'b', start: 5, end: 7 })]
    render(<Timeline {...makeProps({ segments, selectedSegmentId: 'b' })} />)

    const markers = document.querySelectorAll('.timeline-marker')
    expect(markers[0].className).not.toContain('active')
    expect(markers[1].className).toContain('active')
  })

  it('calls onSelectSegment and onSeek when a marker is clicked', async () => {
    const user = userEvent.setup()
    const onSelectSegment = vi.fn()
    const onSeek = vi.fn()
    const segments = [makeSegment({ id: 'a', start: 3, end: 4 })]
    render(<Timeline {...makeProps({ segments, onSelectSegment, onSeek })} />)

    await user.click(screen.getByTitle('hello'))

    expect(onSelectSegment).toHaveBeenCalledWith('a')
    expect(onSeek).toHaveBeenCalledWith(3)
  })

  it('scales the track width with the zoom prop', () => {
    const { rerender } = render(<Timeline {...makeProps({ zoom: 1 })} />)
    expect((document.querySelector('.timeline-track') as HTMLElement).style.width).toBe('100%')

    rerender(<Timeline {...makeProps({ zoom: 3 })} />)
    expect((document.querySelector('.timeline-track') as HTMLElement).style.width).toBe('300%')
  })

  it('shows the detail track only when a segment is selected', () => {
    const segments = [makeSegment({ id: 'a', start: 0, end: 2 })]
    const { rerender } = render(<Timeline {...makeProps({ segments, selectedSegmentId: null })} />)
    expect(document.querySelector('.timeline-detail')).toBeNull()

    rerender(<Timeline {...makeProps({ segments, selectedSegmentId: 'a' })} />)
    expect(document.querySelector('.timeline-detail')).not.toBeNull()
  })
})
