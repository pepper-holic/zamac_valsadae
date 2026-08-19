/**
 * Compares two "x.y.z" version strings. Not a full semver implementation
 * (no pre-release/build metadata handling) - releases here are bumped
 * manually and sequentially, so a simple numeric part-by-part comparison
 * is enough.
 */
export function isNewerVersion(current: string, latest: string): boolean {
  const currentParts = current.split('.').map(Number)
  const latestParts = latest.split('.').map(Number)
  const length = Math.max(currentParts.length, latestParts.length)

  for (let i = 0; i < length; i++) {
    const currentPart = currentParts[i] ?? 0
    const latestPart = latestParts[i] ?? 0
    if (latestPart > currentPart) return true
    if (latestPart < currentPart) return false
  }
  return false
}
