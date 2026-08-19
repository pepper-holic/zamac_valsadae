import { useEffect, useState } from 'react'
import type { Toast } from '../components/ProgressToast'
import { APP_VERSION } from '../version'
import { isNewerVersion } from '../utils/version'

// 소유 도메인이 정해지면 이 오라클 VM의 nip.io 임시 주소를 교체하세요 (다른 WEBSITE_URL
// 상수들과 동일 - AboutModal.tsx, Toolbar.tsx 참고).
const WEBSITE_URL = 'https://site.168-110-107-78.nip.io'
const LATEST_VERSION_URL = `${WEBSITE_URL}/latest-version.json`

type LatestVersionInfo = {
  version: string
  url: string
}

/**
 * One-shot check against the marketing site's static latest-version.json on
 * startup. Best-effort only - a network failure (offline, site down) is
 * swallowed silently since this is purely informational, not a blocking
 * requirement to use the app.
 */
export function useUpdateCheck() {
  const [dismissed, setDismissed] = useState(false)
  const [latest, setLatest] = useState<LatestVersionInfo | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(LATEST_VERSION_URL)
      .then((response) => (response.ok ? (response.json() as Promise<LatestVersionInfo>) : null))
      .then((data) => {
        if (!cancelled && data && isNewerVersion(APP_VERSION, data.version)) {
          setLatest(data)
        }
      })
      .catch(() => {
        // offline / site unreachable - no update banner, no error surfaced
      })
    return () => {
      cancelled = true
    }
  }, [])

  const updateToast: Toast | null =
    latest && !dismissed
      ? {
          id: 'update-available',
          tone: 'info',
          message: (
            <>
              새 버전({latest.version})이 있습니다 -{' '}
              <a href={latest.url} target="_blank" rel="noopener noreferrer">
                다운로드
              </a>
            </>
          ),
          onDismiss: () => setDismissed(true),
        }
      : null

  return { updateToast }
}
