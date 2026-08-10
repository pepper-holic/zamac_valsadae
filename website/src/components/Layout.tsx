import { NavLink, Outlet } from 'react-router-dom'
import { SiteFooter } from './SiteFooter'
import './layout.css'

const NAV_LINKS = [
  { to: '/', label: '홈', end: true },
  { to: '/download', label: '다운로드' },
  { to: '/pricing', label: '가격 정책' },
  { to: '/company', label: '회사 소개' },
]

export function Layout() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <NavLink to="/" className="site-brand">
          <img className="site-brand-mark" src="/app-icon-glyph.png" alt="" aria-hidden="true" />
          Zamak_Valsadae
        </NavLink>
        <nav className="site-nav" aria-label="주요 메뉴">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => (isActive ? 'site-nav-link active' : 'site-nav-link')}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <a className="site-cta" href="/download">
          다운로드
        </a>
      </header>

      <main className="site-main">
        <Outlet />
      </main>

      <SiteFooter />
    </div>
  )
}
