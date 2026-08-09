import { renderHook } from '@testing-library/react'
import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useElapsedSeconds } from './useElapsedSeconds'

describe('useElapsedSeconds', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns null while no task is running', () => {
    const { result } = renderHook(() => useElapsedSeconds(null))
    expect(result.current).toBeNull()
  })

  it('computes elapsed time from the server-provided start time, not from mount', () => {
    // startedAt is 90 seconds in the past relative to "now" - simulates
    // reopening the browser after a task has already been running a while.
    const nowSeconds = 1_700_000_090
    vi.setSystemTime(nowSeconds * 1000)
    const startedAt = nowSeconds - 90

    const { result } = renderHook(() => useElapsedSeconds(startedAt))
    expect(result.current).toBe(90)
  })

  it('keeps ticking upward every second while active', () => {
    const nowSeconds = 1_700_000_000
    vi.setSystemTime(nowSeconds * 1000)
    const { result } = renderHook(() => useElapsedSeconds(nowSeconds))
    expect(result.current).toBe(0)

    act(() => {
      vi.advanceTimersByTime(3000)
    })
    expect(result.current).toBe(3)
  })

  it('returns to null once the task stops', () => {
    const nowSeconds = 1_700_000_000
    vi.setSystemTime(nowSeconds * 1000)
    const { result, rerender } = renderHook(({ startedAt }) => useElapsedSeconds(startedAt), {
      initialProps: { startedAt: nowSeconds as number | null },
    })
    expect(result.current).toBe(0)

    rerender({ startedAt: null })
    expect(result.current).toBeNull()
  })
})
