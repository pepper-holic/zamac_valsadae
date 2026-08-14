import { useState } from 'react'
import type { ExportFormat, ExportTextMode, MediaItem, Project } from '../api/types'
import { cancelItem, exportUrl, renderItem, renderedVideoUrl } from '../api/client'
import { PanelHint } from './PanelHint'
import { formatClock } from '../utils/time'
import { useElapsedSeconds } from '../utils/useElapsedSeconds'

type Props = {
  project: Project
  item: MediaItem
  onItemUpdated: (item: MediaItem) => void
}

const RENDERABLE_STATUSES = new Set(['transcribed', 'translated', 'rendered', 'error'])

const TEXT_MODE_LABELS: Record<ExportTextMode, string> = {
  original: '원문',
  translation: '번역문',
  combined: '합쳐진 자막',
}

function triggerDownload(url: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export function ExportPanel({ project, item, onItemUpdated }: Props) {
  const [format, setFormat] = useState<ExportFormat>('srt')
  const [selectedModes, setSelectedModes] = useState<Set<ExportTextMode>>(new Set(['original']))
  const [renderUseTranslation, setRenderUseTranslation] = useState(false)
  const [cutDeleted, setCutDeleted] = useState(false)
  const [isStartingRender, setIsStartingRender] = useState(false)
  const [isCancellingRender, setIsCancellingRender] = useState(false)

  const hasSegments = item.segments.length > 0
  const hasTranslations = item.segments.some((segment) => segment.translation)
  const isRendering = item.status === 'rendering'
  const canStartRender = hasSegments && RENDERABLE_STATUSES.has(item.status) && !isStartingRender
  const elapsedSeconds = useElapsedSeconds(isRendering ? item.started_at : null)

  function toggleMode(mode: ExportTextMode) {
    setSelectedModes((prev) => {
      const next = new Set(prev)
      if (next.has(mode)) {
        next.delete(mode)
      } else {
        next.add(mode)
      }
      return next
    })
  }

  function handleBulkDownload() {
    for (const mode of selectedModes) {
      triggerDownload(exportUrl(project.id, item.id, format, mode))
    }
  }

  async function handleRender() {
    setIsStartingRender(true)
    try {
      const updated = await renderItem(project.id, item.id, renderUseTranslation, cutDeleted)
      onItemUpdated(updated)
    } finally {
      setIsStartingRender(false)
    }
  }

  async function handleCancelRender() {
    setIsCancellingRender(true)
    try {
      const updated = await cancelItem(project.id, item.id)
      onItemUpdated(updated)
    } finally {
      setIsCancellingRender(false)
    }
  }

  return (
    <section className="panel">
      <h2>
        4. 내보내기
        <PanelHint tip="완성된 자막을 SRT/VTT/JSON 파일로 내려받거나, 자막이 구워진 영상으로 렌더링합니다." />
      </h2>
      <div className="panel-row">
        <label htmlFor="export-format">형식</label>
        <select
          id="export-format"
          value={format}
          onChange={(event) => setFormat(event.target.value as ExportFormat)}
          data-tip="SRT/VTT/ASS는 일반 자막 파일, TTML은 방송/OTT 납품용 표준 포맷, JSON은 시간/원문/번역이 모두 담긴 원본 데이터입니다."
        >
          <option value="srt">SRT</option>
          <option value="vtt">VTT</option>
          <option value="json">JSON</option>
          <option value="ass">ASS</option>
          <option value="ttml">TTML</option>
        </select>
        {format !== 'json' && hasSegments && (
          <>
            {(Object.keys(TEXT_MODE_LABELS) as ExportTextMode[]).map((mode) => (
              <label
                key={mode}
                className="checkbox-label"
                data-tip="체크한 항목을 각각 파일로 한 번에 내려받습니다."
              >
                <input
                  type="checkbox"
                  checked={selectedModes.has(mode)}
                  disabled={mode !== 'original' && !hasTranslations}
                  onChange={() => toggleMode(mode)}
                />
                {TEXT_MODE_LABELS[mode]}
              </label>
            ))}
          </>
        )}
        {hasSegments ? (
          format === 'json' ? (
            <a
              className="download-button"
              href={exportUrl(project.id, item.id, format)}
              download
              data-tip="선택한 형식으로 파일을 내려받습니다."
            >
              다운로드
            </a>
          ) : (
            <button
              type="button"
              className="download-button"
              onClick={handleBulkDownload}
              disabled={selectedModes.size === 0}
              data-tip="체크한 항목을 각각 파일로 한 번에 내려받습니다."
            >
              선택 항목 다운로드
            </button>
          )
        ) : (
          <span className="hint-text">전사 완료 후 이용 가능</span>
        )}
      </div>

      <div className="panel-row">
        <label
          className="checkbox-label"
          data-tip="켜면 번역문을, 끄면 원문을 영상에 구워 넣습니다. 자막 스타일 메뉴에서 설정한 스타일이 그대로 적용됩니다."
        >
          <input
            type="checkbox"
            checked={renderUseTranslation}
            disabled={!hasTranslations}
            onChange={(event) => setRenderUseTranslation(event.target.checked)}
          />
          번역문 사용
        </label>
        <label
          className="checkbox-label"
          data-tip="켜면 문장 목록에 남아있지 않은 구간(삭제한 문장뿐 아니라 문장 사이의 무음 구간 포함)을 최종 영상에서 함께 잘라냅니다. 끄면 자막만 빠지고 영상은 원본 길이 그대로 유지됩니다."
        >
          <input
            type="checkbox"
            checked={cutDeleted}
            onChange={(event) => setCutDeleted(event.target.checked)}
          />
          삭제된 구간도 영상에서 잘라내기
        </label>
        <button
          type="button"
          onClick={handleRender}
          disabled={!canStartRender}
          data-tip="자막을 영상에 직접 구워 넣어(번인) 완성된 영상 파일로 내보냅니다. 영상 길이에 비례해 몇 분~십몇 분이 걸릴 수 있습니다."
        >
          {isRendering
            ? `렌더링 중... ${item.progress != null ? Math.round(item.progress * 100) : 0}%`
            : '영상으로 내보내기 (자막 포함)'}
        </button>
        {isRendering && (
          <button
            type="button"
            onClick={handleCancelRender}
            disabled={isCancellingRender}
            data-tip="진행 중인 렌더링을 중단합니다."
          >
            취소
          </button>
        )}
        {item.status === 'rendered' && item.rendered_path && (
          <a
            className="download-button"
            href={renderedVideoUrl(project.id, item.id)}
            download
            data-tip="번인된 영상 파일을 내려받습니다."
          >
            렌더링된 영상 다운로드
          </a>
        )}
      </div>
      {isRendering && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((item.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            {Math.round((item.progress ?? 0) * 100)}% 렌더링 중 (경과{' '}
            {elapsedSeconds != null ? formatClock(elapsedSeconds) : '0:00'}) — 영상 길이에 비례해 몇
            분~십몇 분이 걸릴 수 있습니다.
          </p>
        </div>
      )}
      {item.status === 'error' && item.error && <p className="error-text">{item.error}</p>}
    </section>
  )
}
