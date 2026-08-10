import { useState } from 'react'
import './legal.css'
import { LEGAL_PAGES, LEGAL_PAGE_GROUPS } from './legalPages'

type Props = {
  onClose: () => void
}

const DUMMY_FLAGGED_IDS = new Set([
  'terms',
  'privacy',
  'refund',
  'company',
  'pricing',
  'community',
  'notices',
  'insights',
])

export function LegalPagesModal({ onClose }: Props) {
  const [activeId, setActiveId] = useState(LEGAL_PAGES[0].id)
  const activePage = LEGAL_PAGES.find((page) => page.id === activeId) ?? LEGAL_PAGES[0]

  return (
    <div className="legal-overlay" onClick={onClose}>
      <div className="legal-modal" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="legal-close" onClick={onClose} data-tip="닫기" aria-label="닫기">
          ✕
        </button>

        <nav className="legal-sidebar" aria-label="법적/회사 정보 페이지">
          <div className="legal-sidebar-notice">
            <b>서버 호스팅 전환 대비 초안</b>
            <span className="legal-dummy">더미</span> 표시가 붙은 값은 실제 정보가 아닙니다.
          </div>

          {LEGAL_PAGE_GROUPS.map((group) => (
            <div className="legal-nav-group" key={group}>
              <div className="legal-nav-group-label">{group}</div>
              {LEGAL_PAGES.filter((page) => page.group === group).map((page) => (
                <button
                  key={page.id}
                  type="button"
                  className={page.id === activeId ? 'legal-nav-btn active' : 'legal-nav-btn'}
                  onClick={() => setActiveId(page.id)}
                >
                  {page.title}
                  {DUMMY_FLAGGED_IDS.has(page.id) && <span className="legal-nav-flag">더미</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="legal-content">
          <select
            className="legal-mobile-nav"
            aria-label="페이지 선택"
            value={activeId}
            onChange={(event) => setActiveId(event.target.value)}
          >
            {LEGAL_PAGES.map((page) => (
              <option key={page.id} value={page.id}>
                {page.title}
              </option>
            ))}
          </select>

          <p className="legal-eyebrow">{activePage.group}</p>
          <h1 className="legal-page-title">{activePage.title}</h1>
          {activePage.subtitle && <p className="legal-page-sub">{activePage.subtitle}</p>}
          {activePage.content}
        </div>
      </div>
    </div>
  )
}
