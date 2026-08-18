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

export function OsCard({
  icon,
  title,
  status,
  children,
}: {
  icon: string
  title: string
  status: 'ok' | 'soon'
  children: ReactNode
}) {
  return (
    <div className={status === 'ok' ? 'os-card os-card-ready' : 'os-card'}>
      <div className="os-card-head">
        <span className="os-card-icon" aria-hidden="true">
          {icon}
        </span>
        <div>
          <b>{title}</b>
          <StatusChip tone={status === 'ok' ? 'ok' : 'warn'}>
            {status === 'ok' ? '사용 가능' : '빌드 준비 중'}
          </StatusChip>
        </div>
      </div>
      <div className="os-card-body">{children}</div>
    </div>
  )
}

export function PlanCard({
  name,
  price,
  priceNote,
  features,
  recommended,
}: {
  name: string
  price: string
  priceNote?: string
  features: string[]
  recommended?: boolean
}) {
  return (
    <div className={recommended ? 'plan-card plan-card-rec' : 'plan-card'}>
      {recommended && <span className="plan-card-badge">추천</span>}
      <b className="plan-card-name">{name}</b>
      <div className="plan-card-price">
        {price}
        {priceNote && <span className="legal-price-note"> · {priceNote}</span>}
      </div>
      <ul className="plan-card-features">
        {features.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>
    </div>
  )
}
