import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem, Project } from '../api/types'
import { useProjectWorkspace } from './useProjectWorkspace'

const { addItem, createProject, deleteItem, getProject, listProjects } = vi.hoisted(() => ({
  addItem: vi.fn(),
  createProject: vi.fn(),
  deleteItem: vi.fn(),
  getProject: vi.fn(),
  listProjects: vi.fn(),
}))

vi.mock('../api/client', () => ({
  addItem,
  createProject,
  deleteItem,
  getProject,
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
})
