import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuth } from './useAuth'

const { postAuthSession, clearAuthSession } = vi.hoisted(() => ({
  postAuthSession: vi.fn().mockResolvedValue(undefined),
  clearAuthSession: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../api/client', () => ({ postAuthSession, clearAuthSession }))

const { mockSupabase, authStateCallback } = vi.hoisted(() => {
  const state: { callback: ((event: string, session: unknown) => void) | null } = {
    callback: null,
  }
  return {
    authStateCallback: state,
    mockSupabase: {
      auth: {
        getSession: vi.fn(),
        onAuthStateChange: vi.fn((cb: (event: string, session: unknown) => void) => {
          state.callback = cb
          return { data: { subscription: { unsubscribe: vi.fn() } } }
        }),
        signInWithPassword: vi.fn(),
        signUp: vi.fn(),
        signOut: vi.fn(),
      },
    },
  }
})

vi.mock('../lib/supabaseClient', () => ({
  get supabase() {
    return mockSupabase
  },
  isAuthConfigured: true,
}))

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authStateCallback.callback = null
    mockSupabase.auth.getSession.mockResolvedValue({ data: { session: null } })
  })

  it('restores an existing session on mount and syncs it to the backend', async () => {
    mockSupabase.auth.getSession.mockResolvedValue({
      data: { session: { access_token: 'tok-1', user: { email: 'a@b.com' } } },
    })

    const { result } = renderHook(() => useAuth())

    await waitFor(() => expect(result.current.email).toBe('a@b.com'))
    expect(postAuthSession).toHaveBeenCalledWith('tok-1', 'a@b.com')
  })

  it('has no session on mount when none is stored', async () => {
    const { result } = renderHook(() => useAuth())

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.email).toBeNull()
    expect(postAuthSession).not.toHaveBeenCalled()
  })

  it('syncs the backend session on SIGNED_IN and clears it on SIGNED_OUT', async () => {
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    authStateCallback.callback?.('SIGNED_IN', {
      access_token: 'tok-2',
      user: { email: 'c@d.com' },
    })
    await waitFor(() => expect(result.current.email).toBe('c@d.com'))
    expect(postAuthSession).toHaveBeenCalledWith('tok-2', 'c@d.com')

    authStateCallback.callback?.('SIGNED_OUT', null)
    await waitFor(() => expect(result.current.email).toBeNull())
    expect(clearAuthSession).toHaveBeenCalled()
  })

  it('signIn surfaces the error message on failure', async () => {
    mockSupabase.auth.signInWithPassword.mockResolvedValue({
      error: { message: '잘못된 비밀번호입니다.' },
    })
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    const outcome = await result.current.signIn('a@b.com', 'wrong')

    expect(outcome).toEqual({ ok: false, message: '잘못된 비밀번호입니다.' })
  })

  it('signUp reports the confirmation-email message when no session comes back', async () => {
    mockSupabase.auth.signUp.mockResolvedValue({ data: { session: null }, error: null })
    const { result } = renderHook(() => useAuth())
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    const outcome = await result.current.signUp('new@user.com', 'password123')

    expect(outcome.ok).toBe(true)
    expect(outcome.message).toMatch(/이메일/)
  })
})
