import type { LegalPageDef } from '../content/legalPages'
import '../content/legalContent.css'

type Props = {
  page: LegalPageDef
}

export function LegalPage({ page }: Props) {
  return (
    <article className="legal-page">
      <p className="legal-eyebrow">{page.group}</p>
      <h1 className="legal-page-title">{page.title}</h1>
      {page.subtitle && <p className="legal-page-sub">{page.subtitle}</p>}
      {page.content}
    </article>
  )
}
