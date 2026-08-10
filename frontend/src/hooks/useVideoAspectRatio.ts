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
  const isPortraitFrame = effectiveRatio < 1
  const videoFrameStyle: CSSProperties = isPortraitFrame
    ? { aspectRatio: String(effectiveRatio), height: 'min(60vh, 100%)', width: 'auto', maxWidth: '100%' }
    : { aspectRatio: String(effectiveRatio), width: '100%', maxHeight: 'min(60vh, 100%)' }

  return { aspectRatioId, setAspectRatioId, videoFrameStyle, handleLoadedMetadata }
}
