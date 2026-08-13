import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AuthModal } from './AuthModal'

describe('AuthModal', () => {
  it('signs in with the entered email/password and closes on success', async () => {
    const user = userEvent.setup()
    const signIn = vi.fn().mockResolvedValue({ ok: true, message: null })
    const signUp = vi.fn()
    const onClose = vi.fn()
    render(<AuthModal onClose={onClose} signIn={signIn} signUp={signUp} />)

    await user.type(screen.getByLabelText('이메일'), 'a@b.com')
    await user.type(screen.getByLabelText('비밀번호'), 'secret1')
    await user.click(screen.getByRole('button', { name: '로그인' }))

    expect(signIn).toHaveBeenCalledWith('a@b.com', 'secret1')
    expect(onClose).toHaveBeenCalled()
  })

  it('shows an error and stays open when sign-in fails', async () => {
    const user = userEvent.setup()
    const signIn = vi.fn().mockResolvedValue({ ok: false, message: '잘못된 비밀번호입니다.' })
    const onClose = vi.fn()
    render(<AuthModal onClose={onClose} signIn={signIn} signUp={vi.fn()} />)

    await user.type(screen.getByLabelText('이메일'), 'a@b.com')
    await user.type(screen.getByLabelText('비밀번호'), 'wrongpass')
    await user.click(screen.getByRole('button', { name: '로그인' }))

    expect(await screen.findByText('잘못된 비밀번호입니다.')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('switches to sign-up mode and calls signUp on submit', async () => {
    const user = userEvent.setup()
    const signUp = vi.fn().mockResolvedValue({ ok: true, message: '가입 확인 이메일을 보냈습니다.' })
    const onClose = vi.fn()
    render(<AuthModal onClose={onClose} signIn={vi.fn()} signUp={signUp} />)

    await user.click(screen.getByRole('button', { name: /회원가입/ }))
    await user.type(screen.getByLabelText('이메일'), 'new@user.com')
    await user.type(screen.getByLabelText('비밀번호'), 'password123')
    await user.click(screen.getByRole('button', { name: '회원가입' }))

    expect(signUp).toHaveBeenCalledWith('new@user.com', 'password123')
    expect(await screen.findByText('가입 확인 이메일을 보냈습니다.')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })
})
