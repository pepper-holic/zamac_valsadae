import { useCallback, useEffect, useState } from 'react'
import { clearAuthSession, postAuthSession } from '../api/client'
import { isAuthConfigured, supabase } from '../lib/supabaseClient'

export type AuthActionResult = { ok: boolean; message: string | null }

export function useAuth() {
  const [email, setEmail] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(isAuthConfigured)

  useEffect(() => {
    if (!supabase) {
      setIsLoading(false)
      return
    }

    supabase.auth.getSession().then(async ({ data }) => {
      const session = data.session
      if (session?.user.email) {
        await postAuthSession(session.access_token, session.user.email)
        setEmail(session.user.email)
      }
      setIsLoading(false)
    })

    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_OUT') {
        void clearAuthSession()
        setEmail(null)
        return
      }
      if (session?.user.email) {
        void postAuthSession(session.access_token, session.user.email)
        setEmail(session.user.email)
      }
    })

    return () => subscription.subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async (email: string, password: string): Promise<AuthActionResult> => {
    if (!supabase) return { ok: false, message: '로그인이 설정되지 않았습니다.' }
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    return error ? { ok: false, message: error.message } : { ok: true, message: null }
  }, [])

  const signUp = useCallback(async (email: string, password: string): Promise<AuthActionResult> => {
    if (!supabase) return { ok: false, message: '로그인이 설정되지 않았습니다.' }
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) return { ok: false, message: error.message }
    if (!data.session) {
      return { ok: true, message: '가입 확인 이메일을 보냈습니다. 메일함을 확인해주세요.' }
    }
    return { ok: true, message: null }
  }, [])

  const signOut = useCallback(async () => {
    if (!supabase) return
    await supabase.auth.signOut()
  }, [])

  return { email, isLoading, isAuthConfigured, signIn, signUp, signOut }
}
