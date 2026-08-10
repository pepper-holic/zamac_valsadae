export type ToolKey = 'transcribe' | 'translate' | 'style' | 'review'

type RailTab = { key: ToolKey; icon: string; label: string }

const RAIL_TABS: RailTab[] = [
  { key: 'transcribe', icon: '\u{1F399}', label: '전사' },
  { key: 'translate', icon: '\u{1F310}', label: '번역' },
  { key: 'style', icon: 'Aa', label: '스타일' },
  { key: 'review', icon: '✓', label: 'AI 검수' },
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
