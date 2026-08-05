import { useRef, useState } from 'react'
import type { Project, ReviewImportResult } from '../api/types'
import { importReviewPackage, reviewPackageUrl } from '../api/client'

type Props = {
  project: Project
  onImported: (result: ReviewImportResult) => void
}

const AI_REVIEW_PROMPT = `[역할 정의]
당신은 서브컬처, 음악 다큐멘터리 및 자막 번역에 능통한 전문 영상 자막 번역가이자 에디터입니다.

[작업 목표]
제공되는 JSON 형식의 자막 데이터에서 원문(text)의 맥락을 파악하고, 어색한 직역이나 음성 인식(STT) 오류를 수정한 뒤 자연스러운 한국어 구어체 자막으로 번역(translation)을 교정해 주세요.

[작업 가이드라인]
1. JSON 포맷 및 데이터 유지:
   - 'project_id', 'media_filename', 'instructions' 및 각 segment의 'id', 'start', 'end', 'text' 값은 절대로 수정하거나 누락하지 마세요.
   - 오직 'translation' 필드의 한국어 텍스트만 수정합니다.

2. 자연스러운 문맥 및 뉘앙스 보정:
   - 직역투(예: ~하는 편입니다, 사물에 가입하다, 늙은 놈 등)를 지양하고, 실제 한국어 다큐멘터리 자막에 어울리는 자연스러운 구어체 말투를 사용하세요.
   - 문맥상 오타/STT 오류가 명확한 단어는 실제 영상 상황에 맞게 유연하게 해석하세요. (예: Hunk -> Punk, tongue-catching/pen -> Zine/독립출판물, grasshopper -> 시각/관점 등)

3. 파일 출력 (중요):
   - 번역 작업 완료 후, 사용자가 바로 파일로 저장하여 업로드할 수 있도록 최종 수정된 전체 JSON 코드를 작성해 주세요.
   - 답변의 맨 마지막 줄에는 아래와 같이 최종 결과를 다운로드할 수 있는 파이썬 코드 블록이나 다운로드 가이드를 제공하거나, JSON 코드 전체를 단일 코드 블록으로 완성해 주세요.`

export function ReviewPanel({ project, onImported }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [isPromptVisible, setIsPromptVisible] = useState(false)
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle')
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setIsImporting(true)
    setError(null)
    try {
      const result = await importReviewPackage(project.id, file)
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

  const hasSegments = project.segments.length > 0

  return (
    <section className="panel">
      <h2>AI 검수 (파일 왕복)</h2>
      <p className="hint-text">
        검수 패키지를 내려받아 Claude/ChatGPT 등에 직접 업로드해 검수를 받은 뒤, 결과 파일을 다시
        업로드하면 변경 사항이 문장 목록과 상세 검수 패널에 세그먼트별로 표시됩니다. (API 키 불필요)
      </p>
      <div className="panel-row">
        {hasSegments ? (
          <a
            className="download-button"
            href={reviewPackageUrl(project.id)}
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
