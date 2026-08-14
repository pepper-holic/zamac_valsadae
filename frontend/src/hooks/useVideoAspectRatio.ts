import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'

type AspectOption = { id: string; label: string; ratio: number | null }

// ratio = width / height; null means "원본" (read from the loaded video's own dimensions).
export const ASPECT_OPTIONS: AspectOption[] = [
  { id: 'auto', label: '원본 비율', ratio: null },
  { id: '16:9', label: '16:9 · 유튜브', ratio: 16 / 9 },
  { id: '9:16', label: '9:16 · 쇼츠/릴스', ratio: 9 / 16 },
  { id: '1:1', label: '1:1 · 정사각형', ratio: 1 },
  { id: '4:5', label: '4:5 · 인스타 피드', ratio: 4 / 5 },
]
const DEFAULT_ASPECT_ID = '16:9'
const ASPECT_STORAGE_KEY = 'zv_previewAspectRatio'
const OUTER_FRAME_RATIO = 16 / 9

export function useVideoAspectRatio(src: string) {
  const [aspectRatioId, setAspectRatioId] = useState<string>(
    () => window.localStorage.getItem(ASPECT_STORAGE_KEY) ?? DEFAULT_ASPECT_ID,
  )
  const [naturalRatio, setNaturalRatio] = useState<number | null>(null)

  useEffect(() => {
    window.localStorage.setItem(ASPECT_STORAGE_KEY, aspectRatioId)
  }, [aspectRatioId])

  useEffect(() => {
    setNaturalRatio(null)
  }, [src])

  function handleLoadedMetadata(event: React.SyntheticEvent<HTMLVideoElement>) {
    const video = event.currentTarget
    if (video.videoWidth > 0 && video.videoHeight > 0) {
      setNaturalRatio(video.videoWidth / video.videoHeight)
    }
  }

  const selectedAspect = ASPECT_OPTIONS.find((option) => option.id === aspectRatioId) ?? ASPECT_OPTIONS[1]
  const effectiveRatio = selectedAspect.ratio ?? naturalRatio ?? 16 / 9

  // The outer frame always keeps the same 16:9 footprint - it's the visible
  // "canvas" size and doesn't change when the ratio picker changes. Only the
  // inner content box (letterboxed/pillarboxed within it) reflects the
  // selected ratio, the way an editor's export-ratio preview usually works.
  const outerFrameStyle: CSSProperties = {
    aspectRatio: String(OUTER_FRAME_RATIO),
    width: '100%',
    maxHeight: 'min(60vh, 100%)',
  }

  // Fit the inner box within the fixed outer frame: anything narrower than
  // the frame's own ratio must be constrained by height (auto-derived width
  // via aspect-ratio), otherwise a definite width:100% would just inherit
  // the frame's full width instead of shrinking to the selected ratio.
  const innerFrameStyle: CSSProperties =
    effectiveRatio < OUTER_FRAME_RATIO
      ? { aspectRatio: String(effectiveRatio), height: '100%', width: 'auto', maxWidth: '100%' }
      : { aspectRatio: String(effectiveRatio), width: '100%', maxHeight: '100%' }

  return { aspectRatioId, setAspectRatioId, outerFrameStyle, innerFrameStyle, handleLoadedMetadata }
}
