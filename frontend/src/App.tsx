import { useCallback, useEffect, useRef, useState } from 'react'
import './styles/index.css'
import { mediaUrl } from './api/client'
import { GlobalTooltip } from './components/GlobalTooltip'
import { ProgressToast } from './components/ProgressToast'
import { HomeView } from './components/home/HomeView'
import { SegmentDetailPanel } from './components/SegmentDetailPanel'
import { SegmentList } from './components/SegmentList'
import { SubtitleStylePanel } from './components/SubtitleStylePanel'
import { TaskQueuePanel } from './components/TaskQueuePanel'
import { Toolbar } from './components/Toolbar'
import { TranscribePanel } from './components/TranscribePanel'
import { TranslationPanel } from './components/TranslationPanel'
import type { ToolKey } from './components/ToolRail'
import { ToolRail } from './components/ToolRail'
import { VideoStage } from './components/VideoStage'
import { usePanelWidths } from './hooks/usePanelWidths'
import { useProjectWorkspace } from './hooks/useProjectWorkspace'
import { useSegmentEditing } from './hooks/useSegmentEditing'
import { useReviewDiffs } from './hooks/useReviewDiffs'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { startColumnResize } from './utils/resize'

const TOOL_DESCRIPTIONS: Record<ToolKey, string> = {
  transcribe: 'Whisper로 음성을 인식해 문장 목록을 만듭니다.',
  translate: '추출된 문장을 한↔영으로 번역합니다.',
  style: '글꼴/색상/위치/효과를 설정해 미리보기에 반영합니다.',
}

function App() {
  const [activeTool, setActiveTool] = useState<ToolKey>('transcribe')
  const {
    toolPanelWidth,
    videoColumnWidth,
    handleToolPanelWidthChange,
    handleVideoColumnWidthChange,
    TOOL_PANEL_MIN_WIDTH,
    TOOL_PANEL_MAX_WIDTH,
    VIDEO_COLUMN_MIN_WIDTH,
    VIDEO_COLUMN_MAX_WIDTH,
  } = usePanelWidths()

  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [loopSegment, setLoopSegment] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  const resetOnProjectLoadRef = useRef<() => void>(() => {})
  const {
    projects,
    selectedProjectId,
    setSelectedProjectId,
    project,
    setProject,
    selectedItemId,
    setSelectedItemId,
    selectedSegmentId,
    setSelectedSegmentId,
    item,
    activeTasks,
    handleCreateProject,
    handleFilesUploaded,
    handleItemUpdated,
    handleItemDeleted,
    handleProjectUpdated,
    handleProjectDeleted,
    handleSelectTask,
  } = useProjectWorkspace(useCallback(() => resetOnProjectLoadRef.current(), []))

  const {
    canUndo,
    canRedo,
    resetHistory,
    handleSegmentSaved,
    handleSegmentDeleted,
    handleSplitSegment,
    handleMergeSegments,
    handleFindReplace,
    handleBulkDelete,
    handleBulkMarkReviewed,
    handleUndo,
    handleRedo,
    handleResizeSegment,
  } = useSegmentEditing(project, setProject, selectedItemId, selectedSegmentId, setSelectedSegmentId)

  const {
    reviewDiffs,
    resetReview,
    handleReviewImported,
    handleAcceptDiff,
    handleRejectDiff,
    handleAcceptAllDiffs,
    handleRejectAllDiffs,
    toasts,
  } = useReviewDiffs(project, selectedItemId, handleSegmentSaved)

  resetOnProjectLoadRef.current = useCallback(() => {
    resetHistory()
    resetReview()
  }, [resetHistory, resetReview])

  // loop the selected segment when enabled
  useEffect(() => {
    if (!loopSegment || !item || !selectedSegmentId) return
    const segment = item.segments.find((s) => s.id === selectedSegmentId)
    const video = videoRef.current
    if (!segment || !video) return
    if (currentTime >= segment.end) {
      video.currentTime = segment.start
    }
  }, [currentTime, loopSegment, item, selectedSegmentId])

  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
    }
  }, [])

  const handlePlaySegment = useCallback(() => {
    const video = videoRef.current
    const segment = item?.segments.find((s) => s.id === selectedSegmentId)
    if (!video || !segment) return
    video.currentTime = segment.start
    video.play()
  }, [item, selectedSegmentId])

  const handleNavigate = useCallback(
    (direction: 'prev' | 'next') => {
      if (!item || item.segments.length === 0) return
      const index = item.segments.findIndex((s) => s.id === selectedSegmentId)
      const nextIndex =
        direction === 'next'
          ? Math.min(index + 1, item.segments.length - 1)
          : Math.max(index - 1, 0)
      const nextSegment = item.segments[nextIndex === -1 ? 0 : nextIndex]
      setSelectedSegmentId(nextSegment.id)
      handleSeek(nextSegment.start)
    },
    [item, selectedSegmentId, setSelectedSegmentId, handleSeek],
  )

  useKeyboardShortcuts(videoRef, handleUndo, handleRedo, handleNavigate)

  const segments = item?.segments ?? []
  const selectedSegment = segments.find((s) => s.id === selectedSegmentId) ?? null
  const selectedIndex = segments.findIndex((s) => s.id === selectedSegmentId)
  const segmentPosition = selectedIndex >= 0 ? `${selectedIndex + 1} / ${segments.length}` : ''
  const segmentDiffsForSelected = selectedSegment
    ? reviewDiffs.filter((diff) => diff.id === selectedSegment.id)
    : []

  return (
    <div className="app-shell">
      <GlobalTooltip />
      <Toolbar
        projects={projects}
        project={project}
        selectedProjectId={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        onCreateProject={handleCreateProject}
        onFilesUploaded={handleFilesUploaded}
        selectedItemId={selectedItemId}
        onSelectItem={(id) => {
          setSelectedItemId(id)
          const nextItem = project?.items.find((i) => i.id === id)
          setSelectedSegmentId(nextItem?.segments[0]?.id ?? null)
        }}
        onItemUpdated={handleItemUpdated}
        onItemDeleted={handleItemDeleted}
        onProjectDeleted={handleProjectDeleted}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={handleUndo}
        onRedo={handleRedo}
        onGoHome={() => setSelectedProjectId(null)}
        onReviewImported={handleReviewImported}
        reviewDiffCount={reviewDiffs.length}
        onAcceptAllReviewDiffs={handleAcceptAllDiffs}
        onRejectAllReviewDiffs={handleRejectAllDiffs}
      />

      <TaskQueuePanel tasks={activeTasks} onSelectTask={handleSelectTask} />
      <ProgressToast toasts={toasts} />

      {!project && (
        <HomeView
          projects={projects}
          onSelectProject={setSelectedProjectId}
          onCreateProject={handleCreateProject}
          onFilesUploaded={handleFilesUploaded}
          onProjectDeleted={handleProjectDeleted}
        />
      )}

      {project && !item && (
        <p className="empty-hint app-empty-hint">
          이 프로젝트에는 아직 파일이 없습니다. 상단에서 파일을 추가하세요.
        </p>
      )}

      {project && item && (
        <div className="workspace-row">
          <ToolRail activeTool={activeTool} onSelect={setActiveTool} />

          <div className="tool-panel-column" style={{ width: toolPanelWidth }}>
            <div
              className="panel-resize-handle"
              onPointerDown={(event) =>
                startColumnResize(
                  event,
                  toolPanelWidth,
                  handleToolPanelWidthChange,
                  TOOL_PANEL_MIN_WIDTH,
                  TOOL_PANEL_MAX_WIDTH,
                )
              }
              data-tip="드래그해서 패널 너비를 조정합니다."
            />
            <div className="tool-panel-column-head">
              <p className="tool-panel-column-desc">{TOOL_DESCRIPTIONS[activeTool]}</p>
            </div>
            {activeTool === 'transcribe' && (
              <TranscribePanel project={project} item={item} onStarted={handleItemUpdated} />
            )}
            {activeTool === 'translate' && (
              <TranslationPanel
                project={project}
                item={item}
                onStarted={handleItemUpdated}
                onGlossaryUpdated={handleProjectUpdated}
              />
            )}
            {activeTool === 'style' && (
              <SubtitleStylePanel project={project} onStyleUpdated={handleProjectUpdated} />
            )}
          </div>

        <div className="three-column-layout">
          <div className="video-column" style={{ width: videoColumnWidth }}>
          <VideoStage
            videoRef={videoRef}
            src={mediaUrl(project.id, item.id)}
            segments={segments}
            selectedSegmentId={selectedSegmentId}
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            playbackRate={playbackRate}
            loopSegment={loopSegment}
            subtitleStyle={project.subtitle_style}
            onTimeUpdate={setCurrentTime}
            onDurationChange={setDuration}
            onPlayStateChange={setIsPlaying}
            onSeek={handleSeek}
            onRateChange={(rate) => {
              setPlaybackRate(rate)
              if (videoRef.current) videoRef.current.playbackRate = rate
            }}
            onLoopToggle={() => setLoopSegment((prev) => !prev)}
            onSelectSegment={setSelectedSegmentId}
            onResizeSegment={handleResizeSegment}
          />
          </div>

          <div
            className="panel-resize-handle"
            onPointerDown={(event) =>
              startColumnResize(
                event,
                videoColumnWidth,
                handleVideoColumnWidthChange,
                VIDEO_COLUMN_MIN_WIDTH,
                VIDEO_COLUMN_MAX_WIDTH,
              )
            }
            data-tip="드래그해서 영상/목록 영역 너비를 조정합니다."
          />

          <SegmentList
            projectId={project.id}
            itemId={item.id}
            segments={segments}
            selectedSegmentId={selectedSegmentId}
            currentTime={currentTime}
            diffs={reviewDiffs}
            onSelect={(id) => {
              setSelectedSegmentId(id)
              const segment = segments.find((s) => s.id === id)
              if (segment) handleSeek(segment.start)
            }}
            onSegmentSaved={handleSegmentSaved}
            onMergeSegments={handleMergeSegments}
            onFindReplace={handleFindReplace}
            onBulkDelete={handleBulkDelete}
            onBulkMarkReviewed={handleBulkMarkReviewed}
          />

          <SegmentDetailPanel
            project={project}
            item={item}
            segment={selectedSegment}
            segmentPosition={segmentPosition}
            currentTime={currentTime}
            segmentDiffs={segmentDiffsForSelected}
            onSegmentSaved={handleSegmentSaved}
            onSegmentDeleted={handleSegmentDeleted}
            onNavigate={handleNavigate}
            onSeek={handleSeek}
            onPlaySegment={handlePlaySegment}
            onAcceptDiff={handleAcceptDiff}
            onRejectDiff={handleRejectDiff}
            onSplitSegment={handleSplitSegment}
          />
        </div>
        </div>
      )}
    </div>
  )
}

export default App
