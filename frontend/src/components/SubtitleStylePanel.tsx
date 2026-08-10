import { useEffect, useRef, useState } from 'react'
import type { Project, SubtitleStyle } from '../api/types'
import { deleteStylePreset, saveStylePreset, updateSubtitleStyle } from '../api/client'

type Props = {
  project: Project
  onStyleUpdated: (project: Project) => void
}

const FONT_OPTIONS = ['Pretendard', 'Noto Sans KR', 'Malgun Gothic', 'Arial', 'Georgia']
const STYLE_UPDATE_DEBOUNCE_MS = 250

export function SubtitleStylePanel({ project, onStyleUpdated }: Props) {
  const [draftStyle, setDraftStyle] = useState<SubtitleStyle>(project.subtitle_style)
  const [presetName, setPresetName] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const debounceTimer = useRef<number | null>(null)
  // Bumped on every send so an out-of-order response (e.g. an earlier PUT
  // that resolves after a later one, from rapid slider/number-input edits)
  // never overwrites the project with stale style data.
  const requestSeq = useRef(0)

  // Sync from the parent's project state, but only while there's no pending
  // debounced edit - otherwise a poll/refresh mid-type would revert what the
  // user just typed before the debounce has a chance to send it.
  useEffect(() => {
    if (debounceTimer.current === null) {
      setDraftStyle(project.subtitle_style)
    }
  }, [project.subtitle_style])

  useEffect(() => {
    return () => {
      if (debounceTimer.current !== null) window.clearTimeout(debounceTimer.current)
    }
  }, [])

  async function sendStyleUpdate(nextStyle: SubtitleStyle) {
    const seq = ++requestSeq.current
    setIsSaving(true)
    try {
      const updated = await updateSubtitleStyle(project.id, nextStyle)
      if (seq === requestSeq.current) {
        onStyleUpdated(updated)
      }
    } finally {
      if (seq === requestSeq.current) setIsSaving(false)
    }
  }

  function applyStyle(update: Partial<SubtitleStyle>) {
    const nextStyle = { ...draftStyle, ...update }
    setDraftStyle(nextStyle)
    if (debounceTimer.current !== null) window.clearTimeout(debounceTimer.current)
    debounceTimer.current = window.setTimeout(() => {
      debounceTimer.current = null
      void sendStyleUpdate(nextStyle)
    }, STYLE_UPDATE_DEBOUNCE_MS)
  }

  const style = draftStyle

  async function handleSavePreset() {
    const name = presetName.trim()
    if (!name) return
    setIsSaving(true)
    try {
      const updated = await saveStylePreset(project.id, name, style)
      onStyleUpdated(updated)
      setPresetName('')
    } finally {
      setIsSaving(false)
    }
  }

  async function handleApplyPreset(name: string) {
    const preset = project.style_presets.find((p) => p.name === name)
    if (!preset) return
    setDraftStyle(preset.style)
    await sendStyleUpdate(preset.style)
  }

  async function handleDeletePreset(name: string) {
    setIsSaving(true)
    try {
      const updated = await deleteStylePreset(project.id, name)
      onStyleUpdated(updated)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <section className="panel subtitle-style-panel">
      <h2>자막 스타일</h2>

      <div className="panel-row">
        <div className="panel-field">
          <label htmlFor="style-font">폰트</label>
          <select
            id="style-font"
            value={style.font_family}
            onChange={(event) => applyStyle({ font_family: event.target.value })}
          >
            {FONT_OPTIONS.map((font) => (
              <option key={font} value={font}>
                {font}
              </option>
            ))}
          </select>
        </div>

        <div className="panel-field">
          <label htmlFor="style-size">크기</label>
          <input
            id="style-size"
            type="number"
            min={12}
            max={96}
            value={style.font_size}
            onChange={(event) => applyStyle({ font_size: Number(event.target.value) })}
          />
        </div>

        <label
          className="checkbox-label panel-field"
          data-tip="굵게/보통 글꼴 두께를 전환합니다."
        >
          <input
            type="checkbox"
            checked={style.font_weight === 'bold'}
            onChange={(event) =>
              applyStyle({ font_weight: event.target.checked ? 'bold' : 'normal' })
            }
          />
          굵게
        </label>
      </div>

      <div className="panel-row">
        <div className="panel-field">
          <label htmlFor="style-color">글자색</label>
          <input
            id="style-color"
            type="color"
            value={style.color}
            onChange={(event) => applyStyle({ color: event.target.value })}
          />
        </div>

        <div className="panel-field">
          <label htmlFor="style-outline-color">외곽선색</label>
          <input
            id="style-outline-color"
            type="color"
            value={style.outline_color}
            onChange={(event) => applyStyle({ outline_color: event.target.value })}
          />
        </div>

        <div className="panel-field">
          <label htmlFor="style-outline-width">외곽선 두께</label>
          <input
            id="style-outline-width"
            type="number"
            min={0}
            max={10}
            value={style.outline_width}
            onChange={(event) => applyStyle({ outline_width: Number(event.target.value) })}
          />
        </div>
      </div>

      <div className="panel-row">
        <div className="panel-field">
          <label htmlFor="style-background">배경색</label>
          <input
            id="style-background"
            type="color"
            value={style.background ?? '#000000'}
            onChange={(event) => applyStyle({ background: event.target.value })}
          />
        </div>
        <label
          className="checkbox-label panel-field"
          data-tip="배경색을 사용하지 않고 외곽선만으로 가독성을 확보합니다."
        >
          <input
            type="checkbox"
            checked={style.background === null}
            onChange={(event) => applyStyle({ background: event.target.checked ? null : '#000000' })}
          />
          배경 없음
        </label>

        <div className="panel-field">
          <label htmlFor="style-position">위치</label>
          <select
            id="style-position"
            value={style.position}
            onChange={(event) =>
              applyStyle({ position: event.target.value as SubtitleStyle['position'] })
            }
          >
            <option value="bottom">하단</option>
            <option value="top">상단</option>
            <option value="custom">사용자 지정</option>
          </select>
        </div>
      </div>

      <div className="panel-row">
        <div className="panel-field">
          <label htmlFor="style-fade-in" data-tip="문장이 나타날 때 밀리초 단위로 서서히 나타납니다.">
            페이드 인(ms)
          </label>
          <input
            id="style-fade-in"
            type="number"
            min={0}
            max={2000}
            step={50}
            value={style.fade_in_ms}
            onChange={(event) => applyStyle({ fade_in_ms: Number(event.target.value) })}
          />
        </div>

        <div className="panel-field">
          <label htmlFor="style-fade-out" data-tip="문장이 사라질 때 밀리초 단위로 서서히 사라집니다.">
            페이드 아웃(ms)
          </label>
          <input
            id="style-fade-out"
            type="number"
            min={0}
            max={2000}
            step={50}
            value={style.fade_out_ms}
            onChange={(event) => applyStyle({ fade_out_ms: Number(event.target.value) })}
          />
        </div>

        <label
          className="checkbox-label panel-field"
          data-tip="단어 타임스탬프를 이용해 재생 중인 단어를 강조 표시합니다 (노래방 자막 스타일)."
        >
          <input
            type="checkbox"
            checked={style.karaoke_highlight}
            onChange={(event) => applyStyle({ karaoke_highlight: event.target.checked })}
          />
          단어 하이라이트
        </label>
      </div>

      <div className="panel-row">
        <label
          className="checkbox-label panel-field"
          data-tip="긴 문장은 마침표 기준으로, 한 문장이 너무 길면 단어 기준으로 자동 줄바꿈합니다."
        >
          <input
            type="checkbox"
            checked={style.auto_line_break}
            onChange={(event) => applyStyle({ auto_line_break: event.target.checked })}
          />
          자동 줄바꿈
        </label>

        <div className="panel-field">
          <label htmlFor="style-max-line-chars">줄당 최대 글자수</label>
          <input
            id="style-max-line-chars"
            type="number"
            min={6}
            max={60}
            value={style.max_line_chars}
            disabled={!style.auto_line_break}
            onChange={(event) => applyStyle({ max_line_chars: Number(event.target.value) })}
          />
        </div>

        <button
          type="button"
          onClick={() => applyStyle({ auto_line_break: true, max_line_chars: 14 })}
          data-tip="세로(9:16, 쇼츠) 화면에 맞춘 짧은 줄바꿈 기준을 적용합니다."
        >
          9:16 짧게
        </button>
        <button
          type="button"
          onClick={() => applyStyle({ auto_line_break: true, max_line_chars: 24 })}
          data-tip="가로(16:9, 유튜브) 화면에 맞춘 넉넉한 줄바꿈 기준을 적용합니다."
        >
          16:9 길게
        </button>
      </div>

      <div className="panel-row subtitle-style-presets">
        <label htmlFor="style-preset-name">프리셋</label>
        <input
          id="style-preset-name"
          type="text"
          placeholder="프리셋 이름"
          value={presetName}
          onChange={(event) => setPresetName(event.target.value)}
        />
        <button type="button" onClick={handleSavePreset} disabled={isSaving || !presetName.trim()}>
          현재 스타일 저장
        </button>

        {project.style_presets.map((preset) => (
          <span key={preset.name} className="subtitle-style-preset-chip">
            <button type="button" onClick={() => handleApplyPreset(preset.name)} disabled={isSaving}>
              {preset.name}
            </button>
            <button
              type="button"
              className="subtitle-style-preset-delete"
              onClick={() => handleDeletePreset(preset.name)}
              disabled={isSaving}
              data-tip="이 프리셋을 삭제합니다."
            >
              ×
            </button>
          </span>
        ))}
      </div>
    </section>
  )
}
