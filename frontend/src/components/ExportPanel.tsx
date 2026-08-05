import { useState } from 'react'
import type { ExportFormat, Project } from '../api/types'
import { exportUrl } from '../api/client'

type Props = {
  project: Project
}

export function ExportPanel({ project }: Props) {
  const [format, setFormat] = useState<ExportFormat>('srt')
  const [useTranslation, setUseTranslation] = useState(false)

  const hasSegments = project.segments.length > 0
  const hasTranslations = project.segments.some((segment) => segment.translation)

  return (
    <section className="panel">
      <h2>4. 내보내기</h2>
      <div className="panel-row">
        <label htmlFor="export-format">형식</label>
        <select
          id="export-format"
          value={format}
          onChange={(event) => setFormat(event.target.value as ExportFormat)}
          data-tip="SRT/VTT는 자막 파일, JSON은 시간/원문/번역이 모두 담긴 원본 데이터입니다."
        >
          <option value="srt">SRT</option>
          <option value="vtt">VTT</option>
          <option value="json">JSON</option>
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
            href={exportUrl(project.id, format, useTranslation)}
            download
            data-tip="선택한 형식으로 파일을 내려받습니다."
          >
            다운로드
          </a>
        ) : (
          <span className="hint-text">전사 완료 후 이용 가능</span>
        )}
      </div>
    </section>
  )
}
