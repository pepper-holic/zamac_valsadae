import { describe, expect, it } from 'vitest'
import { buildReportIssueUrl } from './githubIssueUrl'

describe('buildReportIssueUrl', () => {
  it('points at the project issue tracker with title/body pre-filled', () => {
    const url = buildReportIssueUrl('앱 크래시: boom', '```\nboom\n```')
    const parsed = new URL(url)

    expect(parsed.origin + parsed.pathname).toBe(
      'https://github.com/pepper-holic/zamac_valsadae/issues/new',
    )
    expect(parsed.searchParams.get('title')).toBe('앱 크래시: boom')
    expect(parsed.searchParams.get('body')).toBe('```\nboom\n```')
  })
})
