import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): never {
  throw new Error('boom')
}

describe('ErrorBoundary', () => {
  it('renders children normally when there is no error', () => {
    render(
      <ErrorBoundary>
        <p>정상 화면</p>
      </ErrorBoundary>,
    )

    expect(screen.getByText('정상 화면')).toBeInTheDocument()
  })

  it('renders a fallback with a pre-filled GitHub issue link when a child throws', () => {
    // React logs the caught error to console.error - expected here, silence it
    // so the test output isn't confused with an actual test failure.
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )

    expect(screen.getByText('예상치 못한 오류가 발생했습니다')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'GitHub Issue로 신고하기' })
    const url = new URL(link.getAttribute('href')!)
    expect(url.origin + url.pathname).toBe(
      'https://github.com/pepper-holic/zamac_valsadae/issues/new',
    )
    expect(url.searchParams.get('body')).toContain('boom')

    consoleSpy.mockRestore()
  })
})
