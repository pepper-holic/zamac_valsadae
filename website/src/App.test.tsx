import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { LEGAL_PAGES } from './content/legalPages'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App routing', () => {
  it('renders the home page hero at /', () => {
    renderAt('/')
    expect(screen.getByRole('heading', { name: '자막발사대', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '지금 다운로드' })).toBeInTheDocument()
  })

  it.each(LEGAL_PAGES.map((page) => [page.id, page.title] as const))(
    'renders the %s page with its title at /%s',
    (id, title) => {
      renderAt(`/${id}`)
      expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    },
  )

  it('navigates from the header nav link to the download page', async () => {
    const user = userEvent.setup()
    renderAt('/')

    const nav = screen.getByRole('navigation', { name: '주요 메뉴' })
    await user.click(within(nav).getByRole('link', { name: '다운로드' }))

    expect(screen.getByRole('heading', { level: 1, name: '다운로드' })).toBeInTheDocument()
  })

  it('navigates from a footer link to the terms page', async () => {
    const user = userEvent.setup()
    renderAt('/')

    await user.click(screen.getByRole('link', { name: '이용약관' }))

    expect(screen.getByRole('heading', { level: 1, name: '이용약관' })).toBeInTheDocument()
  })
})
