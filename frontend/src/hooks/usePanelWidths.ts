import { useCallback, useState } from 'react'

const TOOL_PANEL_MIN_WIDTH = 180
const TOOL_PANEL_MAX_WIDTH = 460
const VIDEO_COLUMN_MIN_WIDTH = 360
const VIDEO_COLUMN_MAX_WIDTH = 1100

function readStoredWidth(key: string, fallback: number): number {
  const stored = Number(window.localStorage.getItem(key))
  return Number.isFinite(stored) && stored > 0 ? stored : fallback
}

export function usePanelWidths() {
  const [toolPanelWidth, setToolPanelWidth] = useState(() => readStoredWidth('zv_toolPanelWidth', 260))
  const [videoColumnWidth, setVideoColumnWidth] = useState(() => readStoredWidth('zv_videoColumnWidth', 620))

  const handleToolPanelWidthChange = useCallback((next: number) => {
    setToolPanelWidth(next)
    window.localStorage.setItem('zv_toolPanelWidth', String(next))
  }, [])

  const handleVideoColumnWidthChange = useCallback((next: number) => {
    setVideoColumnWidth(next)
    window.localStorage.setItem('zv_videoColumnWidth', String(next))
  }, [])

  return {
    toolPanelWidth,
    videoColumnWidth,
    handleToolPanelWidthChange,
    handleVideoColumnWidthChange,
    TOOL_PANEL_MIN_WIDTH,
    TOOL_PANEL_MAX_WIDTH,
    VIDEO_COLUMN_MIN_WIDTH,
    VIDEO_COLUMN_MAX_WIDTH,
  }
}
