import { describe, expect, it } from 'vitest'
import { isNewerVersion } from './version'

describe('isNewerVersion', () => {
  it('returns true when the latest patch version is higher', () => {
    expect(isNewerVersion('1.0.0', '1.0.1')).toBe(true)
  })

  it('returns true when the latest major version is higher', () => {
    expect(isNewerVersion('1.2.3', '2.0.0')).toBe(true)
  })

  it('returns false when versions are equal', () => {
    expect(isNewerVersion('1.0.0', '1.0.0')).toBe(false)
  })

  it('returns false when the latest version is older', () => {
    expect(isNewerVersion('1.2.0', '1.1.9')).toBe(false)
  })

  it('handles differing part counts', () => {
    expect(isNewerVersion('1.0', '1.0.1')).toBe(true)
    expect(isNewerVersion('1.0.0', '1.0')).toBe(false)
  })
})
