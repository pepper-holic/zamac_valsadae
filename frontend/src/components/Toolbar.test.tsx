import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem, Project } from '../api/types'
import { Toolbar } from './Toolbar'

const { deleteProject } = vi.hoisted(() => ({
  deleteProject: vi.fn(),
}))

vi.mock('../api/client', () => ({
  deleteProject,
  cancelItem: vi.fn(),
  exportUrl: vi.fn(),
  renderItem: vi.fn(),
  renderedVideoUrl: vi.fn(),
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
    items: [makeItem()],
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

function makeProps(overrides: Partial<Parameters<typeof Toolbar>[0]> = {}) {
  const project = makeProject()
  return {
    projects: [project],
    project,
    selectedProjectId: project.id,
    onSelectProject: vi.fn(),
    onCreateProject: vi.fn().mockResolvedValue(undefined),
    onFilesUploaded: vi.fn().mockResolvedValue(undefined),
    selectedItemId: project.items[0].id,
    onSelectItem: vi.fn(),
    onItemUpdated: vi.fn(),
    onItemDeleted: vi.fn().mockResolvedValue(undefined),
    onProjectDeleted: vi.fn(),
    canUndo: false,
    canRedo: false,
    onUndo: vi.fn(),
    onRedo: vi.fn(),
    onGoHome: vi.fn(),
    onReviewImported: vi.fn(),
    reviewDiffCount: 0,
    onAcceptAllReviewDiffs: vi.fn().mockResolvedValue(undefined),
    onRejectAllReviewDiffs: vi.fn(),
    onGlossaryUpdated: vi.fn(),
    ...overrides,
  }
}

describe('Toolbar', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    deleteProject.mockClear()
  })

  it('lists every project in the workspace switcher', () => {
    const projects = [makeProject({ id: 'a', name: 'Alpha' }), makeProject({ id: 'b', name: 'Beta' })]
    render(<Toolbar {...makeProps({ projects, project: projects[0], selectedProjectId: 'a' })} />)

    expect(screen.getByRole('option', { name: /Alpha/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Beta/ })).toBeInTheDocument()
  })

  it('calls onSelectProject when a different project is chosen', () => {
    const projects = [makeProject({ id: 'a', name: 'Alpha' }), makeProject({ id: 'b', name: 'Beta' })]
    const onSelectProject = vi.fn()
    render(
      <Toolbar
        {...makeProps({ projects, project: projects[0], selectedProjectId: 'a', onSelectProject })}
      />,
    )

    fireEvent.change(screen.getByDisplayValue(/Alpha/), { target: { value: 'b' } })

    expect(onSelectProject).toHaveBeenCalledWith('b')
  })

  it('prompts for a name and creates a project when confirmed', async () => {
    const user = userEvent.setup()
    const onCreateProject = vi.fn().mockResolvedValue(undefined)
    vi.spyOn(window, 'prompt').mockReturnValue('New Project')
    render(<Toolbar {...makeProps({ onCreateProject })} />)

    await user.click(screen.getByRole('button', { name: /파일/ }))
    await user.click(screen.getByRole('button', { name: '+ 새 프로젝트' }))

    expect(onCreateProject).toHaveBeenCalledWith('New Project')
  })

  it('does not create a project when the prompt is cancelled', async () => {
    const user = userEvent.setup()
    const onCreateProject = vi.fn()
    vi.spyOn(window, 'prompt').mockReturnValue(null)
    render(<Toolbar {...makeProps({ onCreateProject })} />)

    await user.click(screen.getByRole('button', { name: /파일/ }))
    await user.click(screen.getByRole('button', { name: '+ 새 프로젝트' }))

    expect(onCreateProject).not.toHaveBeenCalled()
  })

  it('deletes the current project after the user confirms', async () => {
    const user = userEvent.setup()
    const onProjectDeleted = vi.fn()
    deleteProject.mockResolvedValue(undefined)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<Toolbar {...makeProps({ onProjectDeleted })} />)

    await user.click(screen.getByRole('button', { name: /파일/ }))
    await user.click(screen.getByRole('button', { name: '프로젝트 삭제' }))

    expect(deleteProject).toHaveBeenCalledWith('proj-1')
    expect(onProjectDeleted).toHaveBeenCalledWith('proj-1')
  })

  it('does not delete the project when the confirmation is declined', async () => {
    const user = userEvent.setup()
    const onProjectDeleted = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<Toolbar {...makeProps({ onProjectDeleted })} />)

    await user.click(screen.getByRole('button', { name: /파일/ }))
    await user.click(screen.getByRole('button', { name: '프로젝트 삭제' }))

    expect(deleteProject).not.toHaveBeenCalled()
    expect(onProjectDeleted).not.toHaveBeenCalled()
  })

  it('disables undo/redo buttons based on canUndo/canRedo and calls the handlers when enabled', async () => {
    const user = userEvent.setup()
    const onUndo = vi.fn()
    const onRedo = vi.fn()
    render(<Toolbar {...makeProps({ canUndo: true, canRedo: false, onUndo, onRedo })} />)

    const undoButton = screen.getByRole('button', { name: '되돌리기' })
    const redoButton = screen.getByRole('button', { name: '다시 실행' })
    expect(undoButton).toBeEnabled()
    expect(redoButton).toBeDisabled()

    await user.click(undoButton)
    expect(onUndo).toHaveBeenCalledTimes(1)
  })

  it('uploads files selected through the file input', async () => {
    const onFilesUploaded = vi.fn().mockResolvedValue(undefined)
    render(<Toolbar {...makeProps({ onFilesUploaded })} />)

    const file = new File(['data'], 'clip.mp4', { type: 'video/mp4' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await userEvent.upload(input, file)

    expect(onFilesUploaded).toHaveBeenCalledWith([file])
  })
})
