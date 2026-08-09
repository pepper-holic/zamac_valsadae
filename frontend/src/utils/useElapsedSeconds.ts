import { useEffect, useState } from 'react'

// startedAt은 서버가 내려주는 작업 시작 시각(UNIX epoch, 초)입니다. 이 값을
// 기준으로 경과 시간을 계산하므로 페이지를 새로고침해도 실제 시작 시각부터
// 다시 셉니다. startedAt이 null이면 진행 중인 작업이 없다는 뜻으로 null을
// 반환합니다.
export function useElapsedSeconds(startedAt: number | null): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (startedAt == null) return
    setNow(Date.now())
    const interval = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [startedAt])

  if (startedAt == null) return null
  return Math.max(0, Math.floor(now / 1000 - startedAt))
}
