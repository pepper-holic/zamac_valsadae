import { useCallback, useState } from 'react'
import type { Toast } from '../components/ProgressToast'

let nextErrorId = 0

/**
 * Shared "surface this failed request to the user" helper. Several editing
 * actions (split/merge/undo/delete/...) used to swallow network errors
 * silently - the button would just stop spinning as if nothing happened,
 * with no indication the edit was never saved to the backend.
 */
export function useErrorToasts() {
  const [errors, setErrors] = useState<{ id: string; message: string }[]>([])

  const pushError = useCallback((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error)
    const id = `error-${nextErrorId++}`
    setErrors((prev) => [...prev, { id, message }])
  }, [])

  const dismissError = useCallback((id: string) => {
    setErrors((prev) => prev.filter((entry) => entry.id !== id))
  }, [])

  const errorToasts: Toast[] = errors.map((entry) => ({
    id: entry.id,
    tone: 'error',
    message: entry.message,
    onDismiss: () => dismissError(entry.id),
  }))

  return { errorToasts, pushError }
}
