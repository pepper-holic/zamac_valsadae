import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem, Project, ProjectStatusSummary } from '../api/types'
import { useProjectWorkspace } from './useProjectWorkspace'

const { addItem, createProject, deleteItem, getProject, getProjectStatus, listProjects } = vi.hoisted(() => ({
  addItem: vi.fn(),
  createProject: vi.fn(),
  deleteItem: vi.fn(),
  getProject: vi.fn(),
  getProjectStatus: vi.fn(),
  listProjects: vi.fn(),
}))

vi.mock('../api/client', () => ({
  addItem,
  createProject,
  deleteItem,
  getProject,
  getProjectStatus,
  listProjects,
}))

function makeItem(overrides: Partial<MediaItem> = {}): MediaItem {
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
    segments: [],
    rendered_path: null,
    ...overrides,
  }
}

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'proj-1',
    name: 'test project',
    items: [],
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
    ...overrides,
  }
}

describe('useProjectWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listProjects.mockResolvedValue([])
  })

  it('loads the project list on mount', async () => {
    const projects = [makeProject({ id: 'a' }), makeProject({ id: 'b' })]
    listProjects.mockResolvedValue(projects)
    const onProjectLoaded = vi.fn()

    const { result } = renderHook(() => useProjectWorkspace(onProjectLoaded))

    await waitFor(() => expect(result.current.projects).toHaveLength(2))
  })

  it('fetches the project and selects its first item when selectedProjectId changes', async () => {
    const item = makeItem({ id: 'item-1' })
    const project = makeProject({ id: 'proj-1', items: [item] })
    getProject.mockResolvedValue(project)
    const onProjectLoaded = vi.fn()

    const { result } = renderHook(() => useProjectWorkspace(onProjectLoaded))

    act(() => {
      result.current.setSelectedProjectId('proj-1')
    })

    await waitFor(() => expect(result.current.project?.id).toBe('proj-1'))
    expect(result.current.selectedItemId).toBe('item-1')
    expect(onProjectLoaded).toHaveBeenCalledTimes(1)
  })

  it('clears the project when selectedProjectId is set back to null', async () => {
    const project = makeProject({ id: 'proj-1', items: [makeItem()] })
    getProject.mockResolvedValue(project)
    const { result } = renderHook(() => useProjectWorkspace(vi.fn()))

    act(() => {
      result.current.setSelectedProjectId('proj-1')
    })
    await waitFor(() => expect(result.current.project?.id).toBe('proj-1'))

    act(() => {
      result.current.setSelectedProjectId(null)
    })

    expect(result.current.project).toBeNull()
    expect(result.current.selectedItemId).toBeNull()
  })

  it('handleCreateProject adds the new project and selects it', async () => {
    const created = makeProject({ id: 'new-proj' })
    createProject.mockResolvedValue(created)
    getProject.mockResolvedValue(created)
    const { result } = renderHook(() => useProjectWorkspace(vi.fn()))

    await act(async () => {
      await result.current.handleCreateProject('새 프로젝트')
    })

    expect(createProject).toHaveBeenCalledWith('새 프로젝트')
    expect(result.current.projects.map((p) => p.id)).toContain('new-proj')
    expect(result.current.selectedProjectId).toBe('new-proj')
  })

  it('handleProjectDeleted removes the project and clears selection if it was selected', async () => {
    const project = makeProject({ id: 'proj-1', items: [makeItem()] })
    getProject.mockResolvedValue(project)
    listProjects.mockResolvedValue([project])
    const { result } = renderHook(() => useProjectWorkspace(vi.fn()))

    await waitFor(() => expect(result.current.projects).toHaveLength(1))
    act(() => {
      result.current.setSelectedProjectId('proj-1')
    })
    await waitFor(() => expect(result.current.project?.id).toBe('proj-1'))

    act(() => {
      result.current.handleProjectDeleted('proj-1')
    })

    expect(result.current.projects).toHaveLength(0)
    expect(result.current.selectedProjectId).toBeNull()
  })

  it('handleItemDeleted removes the item and falls back the selected item', async () => {
    const itemA = makeItem({ id: 'a' })
    const itemB = makeItem({ id: 'b' })
    const project = makeProject({ id: 'proj-1', items: [itemA, itemB] })
    getProject.mockResolvedValue(project)
    deleteItem.mockResolvedValue(undefined)
    const { result } = renderHook(() => useProjectWorkspace(vi.fn()))

    act(() => {
      result.current.setSelectedProjectId('proj-1')
    })
    await waitFor(() => expect(result.current.selectedItemId).toBe('a'))

    await act(async () => {
      await result.current.handleItemDeleted('a')
    })

    expect(result.current.project?.items.map((i) => i.id)).toEqual(['b'])
    expect(result.current.selectedItemId).toBe('b')
  })

  function statusOf(item: MediaItem): ProjectStatusSummary['items'][number] {
    return {
      id: item.id,
      status: item.status,
      error: item.error,
      progress: item.progress,
      stage: item.stage,
      started_at: item.started_at,
    }
  }

  it('polls the lightweight status endpoint while a task is active, without a full refetch', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const item = makeItem({ id: 'item-1', status: 'transcribing', progress: 0.1 })
      const project = makeProject({ id: 'proj-1', items: [item] })
      getProject.mockResolvedValue(project)
      listProjects.mockResolvedValue([project])
      getProjectStatus.mockResolvedValue({
        id: 'proj-1',
        items: [{ ...statusOf(item), progress: 0.5 }],
      } satisfies ProjectStatusSummary)

      const { result } = renderHook(() => useProjectWorkspace(vi.fn()))
      await waitFor(() => expect(result.current.projects).toHaveLength(1))
      act(() => {
        result.current.setSelectedProjectId('proj-1')
      })
      await waitFor(() => expect(result.current.project?.id).toBe('proj-1'))
      getProject.mockClear()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })

      expect(getProjectStatus).toHaveBeenCalledWith('proj-1')
      expect(result.current.project?.items[0].progress).toBe(0.5)
      // still "transcribing" - no need to re-fetch the full project/segments
      expect(getProject).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('does one full refetch once an active item leaves an active status', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const item = makeItem({ id: 'item-1', status: 'transcribing', progress: 0.9 })
      const project = makeProject({ id: 'proj-1', items: [item] })
      const finished = makeProject({
        id: 'proj-1',
        items: [{ ...item, status: 'transcribed', progress: 1.0, segments: [] }],
      })
      getProject.mockResolvedValue(project)
      listProjects.mockResolvedValue([project])
      getProjectStatus.mockResolvedValue({
        id: 'proj-1',
        items: [{ ...statusOf(item), status: 'transcribed', progress: 1.0 }],
      } satisfies ProjectStatusSummary)

      const { result } = renderHook(() => useProjectWorkspace(vi.fn()))
      await waitFor(() => expect(result.current.projects).toHaveLength(1))
      act(() => {
        result.current.setSelectedProjectId('proj-1')
      })
      await waitFor(() => expect(result.current.project?.id).toBe('proj-1'))
      getProject.mockClear()
      getProject.mockResolvedValue(finished)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })

      expect(getProject).toHaveBeenCalledWith('proj-1')
      await waitFor(() => expect(result.current.project?.items[0].status).toBe('transcribed'))
    } finally {
      vi.useRealTimers()
    }
  })
})
