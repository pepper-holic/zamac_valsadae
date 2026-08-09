export type ToolKey = 'transcribe' | 'translate' | 'style' | 'review'

type RailTab = { key: ToolKey; icon: string; label: string; tip: string }

const RAIL_TABS: RailTab[] = [
  { key: 'transcribe', icon: '\u{1F399}', label: '전사', tip: 'Whisper로 음성을 인식해 자막(문장 목록)을 만듭니다.' },
  { key: 'translate', icon: '\u{1F310}', label: '번역', tip: '추출된 문장을 한↔영으로 번역합니다.' },
  { key: 'style', icon: 'Aa', label: '스타일', tip: '자막의 글꼴/색상/위치/효과를 설정하고 미리보기에 바로 반영합니다.' },
  { key: 'review', icon: '✓', label: 'AI 검수', tip: '검수용 파일을 내려받아 AI 챗에 올려 교정받고, 결과를 다시 불러옵니다.' },
]

type Props = {
  activeTool: ToolKey | null
  onSelect: (key: ToolKey) => void
}

export function ToolRail({ activeTool, onSelect }: Props) {
  return (
    <nav className="tool-rail" aria-label="자막 도구">
      <div className="tool-rail-group">
        {RAIL_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={tab.key === activeTool ? 'tool-rail-item active' : 'tool-rail-item'}
            onClick={() => onSelect(tab.key)}
            data-tip={tab.tip}
          >
            <span className="tool-rail-glyph" aria-hidden="true">
              {tab.icon}
            </span>
            <span className="tool-rail-label">{tab.label}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
