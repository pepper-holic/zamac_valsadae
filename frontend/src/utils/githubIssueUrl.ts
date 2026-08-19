const ISSUES_URL = 'https://github.com/pepper-holic/zamac_valsadae/issues/new'

/**
 * Builds a pre-filled "new GitHub issue" URL. Never sends anything over the
 * network on its own - the app has no automatic error telemetry (see
 * HelpModal.tsx's "데이터 보호" section), so reporting is always this: open
 * the form pre-filled, let the user review and submit it themselves.
 */
export function buildReportIssueUrl(title: string, body: string): string {
  const params = new URLSearchParams({ title, body })
  return `${ISSUES_URL}?${params.toString()}`
}
