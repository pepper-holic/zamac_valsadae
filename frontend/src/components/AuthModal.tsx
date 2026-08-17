import { useState } from 'react'
import { createPortal } from 'react-dom'
import type { AuthActionResult } from '../hooks/useAuth'

type Props = {
  onClose: () => void
  signIn: (email: string, password: string) => Promise<AuthActionResult>
  signUp: (email: string, password: string) => Promise<AuthActionResult>
}

export function AuthModal({ onClose, signIn, signUp }: Props) {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setIsSubmitting(true)
    setMessage(null)
    try {
      const action = mode === 'signin' ? signIn : signUp
      const result = await action(email, password)
      if (result.ok && result.message === null) {
        onClose()
        return
      }
      if (result.message) {
        setMessage({ text: result.message, isError: !result.ok })
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return createPortal(
    <div className="help-overlay" onClick={onClose}>
      <div className="help-modal" onClick={(event) => event.stopPropagation()}>
        <div className="help-header">
          <h2>{mode === 'signin' ? '로그인' : '회원가입'}</h2>
          <button type="button" className="help-close" onClick={onClose} data-tip="닫기">
            ✕
          </button>
        </div>

        <div className="help-body">
          <form className="panel-row" style={{ flexDirection: 'column' }} onSubmit={handleSubmit}>
            <div className="panel-field">
              <label htmlFor="auth-email">이메일</label>
              <input
                id="auth-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>
            <div className="panel-field">
              <label htmlFor="auth-password">비밀번호</label>
              <input
                id="auth-password"
                type="password"
                required
                minLength={6}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            {message && (
              <p className={message.isError ? 'error-text' : 'hint-text'}>{message.text}</p>
            )}

            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? '처리 중...' : mode === 'signin' ? '로그인' : '회원가입'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setMode((prev) => (prev === 'signin' ? 'signup' : 'signin'))
                setMessage(null)
              }}
            >
              {mode === 'signin' ? '계정이 없으신가요? 회원가입' : '이미 계정이 있으신가요? 로그인'}
            </button>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  )
}
