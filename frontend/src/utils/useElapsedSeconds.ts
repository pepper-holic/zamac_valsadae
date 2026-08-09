import { useEffect, useRef, useState } from 'react'

// 경과 시간(초)을 1초마다 갱신해서 반환합니다. active가 false가 되면 타이머를
// 초기화하고 null을 반환하며, 다시 true가 되면 그 시점부터 새로 셉니다.
export function useElapsedSeconds(active: boolean): number | null {
  const startRef = useRef<number | null>(null)
  const [elapsed, setElapsed] = useState<number | null>(null)

  useEffect(() => {
    if (!active) {
      startRef.current = null
      setElapsed(null)
      return
    }
    if (startRef.current === null) {
      startRef.current = Date.now()
    }
    const start = startRef.current
    setElapsed(Math.floor((Date.now() - start) / 1000))
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [active])

  return elapsed
}
