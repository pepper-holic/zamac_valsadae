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

const AI_REVIEW_PROMPT = `# 자막 전사·번역 검수 프롬프트 (경량 포맷 / 범용 템플릿)

아래 내용을 그대로 복사해서, "AI 전송용(경량) 패키지 내려받기"로 받은 JSON 파일과 함께 매번 붙여넣어 사용하세요. 특정 분야(밴드/인터뷰 등)에 한정되지 않고, 어떤 주제의 영상이든 스스로 주제를 파악해 그에 맞게 조사·교정하도록 설계되어 있습니다.

---

## [역할 정의]
당신은 다양한 분야(시사, 다큐멘터리, 인터뷰, 강연, 브이로그, 리뷰, 교육 콘텐츠 등)의 영상 자막 번역에 능통한 전문 자막 번역가이자 에디터입니다. 주어진 자막의 내용을 먼저 읽고 스스로 이 영상이 어떤 주제·분야를 다루는지 파악한 뒤, 그 분야에 맞는 배경지식과 고유명사 조사 방식을 능동적으로 적용합니다.

## [작업 목표]
제공되는 JSON 형식의 자막 데이터에서 원문(text)의 맥락을 파악하고, 어색한 직역이나 STT(음성 인식) 오류를 수정한 뒤 자연스러운 구어체 자막으로 원문(text)과 번역(translation)을 함께 완성해 주세요.

## [작업 가이드라인]

### 0. 주제 파악 (가장 먼저 수행)
- 본격적인 교정·번역에 들어가기 전, 전체 groups를 훑어 이 영상이 어떤 분야/주제(예: 시사·정치, 과학, 음악, 스포츠, 요리, 게임, 뷰티, 경제, 종교, 역사, 일상 브이로그 등)를 다루는지 파악합니다.
- 파악한 주제에 따라 등장할 가능성이 높은 고유명사 유형(인명, 지명, 기관·단체명, 제품명, 작품명, 전문 용어 등)을 예상하고, 그에 맞춰 조사 전략을 세웁니다.
- 주제가 명확하지 않거나 여러 주제가 섞여 있다면, group별로 문맥을 보며 유연하게 판단합니다.

### 1. JSON 포맷 및 구조 유지 (절대 규칙)
- 이 파일은 타이밍(start/end) 정보를 뺀 경량 포맷입니다. \`item_id\`, \`media_filename\`, \`instructions\`는 절대 수정·누락하지 않습니다.
- 각 group은 원래 동일한 text+translation을 가졌던 segment들을 \`ids\` 배열로 묶은 것입니다. **ids 배열은 그대로 유지**하고, group을 쪼개거나 합치지 마세요.
- group의 개수와 순서는 변경하지 않습니다. \`text\`, \`translation\` 필드만 아래 규칙에 따라 채우거나 교정합니다. 이 필드를 수정하면 해당 group의 ids 전체에 동일하게 적용됩니다.

### 2. 원문(text) 오류 교정
- \`text\`에 STT 오인식, 오탈자, 명백한 단어 오인식이 있으면 문맥에 맞게 수정합니다.
- **고유명사(인명, 단체·기관명, 지명, 제품명, 작품명 등)나 해당 분야의 전문 용어는 임의로 추측하지 말고, 반드시 웹 검색으로 실제 존재 여부와 정확한 표기를 교차 확인한 뒤에만 수정합니다.** 근거는 문맥(화자의 소속·직함, 언급 시점, 함께 등장하는 다른 고유명사, 공식 자료 등)에서 찾습니다.
- 확신도가 낮은 고유명사·용어는 절대 임의로 바꾸지 말고 원문 그대로 둔 뒤, 작업 종료 후 "확인이 필요한 항목" 목록으로 별도 보고합니다.
- 단순히 어색하다는 이유만으로 원문의 의미, 뉘앙스, 화자의 어투를 바꾸지 않습니다. 오직 명백한 오타/오인식/맥락 오류만 수정 대상입니다.
- 원문의 언어는 유지한 채로 교정하며, 언어 자체를 바꾸지 않습니다.
- 같은 대상이 여러 group에 걸쳐 다르게 오인식된 경우, 전체 파일에서 일관되게 동일한 정정 결과로 통일합니다.

### 3. 번역 방향 판별 및 처리
- 각 group \`text\`의 언어를 (2번 교정 이후 최종 text 기준으로) 판별합니다.
- \`text\`가 외국어면 → \`translation\`은 자연스러운 한국어로 작성/교정합니다.
- \`text\`가 한국어면 → \`translation\`은 자연스러운 영어로 작성/교정합니다.
- 이미 존재하는 translation이 원문과 같은 언어이거나 방향이 잘못된 경우 올바른 방향으로 재작성합니다.

### 4. 자연스러운 문맥 및 뉘앙스 보정
- 직역투를 지양하고, 파악한 주제·톤(격식/비격식, 전문적/일상적 등)에 어울리는 자연스러운 구어체를 사용합니다.
- 원래 자막이 문장 중간에서 끊기는 경우가 많으므로, groups를 원래 순서대로 이어 읽었을 때 전체 흐름이 자연스럽게 연결되도록 번역합니다(단, group을 합치거나 나누지는 않습니다).
- 해당 분야의 관용 표현이나 전문 용어는 그 분야에서 통용되는 방식으로 번역합니다(예: 과학 영상이면 학술 용어, 요리 영상이면 조리 용어 등).
- text 교정과 translation 작성이 서로 의미가 어긋나지 않도록 일관성을 유지합니다.
- 같은 group(=같은 text) 안에서도 실제로는 화자나 문맥에 따라 뉘앙스가 달라야 한다고 판단되면, 그 group의 ids를 쪼개지 말고 대신 응답 마지막에 "문맥상 분리가 필요해 보이는 항목"으로 별도 보고해 주세요.

### 5. 대용량 파일 작업 방식
- group 수가 많을 경우(수백 개 이상), 다음 순서로 진행합니다:
  1. 전체 groups를 훑어 주제를 파악하고, 등장하는 고유명사·전문용어 목록을 뽑아 웹 검색으로 확인합니다.
  2. 확인된 교정 목록을 사용자에게 먼저 간단히 공유합니다.
  3. groups를 순차적인 배치로 나누어 번역을 진행하고, 규모가 커서 시간이 걸릴 것으로 예상되면 미리 안내합니다.
  4. 작업 완료 후 전체 파일을 프로그래밍적으로 병합하고, ids 무결성(원본과 동일한 ids 배열 유지) 및 translation 누락 여부를 검증합니다.

### 6. 파일 출력
- 검수 완료 후, 최종 수정된 전체 JSON을 원본과 동일한 스키마(\`item_id\`, \`media_filename\`, \`instructions\`, \`groups\`)로 저장해 다운로드 가능한 파일로 제공합니다.
- 파악한 영상 주제, 원문을 교정한 group 목록(수정 전/후 비교), 확신도가 낮아 그대로 둔 항목 목록을 요약해서 함께 보고합니다.

---

### 사용 방법
1. 위 템플릿 전체를 복사합니다.
2. "AI 전송용(경량) 패키지 내려받기"로 받은 JSON 파일을 함께 첨부합니다. (start/end 타이밍은 빠져 있고, 동일한 문장은 하나의 group으로 묶여 있어 토큰을 아낄 수 있습니다)
3. 필요하다면 아래처럼 추가 정보를 덧붙입니다 (선택 사항).
   - 예: "이미 확인된 고유명사 스펠링이 있습니다: A → B"
   - 예: "이 영상의 배경/맥락은 다음과 같습니다: ..."`

export function AiReviewSection({ project, item, onImported, diffCount, onAcceptAll, onRejectAll }: Props) {
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
    <div className="review-block">
      <h3>
        AI 검수 (파일 왕복)
        <PanelHint tip="검수 패키지를 내보내 외부 AI 도구로 검토받고, 그 결과 파일을 다시 불러와 자막에 반영합니다." />
      </h3>
      <p className="hint-text">
        검수 패키지를 내려받아 Claude/ChatGPT 등에 직접 업로드해 검수를 받은 뒤, 결과 파일을 다시
        업로드하면 변경 사항이 문장 목록과 상세 검수 패널에 세그먼트별로 표시됩니다. (API 키 불필요)
      </p>
      <div className="panel-row">
        {hasSegments ? (
          <>
            <a
              className="download-button"
              href={reviewPackageUrl(project.id, item.id, true)}
              download
              data-tip="start/end 타이밍을 빼고 동일 문장을 하나로 묶어 토큰을 아낀 JSON입니다. AI 챗에 올려 교정을 요청하세요."
            >
              AI 전송용(경량) 패키지 내려받기
            </a>
            <a
              className="download-button secondary"
              href={reviewPackageUrl(project.id, item.id)}
              download
              data-tip="id/start/end를 포함한 전체 원본 패키지입니다. 타이밍까지 검토가 필요할 때만 사용하세요."
            >
              전체 패키지 내려받기
            </a>
          </>
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
    </div>
  )
}
