import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, SubtitleStyle } from '../api/types'
import { SubtitleStylePanel } from './SubtitleStylePanel'

const { updateSubtitleStyle, saveStylePreset, deleteStylePreset } = vi.hoisted(() => ({
  updateSubtitleStyle: vi.fn(),
  saveStylePreset: vi.fn(),
  deleteStylePreset: vi.fn(),
}))

vi.mock('../api/client', () => ({
  updateSubtitleStyle,
  saveStylePreset,
  deleteStylePreset,
}))

function makeStyle(overrides: Partial<SubtitleStyle> = {}): SubtitleStyle {
  return {
    font_family: 'Pretendard',
    font_size: 32,
    font_weight: 'bold',
    color: '#ffffff',
    outline_color: '#000000',
    outline_width: 2,
    background: null,
    position: 'bottom',
    fade_in_ms: 0,
    fade_out_ms: 0,
    karaoke_highlight: false,
    auto_line_break: true,
    max_line_chars: 18,
    ...overrides,
  }
}

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'proj-1',
    name: 'test project',
    items: [],
    glossary: {},
    subtitle_style: makeStyle(),
    style_presets: [],
    ...overrides,
  }
}

describe('SubtitleStylePanel', () => {
  afterEach(() => {
    updateSubtitleStyle.mockReset()
    saveStylePreset.mockReset()
    deleteStylePreset.mockReset()
  })

  it('debounces style edits into a single update request', async () => {
    const user = userEvent.setup()
    updateSubtitleStyle.mockResolvedValue(makeProject().subtitle_style)
    render(<SubtitleStylePanel project={makeProject()} onStyleUpdated={vi.fn()} />)

    const sizeInput = screen.getByLabelText('크기')
    await user.clear(sizeInput)
    await user.type(sizeInput, '40')

    expect(updateSubtitleStyle).not.toHaveBeenCalled()

    await waitFor(() => expect(updateSubtitleStyle).toHaveBeenCalledTimes(1))
    expect(updateSubtitleStyle).toHaveBeenCalledWith('proj-1', expect.objectContaining({ font_size: 40 }))
  }, 10000)

  it('applying a 9:16 preset sets a short auto line-break length', async () => {
    const user = userEvent.setup()
    updateSubtitleStyle.mockResolvedValue(makeProject().subtitle_style)
    render(<SubtitleStylePanel project={makeProject()} onStyleUpdated={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '9:16 짧게' }))

    await waitFor(() =>
      expect(updateSubtitleStyle).toHaveBeenCalledWith(
        'proj-1',
        expect.objectContaining({ auto_line_break: true, max_line_chars: 14 }),
      ),
    )
  }, 10000)

  it('disables the max-line-chars input when auto line-break is off', () => {
    const project = makeProject({ subtitle_style: makeStyle({ auto_line_break: false }) })
    render(<SubtitleStylePanel project={project} onStyleUpdated={vi.fn()} />)

    expect(screen.getByLabelText('줄당 최대 글자수')).toBeDisabled()
  })

  it('disables "현재 스타일 저장" until a preset name is entered', async () => {
    const user = userEvent.setup()
    render(<SubtitleStylePanel project={makeProject()} onStyleUpdated={vi.fn()} />)

    const saveButton = screen.getByRole('button', { name: '현재 스타일 저장' })
    expect(saveButton).toBeDisabled()

    await user.type(screen.getByPlaceholderText('프리셋 이름'), 'my preset')
    expect(saveButton).toBeEnabled()
  })

  it('saves a new preset and applies the updated project from the server', async () => {
    const user = userEvent.setup()
    const onStyleUpdated = vi.fn()
    const updatedProject = makeProject({
      style_presets: [{ name: 'my preset', style: makeStyle() }],
    })
    saveStylePreset.mockResolvedValue(updatedProject)
    render(<SubtitleStylePanel project={makeProject()} onStyleUpdated={onStyleUpdated} />)

    await user.type(screen.getByPlaceholderText('프리셋 이름'), 'my preset')
    await user.click(screen.getByRole('button', { name: '현재 스타일 저장' }))

    expect(saveStylePreset).toHaveBeenCalledWith('proj-1', 'my preset', expect.any(Object))
    expect(onStyleUpdated).toHaveBeenCalledWith(updatedProject)
  })

  it('lists saved presets and deletes one on click', async () => {
    const user = userEvent.setup()
    const onStyleUpdated = vi.fn()
    const project = makeProject({ style_presets: [{ name: 'shorts', style: makeStyle() }] })
    deleteStylePreset.mockResolvedValue(makeProject({ style_presets: [] }))
    render(<SubtitleStylePanel project={project} onStyleUpdated={onStyleUpdated} />)

    expect(screen.getByRole('button', { name: 'shorts' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '×' }))

    expect(deleteStylePreset).toHaveBeenCalledWith('proj-1', 'shorts')
    expect(onStyleUpdated).toHaveBeenCalled()
  })
})
