import { useEffect, useState } from 'react'
import type { MediaItem, Project } from '../api/types'
import { WHISPER_MODELS } from '../api/types'
import { cancelItem, getModelStatus, transcribeItem } from '../api/client'
import { PanelHint } from './PanelHint'
import { formatClock } from '../utils/time'
import { useElapsedSeconds } from '../utils/useElapsedSeconds'

type Props = {
  project: Project
  item: MediaItem
  onStarted: (item: MediaItem) => void
}

const isBusy = (status: MediaItem['status']) =>
  status === 'queued' || status === 'transcribing' || status === 'translating'

const MODEL_NOTES: Record<string, string> = {
  tiny: '매우 빠름 · 정확도 낮음 — 빠른 테스트용',
  base: '빠름 · 정확도 낮음~보통',
  small: '보통 속도 · 정확도 보통~좋음 — 기본 권장',
  medium: '느림 · 정확도 좋음 — 소음/사투리에 강함',
  large: '매우 느림(CPU) · 정확도 최고',
  'large-v2': '매우 느림(CPU) · 정확도 최고',
  'large-v3': '매우 느림(CPU) · 정확도 최고',
  'large-v3-turbo': '빠름(large-v3 대비 약 5배) · 정확도 거의 동일',
}

export function TranscribePanel({ project, item, onStarted }: Props) {
  const [model, setModel] = useState(item.whisper_model ?? 'small')
  const [diarize, setDiarize] = useState(false)
  const [multilingual, setMultilingual] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [whisperCacheStatus, setWhisperCacheStatus] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let cancelled = false
    getModelStatus()
      .then((status) => {
        if (!cancelled) setWhisperCacheStatus(status.whisper)
      })
      .catch(() => {
        // best-effort only - selectors just skip the download badge on failure
      })
    return () => {
      cancelled = true
    }
  }, [])

  const isModelCached = whisperCacheStatus[model]
  const isDownloadingModel = item.status === 'transcribing' && item.stage === 'downloading_model'
  const elapsedSeconds = useElapsedSeconds(item.status === 'transcribing' ? item.started_at : null)

  async function handleTranscribe() {
    setError(null)
    try {
      const updated = await transcribeItem(project.id, item.id, model, diarize, multilingual)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleCancel() {
    setError(null)
    try {
      const updated = await cancelItem(project.id, item.id)
      onStarted(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <section className="panel">
      <h2>
        1. 전사 (Whisper)
        <PanelHint tip="업로드한 영상/오디오에서 Whisper로 음성을 인식해 문장 단위 자막을 만듭니다. 모델이 클수록 정확하지만 느립니다." />
      </h2>
      <div className="panel-row">
        <label htmlFor="model-select">모델 크기</label>
        <select
          id="model-select"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          disabled={isBusy(item.status)}
          data-tip="클수록 정확하지만 GPU 없이는 훨씬 느려집니다. small을 기본으로 추천합니다."
        >
          {WHISPER_MODELS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
        <label
          className="checkbox-label"
          data-tip="누가 말했는지 화자 라벨을 붙입니다. HuggingFace 토큰(HF_TOKEN) 설정과 최초 1회 모델 다운로드가 필요하며, 처리 시간이 더 걸립니다."
        >
          <input
            type="checkbox"
            checked={diarize}
            disabled={isBusy(item.status)}
            onChange={(event) => setDiarize(event.target.checked)}
          />
          화자 분리
        </label>
        <label
          className="checkbox-label"
          data-tip="한 영상 안에서 언어가 섞여 있을 때(예: 한국어↔영어 전환) 약 30초 구간마다 언어를 다시 감지합니다. 기본값은 파일 전체에 대해 언어를 한 번만 감지합니다."
        >
          <input
            type="checkbox"
            checked={multilingual}
            disabled={isBusy(item.status)}
            onChange={(event) => setMultilingual(event.target.checked)}
          />
          다국어 혼합
        </label>
        <button
          type="button"
          onClick={handleTranscribe}
          disabled={isBusy(item.status)}
          data-tip="선택한 모델로 음성 인식을 시작합니다."
        >
          {item.status === 'queued' ? '대기 중...' : item.status === 'transcribing' ? '전사 중...' : '전사 시작'}
        </button>
        {(item.status === 'queued' || item.status === 'transcribing') && (
          <button
            type="button"
            onClick={handleCancel}
            data-tip={
              item.status === 'queued'
                ? '큐에서 이 파일을 제거합니다.'
                : '진행 중인 전사를 중단합니다.'
            }
          >
            취소
          </button>
        )}
      </div>
      <p className="hint-text">{MODEL_NOTES[model]}</p>
      {!isBusy(item.status) && whisperCacheStatus[model] === false && (
        <p className="hint-text">⬇ 이 모델은 아직 다운로드되지 않았습니다. 전사 시작 시 최초 1회 자동으로 다운로드됩니다.</p>
      )}
      {!isBusy(item.status) && isModelCached && (
        <p className="hint-text">✓ 모델이 이미 다운로드되어 있습니다.</p>
      )}
      {item.status === 'queued' && (
        <p className="hint-text">
          ⏳ 다른 파일 전사가 끝나면 자동으로 순서대로 시작됩니다. (한 번에 하나씩만 처리)
        </p>
      )}
      {item.status === 'transcribing' && isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((item.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            모델 다운로드 중 {Math.round((item.progress ?? 0) * 100)}% (경과{' '}
            {elapsedSeconds != null ? formatClock(elapsedSeconds) : '0:00'}) — 인터넷 연결이
            필요하며 모델 크기에 따라 수 분~수십 분이 걸릴 수 있습니다. (최초 1회만 필요)
          </p>
        </div>
      )}
      {item.status === 'transcribing' && !isDownloadingModel && (
        <div className="progress-block">
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round((item.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="hint-text">
            {Math.round((item.progress ?? 0) * 100)}% 처리 중 (경과{' '}
            {elapsedSeconds != null ? formatClock(elapsedSeconds) : '0:00'}) — 모델을 로드하고 음성을
            인식하는 중입니다. 모델 크기에 따라 수 분이 걸릴 수 있습니다.
          </p>
        </div>
      )}
      {item.status === 'error' && item.error && <p className="error-text">{item.error}</p>}
      {error && <p className="error-text">{error}</p>}
    </section>
  )
}
