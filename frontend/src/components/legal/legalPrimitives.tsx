import type { ReactNode } from 'react'

export function Dummy({ children }: { children: ReactNode }) {
  return <span className="legal-dummy">{children}</span>
}

export function DummyBanner({ children }: { children: ReactNode }) {
  return (
    <div className="legal-dummy-banner">
      <span className="legal-dummy-banner-dot" aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export function FieldList({ items }: { items: { k: string; v: ReactNode }[] }) {
  return (
    <ul className="legal-field-list">
      {items.map((item) => (
        <li key={item.k}>
          <span className="legal-field-k">{item.k}</span>
          <span className="legal-field-v">{item.v}</span>
        </li>
      ))}
    </ul>
  )
}

export function Suggest({ children }: { children: ReactNode }) {
  return (
    <div className="legal-suggest">
      <b>더미 제안</b> {children}
    </div>
  )
}

export function StatusChip({ tone, children }: { tone: 'ok' | 'warn'; children: ReactNode }) {
  return (
    <span className={tone === 'warn' ? 'legal-status-chip warn' : 'legal-status-chip'}>
      <span className="dot" aria-hidden="true" />
      {children}
    </span>
  )
}

export function LinkCard({ href, sub, children }: { href: string; sub: string; children: ReactNode }) {
  return (
    <a className="legal-link-card" href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <br />
      <span className="legal-link-card-url">{sub}</span>
    </a>
  )
}

export function Clause({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="legal-clause">
      <h3>{title}</h3>
      {children}
    </div>
  )
}
