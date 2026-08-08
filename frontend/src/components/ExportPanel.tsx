import { useState } from 'react'
import type { ExportFormat, MediaItem, Project } from '../api/types'
import { cancelItem, exportUrl, renderItem, renderedVideoUrl } from '../api/client'

type Props = {
  project: Project
  item: MediaItem
  onItemUpdated: (item: MediaItem) => void
}

const RENDERABLE_STATUSES = new Set(['transcribed', 'translated', 'rendered', 'error'])

export function ExportPanel({ project, item, onItemUpdated }: Props) {
  const [format, setFormat] = useState<ExportFormat>('srt')
  const [useTranslation, setUseTranslation] = useState(false)
  const [renderUseTranslation, setRenderUseTranslation] = useState(false)
  const [isStartingRender, setIsStartingRender] = useState(false)
  const [isCancellingRender, setIsCancellingRender] = useState(false)

  const hasSegments = item.segments.length > 0
  const hasTranslations = item.segments.some((segment) => segment.translation)
  const isRendering = item.status === 'rendering'
  const canStartRender = hasSegments && RENDERABLE_STATUSES.has(item.status) && !isStartingRender

  async function handleRender() {
    setIsStartingRender(true)
    try {
      const updated = await renderItem(project.id, item.id, renderUseTranslation)
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
      <h2>4. 내보내기</h2>
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
        {format !== 'json' && (
          <label
            className="checkbox-label"
            data-tip="켜면 번역문을, 끄면 원문을 자막으로 내보냅니다."
          >
            <input
              type="checkbox"
              checked={useTranslation}
              disabled={!hasTranslations}
              onChange={(event) => setUseTranslation(event.target.checked)}
            />
            번역문 사용
          </label>
        )}
        {hasSegments ? (
          <a
            className="download-button"
            href={exportUrl(project.id, item.id, format, useTranslation)}
            download
            data-tip="선택한 형식으로 파일을 내려받습니다."
          >
            다운로드
          </a>
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
            {Math.round((item.progress ?? 0) * 100)}% 렌더링 중 — 영상 길이에 비례해 몇 분~십몇
            분이 걸릴 수 있습니다.
          </p>
        </div>
      )}
      {item.status === 'error' && item.error && <p className="error-text">{item.error}</p>}
    </section>
  )
}
