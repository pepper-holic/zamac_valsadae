import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Segment } from '../api/types'
import { SegmentList } from './SegmentList'

vi.mock('../api/client', () => ({
  detectFillerSegments: vi.fn(),
  updateSegment: vi.fn(),
}))

function makeSegment(overrides: Partial<Segment> = {}): Segment {
  return {
    id: 'seg-1',
    start: 0,
    end: 2,
    text: 'hello world',
    speaker: null,
    translation: null,
    transcription_quality: 'good',
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

function makeProps(overrides: Partial<Parameters<typeof SegmentList>[0]> = {}) {
  return {
    projectId: 'proj-1',
    itemId: 'item-1',
    segments: [] as Segment[],
    selectedSegmentId: null,
    currentTime: 0,
    diffs: [],
    onSelect: vi.fn(),
    onSegmentSaved: vi.fn(),
    onMergeSegments: vi.fn().mockResolvedValue(undefined),
    onFindReplace: vi.fn().mockResolvedValue(undefined),
    onBulkDelete: vi.fn().mockResolvedValue(undefined),
    onBulkMarkReviewed: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('SegmentList', () => {
  beforeEach(() => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows an empty-state hint when there are no segments at all', () => {
    render(<SegmentList {...makeProps({ segments: [] })} />)
    expect(screen.getByText('전사를 실행하면 이곳에 문장 목록이 표시됩니다.')).toBeInTheDocument()
  })

  it('renders one row per segment with its index and text', () => {
    const segments = [
      makeSegment({ id: 'a', text: '첫 문장' }),
      makeSegment({ id: 'b', text: '둘째 문장' }),
    ]
    render(<SegmentList {...makeProps({ segments })} />)
    expect(screen.getByText('첫 문장')).toBeInTheDocument()
    expect(screen.getByText('둘째 문장')).toBeInTheDocument()
  })

  it('filters to only reviewed segments when the 완료 tab is clicked', async () => {
    const user = userEvent.setup()
    const segments = [
      makeSegment({ id: 'a', text: '검토 완료된 문장', reviewed: true }),
      makeSegment({ id: 'b', text: '미검토 문장', reviewed: false }),
    ]
    render(<SegmentList {...makeProps({ segments })} />)

    await user.click(screen.getByRole('button', { name: /완료 \(1\)/ }))

    expect(screen.getByText('검토 완료된 문장')).toBeInTheDocument()
    expect(screen.queryByText('미검토 문장')).not.toBeInTheDocument()
  })

  it('filters to segments needing check when the 검토 필요 tab is clicked', async () => {
    const user = userEvent.setup()
    const segments = [
      makeSegment({ id: 'a', text: '문제 있는 문장', transcription_quality: 'check' }),
      makeSegment({ id: 'b', text: '괜찮은 문장', transcription_quality: 'good' }),
    ]
    render(<SegmentList {...makeProps({ segments })} />)

    await user.click(screen.getByRole('button', { name: /검토 필요 \(1\)/ }))

    expect(screen.getByText('문제 있는 문장')).toBeInTheDocument()
    expect(screen.queryByText('괜찮은 문장')).not.toBeInTheDocument()
  })

  it('shows a filter-specific empty hint when no segment matches the active filter', async () => {
    const user = userEvent.setup()
    const segments = [makeSegment({ id: 'a', reviewed: false })]
    render(<SegmentList {...makeProps({ segments })} />)

    await user.click(screen.getByRole('button', { name: /완료 \(0\)/ }))

    expect(screen.getByText('이 필터에 해당하는 문장이 없습니다.')).toBeInTheDocument()
  })

  it('calls onSelect with the segment id when a row is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const segments = [makeSegment({ id: 'seg-42', text: '클릭할 문장' })]
    render(<SegmentList {...makeProps({ segments, onSelect })} />)

    await user.click(screen.getByText('클릭할 문장'))

    expect(onSelect).toHaveBeenCalledWith('seg-42')
  })

  it('reveals bulk-action buttons only once at least one segment is checked', async () => {
    const segments = [makeSegment({ id: 'a' }), makeSegment({ id: 'b' })]
    render(<SegmentList {...makeProps({ segments })} />)

    expect(screen.queryByText(/개 선택됨/)).not.toBeInTheDocument()

    // index 0 is the "select all filtered" checkbox; row checkboxes start at 1
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[1])

    expect(screen.getByText('1개 선택됨')).toBeInTheDocument()
  })

  it('disables the merge button until 2 or more segments are checked', () => {
    const segments = [makeSegment({ id: 'a' }), makeSegment({ id: 'b' })]
    render(<SegmentList {...makeProps({ segments })} />)

    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[1])

    const mergeButton = screen.getByRole('button', { name: '병합' })
    expect(mergeButton).toBeDisabled()

    fireEvent.click(checkboxes[2])
    expect(mergeButton).not.toBeDisabled()
  })

  it('calls onBulkDelete with the checked segment ids after confirming', async () => {
    const user = userEvent.setup()
    const onBulkDelete = vi.fn().mockResolvedValue(undefined)
    const segments = [makeSegment({ id: 'a' }), makeSegment({ id: 'b' })]
    render(<SegmentList {...makeProps({ segments, onBulkDelete })} />)

    fireEvent.click(screen.getAllByRole('checkbox')[1])
    await user.click(screen.getByRole('button', { name: '삭제' }))

    expect(onBulkDelete).toHaveBeenCalledWith(['a'])
  })

  it('selects all filtered segments when "select all" is checked, and can deselect them', async () => {
    const user = userEvent.setup()
    const segments = [makeSegment({ id: 'a' }), makeSegment({ id: 'b' })]
    render(<SegmentList {...makeProps({ segments })} />)

    const selectAll = screen.getByRole('checkbox', { name: /전체 선택/ })
    await user.click(selectAll)

    expect(screen.getByText('2개 선택됨')).toBeInTheDocument()

    await user.click(selectAll)
    expect(screen.queryByText(/개 선택됨/)).not.toBeInTheDocument()
  })

  it('runs a find/replace call with the entered text', async () => {
    const user = userEvent.setup()
    const onFindReplace = vi.fn().mockResolvedValue(undefined)
    const segments = [makeSegment({ id: 'a', text: 'foo bar' })]
    render(<SegmentList {...makeProps({ segments, onFindReplace })} />)

    const [findInput, replaceInput] = screen.getAllByPlaceholderText(/찾기|바꾸기/)
    await user.type(findInput, 'foo')
    await user.type(replaceInput, 'baz')
    await user.click(screen.getByRole('button', { name: '모두 바꾸기' }))

    expect(onFindReplace).toHaveBeenCalledWith('text', 'foo', 'baz')
  })

  it('paginates segments in pages of 20', async () => {
    const user = userEvent.setup()
    const segments = Array.from({ length: 25 }, (_, i) =>
      makeSegment({ id: `seg-${i}`, text: `문장 ${i}` }),
    )
    render(<SegmentList {...makeProps({ segments })} />)

    expect(screen.getByText('문장 0')).toBeInTheDocument()
    expect(screen.queryByText('문장 20')).not.toBeInTheDocument()

    const pager = screen.getByText('1 / 2').closest('div') as HTMLElement
    await user.click(within(pager).getByText('▶'))

    expect(screen.getByText('문장 20')).toBeInTheDocument()
    expect(screen.queryByText('문장 0')).not.toBeInTheDocument()
  })
})
