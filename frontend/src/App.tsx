import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { getProject, listProjects, mediaUrl, updateSegment } from './api/client'
import type { Project, ReviewDiffEntry, ReviewImportResult, Segment } from './api/types'
import { SegmentDetailPanel } from './components/SegmentDetailPanel'
import { SegmentList } from './components/SegmentList'
import { Toolbar } from './components/Toolbar'
import { VideoStage } from './components/VideoStage'

const POLL_INTERVAL_MS = 1500
const ACTIVE_STATUSES = new Set(['transcribing', 'translating'])

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null)

  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [loopSegment, setLoopSegment] = useState(false)

  const [reviewDiffs, setReviewDiffs] = useState<ReviewDiffEntry[]>([])
  const [reviewUnknownIds, setReviewUnknownIds] = useState<string[]>([])

  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    listProjects().then(setProjects)
  }, [])

  useEffect(() => {
    if (!selectedProjectId) {
      setProject(null)
      return
    }
    getProject(selectedProjectId).then((loaded) => {
      setProject(loaded)
      setSelectedSegmentId(loaded.segments[0]?.id ?? null)
      setReviewDiffs([])
      setReviewUnknownIds([])
    })
  }, [selectedProjectId])

  useEffect(() => {
    if (!project || !ACTIVE_STATUSES.has(project.status)) return
    const interval = setInterval(async () => {
      const refreshed = await getProject(project.id)
      setProject(refreshed)
      setProjects((prev) => prev.map((p) => (p.id === refreshed.id ? refreshed : p)))
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [project])

  // loop the selected segment when enabled
  useEffect(() => {
    if (!loopSegment || !project || !selectedSegmentId) return
    const segment = project.segments.find((s) => s.id === selectedSegmentId)
    const video = videoRef.current
    if (!segment || !video) return
    if (currentTime >= segment.end) {
      video.currentTime = segment.start
    }
  }, [currentTime, loopSegment, project, selectedSegmentId])

  const handleUploaded = useCallback((created: Project) => {
    setProjects((prev) => [...prev, created])
    setSelectedProjectId(created.id)
  }, [])

  const handleProjectUpdated = useCallback((updated: Project) => {
    setProject(updated)
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }, [])

  const handleProjectDeleted = useCallback(
    (projectId: string) => {
      setProjects((prev) => prev.filter((p) => p.id !== projectId))
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null)
      }
    },
    [selectedProjectId],
  )

  const handleSegmentSaved = useCallback((segment: Segment) => {
    setProject((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        segments: prev.segments.map((s) => (s.id === segment.id ? segment : s)),
      }
    })
  }, [])

  const handleSegmentDeleted = useCallback(
    (segmentId: string) => {
      setProject((prev) => {
        if (!prev) return prev
        const index = prev.segments.findIndex((s) => s.id === segmentId)
        const remaining = prev.segments.filter((s) => s.id !== segmentId)
        if (selectedSegmentId === segmentId) {
          const fallback = remaining[Math.min(index, remaining.length - 1)] ?? null
          setSelectedSegmentId(fallback?.id ?? null)
        }
        return { ...prev, segments: remaining }
      })
    },
    [selectedSegmentId],
  )

  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
    }
  }, [])

  const handlePlaySegment = useCallback(() => {
    const video = videoRef.current
    const segment = project?.segments.find((s) => s.id === selectedSegmentId)
    if (!video || !segment) return
    video.currentTime = segment.start
    video.play()
  }, [project, selectedSegmentId])

  const handleNavigate = useCallback(
    (direction: 'prev' | 'next') => {
      if (!project || project.segments.length === 0) return
      const index = project.segments.findIndex((s) => s.id === selectedSegmentId)
      const nextIndex =
        direction === 'next'
          ? Math.min(index + 1, project.segments.length - 1)
          : Math.max(index - 1, 0)
      const nextSegment = project.segments[nextIndex === -1 ? 0 : nextIndex]
      setSelectedSegmentId(nextSegment.id)
      handleSeek(nextSegment.start)
    },
    [project, selectedSegmentId, handleSeek],
  )

  // Keyboard shortcuts: space to play/pause, arrows to seek/navigate segments.
  // Ignored while typing in an input/textarea so text editing isn't hijacked.
  useEffect(() => {
    function isEditableTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target) || !videoRef.current) return

      if (event.code === 'Space') {
        event.preventDefault()
        if (videoRef.current.paused) videoRef.current.play()
        else videoRef.current.pause()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        videoRef.current.currentTime = Math.max(videoRef.current.currentTime - 1, 0)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        videoRef.current.currentTime = videoRef.current.currentTime + 1
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        handleNavigate('prev')
      } else if (event.key === 'ArrowDown') {
        event.preventDefault()
        handleNavigate('next')
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleNavigate])

  const handleReviewImported = useCallback((result: ReviewImportResult) => {
    setReviewDiffs(result.diffs)
    setReviewUnknownIds(result.unknown_segment_ids)
  }, [])

  const handleAcceptDiff = useCallback(
    async (diff: ReviewDiffEntry) => {
      if (!project) return
      const updated = await updateSegment(project.id, diff.id, { [diff.field]: diff.new_value })
      handleSegmentSaved(updated as Segment)
      setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
    },
    [project, handleSegmentSaved],
  )

  const handleRejectDiff = useCallback((diff: ReviewDiffEntry) => {
    setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
  }, [])

  const selectedSegment = project?.segments.find((s) => s.id === selectedSegmentId) ?? null
  const selectedIndex = project?.segments.findIndex((s) => s.id === selectedSegmentId) ?? -1
  const segmentPosition =
    project && selectedIndex >= 0 ? `${selectedIndex + 1} / ${project.segments.length}` : ''
  const segmentDiffsForSelected = selectedSegment
    ? reviewDiffs.filter((diff) => diff.id === selectedSegment.id)
    : []

  return (
    <div className="app-shell">
      <Toolbar
        projects={projects}
        project={project}
        selectedProjectId={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        onUploaded={handleUploaded}
        onProjectUpdated={handleProjectUpdated}
        onProjectDeleted={handleProjectDeleted}
        onReviewImported={handleReviewImported}
      />

      {reviewUnknownIds.length > 0 && (
        <p className="error-text toolbar-warning">
          검수 파일에 알 수 없는 세그먼트 ID가 있습니다: {reviewUnknownIds.join(', ')}
        </p>
      )}

      {!project && (
        <p className="empty-hint app-empty-hint">
          상단에서 파일을 업로드하거나 프로젝트를 선택하세요.
        </p>
      )}

      {project && (
        <div className="three-column-layout">
          <VideoStage
            videoRef={videoRef}
            src={mediaUrl(project.id)}
            segments={project.segments}
            selectedSegmentId={selectedSegmentId}
            currentTime={currentTime}
            duration={duration}
            isPlaying={isPlaying}
            playbackRate={playbackRate}
            loopSegment={loopSegment}
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
          />

          <SegmentList
            projectId={project.id}
            segments={project.segments}
            selectedSegmentId={selectedSegmentId}
            currentTime={currentTime}
            diffs={reviewDiffs}
            onSelect={(id) => {
              setSelectedSegmentId(id)
              const segment = project.segments.find((s) => s.id === id)
              if (segment) handleSeek(segment.start)
            }}
            onSegmentSaved={handleSegmentSaved}
          />

          <SegmentDetailPanel
            project={project}
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
          />
        </div>
      )}
    </div>
  )
}

export default App
