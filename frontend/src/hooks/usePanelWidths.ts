import { useCallback, useState } from 'react'

const VIDEO_COLUMN_MIN_WIDTH = 360
const VIDEO_COLUMN_MAX_WIDTH = 1100
const WORKSPACE_TOP_MIN_HEIGHT = 320
const WORKSPACE_TOP_MAX_HEIGHT = 900

function readStoredWidth(key: string, fallback: number): number {
  const stored = Number(window.localStorage.getItem(key))
  return Number.isFinite(stored) && stored > 0 ? stored : fallback
}

export function usePanelWidths() {
  const [videoColumnWidth, setVideoColumnWidth] = useState(() => readStoredWidth('zv_videoColumnWidth', 680))
  // v2: the scrubber/timeline row moved out of this area into its own row
  // below it, so the video/review panels need much less height than before -
  // a new key avoids reusing a stale oversized value from localStorage.
  const [workspaceTopHeight, setWorkspaceTopHeight] = useState(() =>
    readStoredWidth('zv_workspaceTopHeight2', 480),
  )

  const handleVideoColumnWidthChange = useCallback((next: number) => {
    setVideoColumnWidth(next)
    window.localStorage.setItem('zv_videoColumnWidth', String(next))
  }, [])

  const handleWorkspaceTopHeightChange = useCallback((next: number) => {
    setWorkspaceTopHeight(next)
    window.localStorage.setItem('zv_workspaceTopHeight2', String(next))
  }, [])

  return {
    videoColumnWidth,
    handleVideoColumnWidthChange,
    VIDEO_COLUMN_MIN_WIDTH,
    VIDEO_COLUMN_MAX_WIDTH,
    workspaceTopHeight,
    handleWorkspaceTopHeightChange,
    WORKSPACE_TOP_MIN_HEIGHT,
    WORKSPACE_TOP_MAX_HEIGHT,
  }
}
