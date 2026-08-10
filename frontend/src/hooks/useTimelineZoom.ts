import { useState } from 'react'

const ZOOM_LEVELS = [1, 1.5, 2, 3, 4, 6, 8]
const MIN_ZOOM_INDEX = 0
const MAX_ZOOM_INDEX = ZOOM_LEVELS.length - 1

export function useTimelineZoom() {
  const [zoomIndex, setZoomIndex] = useState(MIN_ZOOM_INDEX)
  const zoom = ZOOM_LEVELS[zoomIndex]

  return {
    zoom,
    zoomIn: () => setZoomIndex((prev) => Math.min(prev + 1, MAX_ZOOM_INDEX)),
    zoomOut: () => setZoomIndex((prev) => Math.max(prev - 1, MIN_ZOOM_INDEX)),
    atMin: zoomIndex === MIN_ZOOM_INDEX,
    atMax: zoomIndex === MAX_ZOOM_INDEX,
  }
}
