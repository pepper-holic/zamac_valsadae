import { useEffect, useState } from 'react'
import type { Toast } from '../components/ProgressToast'
import { buildReportIssueUrl } from '../utils/githubIssueUrl'

let nextId = 0

/**
 * Catches errors that ErrorBoundary can't: uncaught exceptions in event
 * handlers/timers ('error') and unhandled promise rejections
 * ('unhandledrejection'). Unlike a render crash, these don't take down the
 * whole screen, so they surface as a dismissible toast (with a report link)
 * instead of replacing the app.
 */
export function useGlobalErrorToasts() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    function push(message: string, stack?: string) {
      const id = `global-error-${nextId++}`
      const url = buildReportIssueUrl(
        `앱 오류: ${message}`.slice(0, 200),
        ['```', message, stack ?? '', '```'].join('\n'),
      )
      setToasts((prev) => [
        ...prev,
        {
          id,
          tone: 'error',
          message: (
            <>
              오류가 발생했습니다: {message}{' '}
              <a href={url} target="_blank" rel="noopener noreferrer">
                신고하기
              </a>
            </>
          ),
          onDismiss: () => setToasts((current) => current.filter((toast) => toast.id !== id)),
        },
      ])
    }

    function handleError(event: ErrorEvent) {
      push(event.message, event.error?.stack)
    }
    function handleRejection(event: PromiseRejectionEvent) {
      const reason = event.reason
      const message = reason instanceof Error ? reason.message : String(reason)
      push(message, reason instanceof Error ? reason.stack : undefined)
    }

    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleRejection)
    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleRejection)
    }
  }, [])

  return { globalErrorToasts: toasts }
}
