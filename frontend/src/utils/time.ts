export function formatTimestamp(seconds: number): string {
  const totalMs = Math.round(seconds * 1000)
  const ms = totalMs % 1000
  const totalSeconds = Math.floor(totalMs / 1000)
  const s = totalSeconds % 60
  const m = Math.floor(totalSeconds / 60) % 60
  const h = Math.floor(totalSeconds / 3600)
  const pad = (n: number, len = 2) => n.toString().padStart(len, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}.${pad(ms, 3)}`
}

export function formatClock(seconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(seconds))
  const s = totalSeconds % 60
  const m = Math.floor(totalSeconds / 60)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(m)}:${pad(s)}`
}

export function parseTimestamp(value: string): number | null {
  const match = value.trim().match(/^(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d{1,3}))?$/)
  if (!match) {
    const asNumber = Number(value)
    return Number.isFinite(asNumber) ? asNumber : null
  }
  const [, h, m, s, ms] = match
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms ?? 0) / 1000
}
