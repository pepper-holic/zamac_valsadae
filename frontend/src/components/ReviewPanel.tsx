import { useRef, useState } from 'react'
import type { MediaItem, Project, ReviewImportResult } from '../api/types'
import { importReviewPackage, reviewPackageUrl } from '../api/client'
import { PanelHint } from './PanelHint'

type Props = {
  project: Project
  item: MediaItem
  onImported: (result: ReviewImportResult) => void
  diffCount: number
  onAcceptAll: () => Promise<void>
  onRejectAll: () => void
}

const AI_REVIEW_PROMPT = `[역할 정의]
당신은 서브컬처, 음악 다큐멘터리 및 자막 번역에 능통한 전문 영상 자막 번역가이자 에디터입니다.

[작업 목표]
제공되는 JSON 형식의 자막 데이터에서 원문(text)의 맥락을 파악하고, 어색한 직역이나 음성 인식(STT) 오류를 수정한 뒤 자연스러운 구어체 자막으로 원문(text)과 번역(translation)을 함께 교정해 주세요.

[작업 가이드라인]

1. JSON 포맷 및 구조 유지:
   * 'item_id', 'media_filename', 'instructions' 및 각 segment의 'id', 'start', 'end' 값은 절대로 수정하거나 누락하지 마세요.
   * 'text'와 'translation' 필드는 아래 2~4번 가이드라인에 따라 내용을 교정할 수 있습니다. 단, segment의 개수나 순서, 타임코드는 변경하지 마세요.

2. 원문(text) 오류 교정 (신규):
   * 'text' 필드에 음성 인식(STT) 오류, 오탈자, 명백한 단어 오인식이 있는 경우 문맥과 실제 영상 상황에 맞게 자연스럽게 수정하세요.
     (예: Hunk -> Punk, tongue-catching/pen -> Zine, grasshopper -> 관점 등 문맥상 명확히 오인식된 단어)
   * 단순히 어색하다는 이유만으로 원문의 의미나 뉘앙스, 화자의 어투를 임의로 바꾸지 마세요. 오직 명백한 오타/오인식/맥락 오류만 수정 대상입니다.
   * 원문의 언어(영어/한국어 등)는 유지한 채로 교정하며, 언어 자체를 바꾸지 않습니다.

3. 번역 방향 판별 및 처리:
   * 각 segment의 'text' 필드 언어를 먼저 판별하세요. (2번에서 교정한 이후의 최종 text 기준)
   * 'text'가 영어(또는 기타 외국어)인 경우 → 'translation' 필드는 자연스러운 한국어로 작성/교정합니다.
   * 'text'가 한국어인 경우 → 'translation' 필드는 자연스러운 영어로 작성/교정합니다.
   * 즉, 원문 언어와 반대되는 언어로 'translation'이 채워지도록 하며, 이미 존재하는 translation이 원문과 같은 언어이거나 방향이 잘못된 경우 올바른 방향으로 재작성하세요.

4. 자연스러운 문맥 및 뉘앙스 보정:
   * 직역투(예: ~하는 편입니다, 사물에 가입하다, 늙은 놈 등)를 지양하고, 실제 다큐멘터리 자막에 어울리는 자연스러운 구어체 말투를 사용하세요. (영→한, 한→영 모두 동일하게 적용)
   * text 교정과 translation 작성 시 서로 의미가 어긋나지 않도록 일관성을 유지하세요.

5. 파일 출력 (중요):
   * 번역 작업 완료 후, 사용자가 바로 파일로 저장하여 업로드할 수 있도록 최종 수정된 전체 JSON 코드를 작성해 주세요.
   * 답변의 맨 마지막 줄에는 아래와 같이 최종 결과를 다운로드할 수 있는 파이썬 코드 블록이나 다운로드 가이드를 제공하거나, JSON 코드 전체를 단일 코드 블록으로 완성해 주세요.`

export function ReviewPanel({ project, item, onImported, diffCount, onAcceptAll, onRejectAll }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
  const [isApplyingAll, setIsApplyingAll] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleAcceptAllClick() {
    setIsApplyingAll(true)
    try {
      await onAcceptAll()
    } finally {
      setIsApplyingAll(false)
    }
  }

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setIsImporting(true)
    setError(null)
    try {
      const result = await importReviewPackage(project.id, item.id, file)
      onImported(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setIsImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleCopyPrompt() {
    try {
      await navigator.clipboard.writeText(AI_REVIEW_PROMPT)
      setCopyStatus('copied')
    } catch {
      setCopyStatus('failed')
    } finally {
      setTimeout(() => setCopyStatus('idle'), 2000)
    }
  }

  const hasSegments = item.segments.length > 0

  return (
    <section className="panel">
      <h2>
        AI 검수 (파일 왕복)
        <PanelHint tip="검수 패키지를 내보내 외부 AI 도구로 검토받고, 그 결과 파일을 다시 불러와 자막에 반영합니다." />
      </h2>
      <p className="hint-text">
        검수 패키지를 내려받아 Claude/ChatGPT 등에 직접 업로드해 검수를 받은 뒤, 결과 파일을 다시
        업로드하면 변경 사항이 문장 목록과 상세 검수 패널에 세그먼트별로 표시됩니다. (API 키 불필요)
      </p>
      <div className="panel-row">
        {hasSegments ? (
          <a
            className="download-button"
            href={reviewPackageUrl(project.id, item.id)}
            download
            data-tip="문장/시간/번역이 담긴 JSON 파일을 내려받습니다. AI 챗에 올려 교정을 요청하세요."
          >
            검수 패키지 내려받기
          </a>
        ) : (
          <span className="hint-text">전사 완료 후 이용 가능</span>
        )}
        <label
          className="upload-button"
          data-tip="AI에게 교정받은 JSON 파일을 다시 업로드하면 변경 사항을 비교해 보여줍니다."
        >
          {isImporting ? '가져오는 중...' : '검수 결과 업로드'}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/json"
            onChange={handleImportFile}
            disabled={!hasSegments || isImporting}
            hidden
          />
        </label>
        <button
          type="button"
          className="secondary"
          onClick={() => setIsPromptVisible((prev) => !prev)}
          data-tip="다운로드한 JSON과 함께 AI 챗에 붙여넣을 검수 프롬프트를 보여줍니다."
        >
          {isPromptVisible ? '프롬프트 닫기' : '검수용 프롬프트 보기'}
        </button>
      </div>
      {error && <p className="error-text">{error}</p>}

      {diffCount > 0 && (
        <div className="segment-bulk-actions">
          <span>AI 검수 변경 제안 {diffCount}건</span>
          <button type="button" onClick={handleAcceptAllClick} disabled={isApplyingAll}>
            {isApplyingAll ? '반영 중...' : '전체 반영'}
          </button>
          <button type="button" className="danger-button" onClick={onRejectAll} disabled={isApplyingAll}>
            전체 거절
          </button>
        </div>
      )}

      {isPromptVisible && (
        <div className="review-prompt-block">
          <p className="hint-text">
            검수 패키지 JSON을 내려받은 뒤, 이 프롬프트를 AI 챗(Claude/ChatGPT 등)에 먼저 붙여넣고
            JSON 파일을 함께 올리면 자연스러운 번역으로 교정받을 수 있습니다.
          </p>
          <textarea className="review-prompt-textarea" readOnly value={AI_REVIEW_PROMPT} />
          <div className="panel-row">
            <button type="button" onClick={handleCopyPrompt}>
              프롬프트 복사
            </button>
            {copyStatus === 'copied' && <span className="saved-check">복사됨 ✓</span>}
            {copyStatus === 'failed' && (
              <span className="error-text">복사에 실패했습니다. 직접 선택해 복사해 주세요.</span>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
