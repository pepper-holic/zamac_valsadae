export type ToastTone = 'info' | 'warning' | 'error'

export type Toast = {
  id: string
  tone: ToastTone
  message: string
  progress?: number | null
  onDismiss?: () => void
}

type Props = {
  toasts: Toast[]
}

export function ProgressToast({ toasts }: Props) {
  if (toasts.length === 0) return null

  return (
    <div className="progress-toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`progress-toast progress-toast-${toast.tone}`}>
          <span className="progress-toast-message">{toast.message}</span>
          {toast.progress != null && (
            <div className="progress-toast-bar">
              <div
                className="progress-toast-bar-fill"
                style={{ width: `${Math.round(toast.progress * 100)}%` }}
              />
            </div>
          )}
          {toast.onDismiss && (
            <button
              type="button"
              className="progress-toast-dismiss"
              onClick={toast.onDismiss}
              aria-label="알림 닫기"
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
