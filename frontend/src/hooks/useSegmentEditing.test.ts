import { act, renderHook } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem, Project, Segment } from '../api/types'
import { useSegmentEditing } from './useSegmentEditing'

const { deleteSegment, findReplaceSegments, mergeSegments, splitSegment, undoItem, redoItem, updateSegment } =
  vi.hoisted(() => ({
    deleteSegment: vi.fn(),
    findReplaceSegments: vi.fn(),
    mergeSegments: vi.fn(),
    splitSegment: vi.fn(),
    undoItem: vi.fn(),
    redoItem: vi.fn(),
    updateSegment: vi.fn(),
  }))

vi.mock('../api/client', () => ({
  deleteSegment,
  findReplaceSegments,
  mergeSegments,
  splitSegment,
  undoItem,
  redoItem,
  updateSegment,
}))

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

function makeItem(segments: Segment[]): MediaItem {
  return {
    id: 'item-1',
    filename: 'video.mp4',
    media_path: '/tmp/video.mp4',
    status: 'transcribed',
    whisper_model: 'small',
    error: null,
    progress: null,
    stage: null,
    started_at: null,
    segments,
    rendered_path: null,
  }
}

function makeProject(item: MediaItem): Project {
  return {
    id: 'proj-1',
    name: 'test project',
    items: [item],
    glossary: {},
    subtitle_style: {
      font_family: 'Pretendard',
      font_size: 12,
      font_weight: 'bold',
      color: '#fff',
      outline_color: '#000',
      outline_width: 2,
      background: null,
      position: 'bottom',
      fade_in_ms: 0,
      fade_out_ms: 0,
      karaoke_highlight: false,
      auto_line_break: true,
      max_line_chars: 18,
    },
    style_presets: [],
  }
}

// Wraps the hook with the (project, setProject, selectedSegmentId, setSelectedSegmentId)
// state it expects from its App.tsx caller, so tests can drive it like the real app does.
function useHarness(initialProject: Project, initialSegmentId: string | null) {
  const [project, setProject] = useState<Project | null>(initialProject)
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(initialSegmentId)
  const editing = useSegmentEditing(project, setProject, 'item-1', selectedSegmentId, setSelectedSegmentId)
  return { project, selectedSegmentId, ...editing }
}

describe('useSegmentEditing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('starts with undo/redo both disabled', () => {
    const item = makeItem([makeSegment()])
    const project = makeProject(item)
    const { result } = renderHook(() => useHarness(project, 'seg-1'))
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(false)
  })

  it('handleSegmentSaved updates the segment in place and enables undo', () => {
    const item = makeItem([makeSegment({ id: 'seg-1', text: 'old text' })])
    const project = makeProject(item)
    const { result } = renderHook(() => useHarness(project, 'seg-1'))

    act(() => {
      result.current.handleSegmentSaved(makeSegment({ id: 'seg-1', text: 'new text' }))
    })

    expect(result.current.project?.items[0].segments[0].text).toBe('new text')
    expect(result.current.canUndo).toBe(true)
    expect(result.current.canRedo).toBe(false)
  })

  it('handleSegmentDeleted removes the segment and falls back the selection', () => {
    const item = makeItem([makeSegment({ id: 'a' }), makeSegment({ id: 'b' })])
    const project = makeProject(item)
    const { result } = renderHook(() => useHarness(project, 'b'))

    act(() => {
      result.current.handleSegmentDeleted('b')
    })

    expect(result.current.project?.items[0].segments.map((s) => s.id)).toEqual(['a'])
    expect(result.current.selectedSegmentId).toBe('a')
  })

  it('handleBulkDelete calls the API for every id and removes them from state', async () => {
    deleteSegment.mockResolvedValue(undefined)
    const item = makeItem([makeSegment({ id: 'a' }), makeSegment({ id: 'b' }), makeSegment({ id: 'c' })])
    const project = makeProject(item)
    const { result } = renderHook(() => useHarness(project, null))

    await act(async () => {
      await result.current.handleBulkDelete(['a', 'c'])
    })

    expect(deleteSegment).toHaveBeenCalledWith('proj-1', 'item-1', 'a')
    expect(deleteSegment).toHaveBeenCalledWith('proj-1', 'item-1', 'c')
    expect(result.current.project?.items[0].segments.map((s) => s.id)).toEqual(['b'])
  })

  it('handleUndo applies the returned segments and updated undo/redo flags', async () => {
    const item = makeItem([makeSegment({ id: 'seg-1', text: 'edited' })])
    const project = makeProject(item)
    undoItem.mockResolvedValue({
      segments: [makeSegment({ id: 'seg-1', text: 'original' })],
      can_undo: false,
      can_redo: true,
    })

    const { result } = renderHook(() => useHarness(project, 'seg-1'))

    // Prime canUndo=true via a save, since handleUndo no-ops while canUndo is false.
    act(() => {
      result.current.handleSegmentSaved(makeSegment({ id: 'seg-1', text: 'edited' }))
    })
    expect(result.current.canUndo).toBe(true)

    await act(async () => {
      await result.current.handleUndo()
    })

    expect(undoItem).toHaveBeenCalledWith('proj-1', 'item-1')
    expect(result.current.project?.items[0].segments[0].text).toBe('original')
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(true)
  })

  it('handleUndo is a no-op when canUndo is false', async () => {
    const item = makeItem([makeSegment()])
    const project = makeProject(item)
    const { result } = renderHook(() => useHarness(project, 'seg-1'))

    await act(async () => {
      await result.current.handleUndo()
    })

    expect(undoItem).not.toHaveBeenCalled()
  })
})
