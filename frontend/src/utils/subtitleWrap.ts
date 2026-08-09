const SENTENCE_SPLIT_RE = /(?<=[.!?。！？])\s+/

function wrapLongLine(line: string, maxChars: number): string[] {
  const words = line.split(/\s+/).filter(Boolean)
  if (words.length === 0) return [line]
  const lines: string[] = []
  let current = words[0]
  for (const word of words.slice(1)) {
    const candidate = `${current} ${word}`
    if (candidate.length <= maxChars) {
      current = candidate
    } else {
      lines.push(current)
      current = word
    }
  }
  lines.push(current)
  return lines
}

// 마침표/물음표/느낌표 기준으로 우선 나누고, 한 문장 자체가 maxChars를 넘으면
// 단어 단위로 추가 분할합니다. 백엔드 app/services/text_wrap.py와 동일한 규칙.
export function wrapSubtitleText(text: string, maxChars: number): string {
  const trimmed = text.trim()
  if (!trimmed || maxChars <= 0 || trimmed.length <= maxChars) return text

  const sentences = trimmed.split(SENTENCE_SPLIT_RE).filter(Boolean)

  const lines: string[] = []
  let current = ''
  for (const sentence of sentences) {
    const candidate = `${current} ${sentence}`.trim()
    if (candidate.length <= maxChars) {
      current = candidate
    } else {
      if (current) lines.push(current)
      current = sentence
    }
  }
  if (current) lines.push(current)

  const finalLines: string[] = []
  for (const line of lines) {
    if (line.length <= maxChars) finalLines.push(line)
    else finalLines.push(...wrapLongLine(line, maxChars))
  }

  return finalLines.join('\n')
}
