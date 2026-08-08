import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import {
  addItem,
  createProject,
  deleteItem,
  deleteSegment,
  findReplaceSegments,
  getProject,
  mediaUrl,
  mergeSegments,
  listProjects,
  redoItem,
  splitSegment,
  transcribeItem,
  undoItem,
  updateSegment,
} from './api/client'
import type { MediaItem, Project, ReviewDiffEntry, ReviewImportResult, Segment } from './api/types'
import { SegmentDetailPanel } from './components/SegmentDetailPanel'
import { SegmentList } from './components/SegmentList'
import { Toolbar } from './components/Toolbar'
import { VideoStage } from './components/VideoStage'

const POLL_INTERVAL_MS = 1500
const ACTIVE_STATUSES = new Set(['transcribing', 'translating'])

type QueueEntry = { projectId: string; itemId: string }
type HistoryState = { canUndo: boolean; canRedo: boolean }

function updateItemInProject(
  project: Project,
  itemId: string,
  updater: (item: MediaItem) => MediaItem,
): Project {
  return { ...project, items: project.items.map((i) => (i.id === itemId ? updater(i) : i)) }
}

function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null)

  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [loopSegment, setLoopSegment] = useState(false)

  const [reviewDiffs, setReviewDiffs] = useState<ReviewDiffEntry[]>([])
  const [reviewUnknownIds, setReviewUnknownIds] = useState<string[]>([])

  // 아이템별 undo/redo 가능 여부 - 백엔드 히스토리가 아이템 단위 프로세스 메모리에
  // 있어 조회 전용 엔드포인트가 없으므로, 이 세션에서 각 아이템을 마지막으로 편집/
  // undo/redo한 결과를 프론트에 기억해두고 파일을 다시 선택해도 유지합니다.
  const [historyByItem, setHistoryByItem] = useState<Record<string, HistoryState>>({})
  const { canUndo, canRedo } = selectedItemId
    ? (historyByItem[selectedItemId] ?? { canUndo: false, canRedo: false })
    : { canUndo: false, canRedo: false }

  const setItemHistoryState = useCallback((itemId: string, state: HistoryState) => {
    setHistoryByItem((prev) => ({ ...prev, [itemId]: state }))
  }, [])

  const [batchModel, setBatchModel] = useState('small')
  const [transcribeQueue, setTranscribeQueue] = useState<QueueEntry[]>([])
  const [activeQueueEntry, setActiveQueueEntry] = useState<QueueEntry | null>(null)

  const videoRef = useRef<HTMLVideoElement>(null)
  // Set right before setSelectedProjectId() when we already have the fresh
  // Project object in hand (e.g. one we just created) - tells the effect
  // below to skip its own fetch instead of racing a stale one against it.
  const skipNextProjectFetchRef = useRef<string | null>(null)

  const item = project?.items.find((i) => i.id === selectedItemId) ?? null

  useEffect(() => {
    listProjects().then(setProjects)
  }, [])

  useEffect(() => {
    if (!selectedProjectId) {
      setProject(null)
      setSelectedItemId(null)
      return
    }
    if (skipNextProjectFetchRef.current === selectedProjectId) {
      skipNextProjectFetchRef.current = null
      return
    }
    getProject(selectedProjectId).then((loaded) => {
      setProject(loaded)
      setSelectedItemId(loaded.items[0]?.id ?? null)
      setSelectedSegmentId(loaded.items[0]?.segments[0]?.id ?? null)
      setReviewDiffs([])
      setReviewUnknownIds([])
      // 새 프로젝트를 불러오면 백엔드 프로세스가 재시작되지 않은 한 서버 히스토리
      // 자체는 남아있을 수 있지만, 프로젝트를 새로 불러왔다는 것은 최신 상태를
      // 신뢰해야 한다는 뜻이므로 세션의 undo/redo 가능 여부 캐시를 초기화합니다.
      setHistoryByItem({})
    })
  }, [selectedProjectId])

  // poll while the currently viewed file is actively processing
  useEffect(() => {
    if (!project || !item || !ACTIVE_STATUSES.has(item.status)) return
    const interval = setInterval(async () => {
      const refreshed = await getProject(project.id)
      setProject(refreshed)
      setProjects((prev) => prev.map((p) => (p.id === refreshed.id ? refreshed : p)))
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [project, item])

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

  const applyItemUpdate = useCallback((projectId: string, updatedItem: MediaItem) => {
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? updateItemInProject(p, updatedItem.id, () => updatedItem) : p)),
    )
    setProject((prev) => (prev?.id === projectId ? updateItemInProject(prev, updatedItem.id, () => updatedItem) : prev))
  }, [])

  const handleCreateProject = useCallback(async (name: string) => {
    const created = await createProject(name)
    setProjects((prev) => [...prev, created])
    setSelectedProjectId(created.id)
  }, [])

  const handleFilesUploaded = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return

      let targetProjectId = selectedProjectId
      if (!targetProjectId) {
        const created = await createProject()
        setProjects((prev) => [...prev, created])
        setProject(created)
        targetProjectId = created.id
        skipNextProjectFetchRef.current = targetProjectId
        setSelectedProjectId(targetProjectId)
      }

      const newItems: MediaItem[] = []
      for (const file of files) {
        newItems.push(await addItem(targetProjectId, file))
      }

      setProjects((prev) =>
        prev.map((p) => (p.id === targetProjectId ? { ...p, items: [...p.items, ...newItems] } : p)),
      )
      setProject((prev) => (prev && prev.id === targetProjectId ? { ...prev, items: [...prev.items, ...newItems] } : prev))
      setSelectedItemId((prev) => prev ?? newItems[0]?.id ?? null)
      // 새로 추가된 파일들은 파일마다 별도로 관리되면서, 사용자가 하나씩 열어
      // "전사 시작"을 누르지 않아도 순서대로 자동 전사되도록 대기열에 넣습니다.
      setTranscribeQueue((prev) => [
        ...prev,
        ...newItems.map((i) => ({ projectId: targetProjectId as string, itemId: i.id })),
      ])
    },
    [selectedProjectId],
  )

  // 대기열이 비어있지 않고 현재 처리 중인 항목이 없으면 다음 항목의 전사를 시작합니다.
  useEffect(() => {
    if (activeQueueEntry || transcribeQueue.length === 0) return
    const next = transcribeQueue[0]
    setTranscribeQueue((prev) => prev.slice(1))
    setActiveQueueEntry(next)
    transcribeItem(next.projectId, next.itemId, batchModel).then((started) => {
      applyItemUpdate(next.projectId, started)
    })
  }, [transcribeQueue, activeQueueEntry, batchModel, applyItemUpdate])

  // 현재 대기열에서 처리 중인 파일을 별도로 폴링합니다 - 사용자가 다른 파일을
  // 보고 있어도 백그라운드에서 전사가 계속 진행/완료되어야 하므로, "선택된
  // 파일만 폴링"하는 위 effect와는 독립적으로 동작합니다.
  useEffect(() => {
    if (!activeQueueEntry) return
    const interval = setInterval(async () => {
      const refreshedProject = await getProject(activeQueueEntry.projectId)
      setProjects((prev) => prev.map((p) => (p.id === refreshedProject.id ? refreshedProject : p)))
      setProject((prev) => (prev?.id === refreshedProject.id ? refreshedProject : prev))
      const refreshedItem = refreshedProject.items.find((i) => i.id === activeQueueEntry.itemId)
      if (!refreshedItem || refreshedItem.status !== 'transcribing') {
        setActiveQueueEntry(null)
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [activeQueueEntry])

  const handleItemUpdated = useCallback(
    (updatedItem: MediaItem) => {
      if (!project) return
      applyItemUpdate(project.id, updatedItem)
    },
    [project, applyItemUpdate],
  )

  const handleItemDeleted = useCallback(
    async (itemId: string) => {
      if (!project) return
      await deleteItem(project.id, itemId)
      setProject((prev) => (prev ? { ...prev, items: prev.items.filter((i) => i.id !== itemId) } : prev))
      setProjects((prev) =>
        prev.map((p) => (p.id === project.id ? { ...p, items: p.items.filter((i) => i.id !== itemId) } : p)),
      )
      setTranscribeQueue((prev) => prev.filter((entry) => entry.itemId !== itemId))
      if (selectedItemId === itemId) {
        const remaining = project.items.filter((i) => i.id !== itemId)
        setSelectedItemId(remaining[0]?.id ?? null)
        setSelectedSegmentId(remaining[0]?.segments[0]?.id ?? null)
      }
    },
    [project, selectedItemId],
  )

  const handleGlossaryUpdated = useCallback((updated: Project) => {
    setProject((prev) => (prev?.id === updated.id ? updated : prev))
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
  }, [])

  const handleProjectDeleted = useCallback(
    (projectId: string) => {
      setProjects((prev) => prev.filter((p) => p.id !== projectId))
      setTranscribeQueue((prev) => prev.filter((entry) => entry.projectId !== projectId))
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null)
      }
    },
    [selectedProjectId],
  )

  const handleSegmentSaved = useCallback(
    (segment: Segment) => {
      if (!selectedItemId) return
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => ({
              ...i,
              segments: i.segments.map((s) => (s.id === segment.id ? segment : s)),
            }))
          : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [selectedItemId],
  )

  const handleSegmentDeleted = useCallback(
    (segmentId: string) => {
      if (!selectedItemId) return
      setProject((prev) => {
        if (!prev) return prev
        const currentItem = prev.items.find((i) => i.id === selectedItemId)
        if (!currentItem) return prev
        const index = currentItem.segments.findIndex((s) => s.id === segmentId)
        const remaining = currentItem.segments.filter((s) => s.id !== segmentId)
        if (selectedSegmentId === segmentId) {
          const fallback = remaining[Math.min(index, remaining.length - 1)] ?? null
          setSelectedSegmentId(fallback?.id ?? null)
        }
        return updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: remaining }))
      })
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [selectedItemId, selectedSegmentId],
  )

  const handleSplitSegment = useCallback(
    async (splitAt: number) => {
      if (!project || !selectedItemId || !selectedSegmentId) return
      const [first, second] = await splitSegment(project.id, selectedItemId, selectedSegmentId, splitAt)
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => {
              const index = i.segments.findIndex((s) => s.id === selectedSegmentId)
              if (index === -1) return i
              const segments = [...i.segments]
              segments.splice(index, 1, first, second)
              return { ...i, segments }
            })
          : prev,
      )
      setSelectedSegmentId(first.id)
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId, selectedSegmentId],
  )

  const handleMergeSegments = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      const merged = await mergeSegments(project.id, selectedItemId, segmentIds)
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => {
              const insertIndex = i.segments.findIndex((s) => segmentIds.includes(s.id))
              const remaining = i.segments.filter((s) => !segmentIds.includes(s.id))
              remaining.splice(insertIndex, 0, merged)
              return { ...i, segments: remaining }
            })
          : prev,
      )
      setSelectedSegmentId(merged.id)
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId],
  )

  const handleFindReplace = useCallback(
    async (field: 'text' | 'translation', find: string, replace: string) => {
      if (!project || !selectedItemId) return
      const updated = await findReplaceSegments(project.id, selectedItemId, field, find, replace)
      setProject((prev) =>
        prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: updated })) : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId],
  )

  const handleBulkDelete = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      await Promise.all(segmentIds.map((id) => deleteSegment(project.id, selectedItemId, id)))
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => ({
              ...i,
              segments: i.segments.filter((s) => !segmentIds.includes(s.id)),
            }))
          : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId],
  )

  const handleBulkMarkReviewed = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      const updates = await Promise.all(
        segmentIds.map((id) => updateSegment(project.id, selectedItemId, id, { reviewed: true })),
      )
      const byId = new Map(updates.map((u) => [u.id, u as Segment]))
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => ({
              ...i,
              segments: i.segments.map((s) => byId.get(s.id) ?? s),
            }))
          : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId],
  )

  const handleUndo = useCallback(async () => {
    if (!project || !selectedItemId || !canUndo) return
    const result = await undoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canUndo])

  const handleRedo = useCallback(async () => {
    if (!project || !selectedItemId || !canRedo) return
    const result = await redoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canRedo])

  const handleResizeSegment = useCallback(
    async (segmentId: string, edge: 'start' | 'end', time: number) => {
      if (!project || !selectedItemId) return
      const updated = await updateSegment(project.id, selectedItemId, segmentId, { [edge]: time })
      handleSegmentSaved(updated as Segment)
    },
    [project, selectedItemId, handleSegmentSaved],
  )

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
    [item, selectedSegmentId, handleSeek],
  )

  // Keyboard shortcuts: space to play/pause, arrows to seek/navigate segments.
  // Ignored while typing in an input/textarea so text editing isn't hijacked.
  useEffect(() => {
    function isEditableTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (isEditableTarget(event.target)) return

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) {
          handleRedo()
        } else {
          handleUndo()
        }
        return
      }

      if (!videoRef.current) return

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
  }, [handleNavigate, handleUndo, handleRedo])

  const handleReviewImported = useCallback((result: ReviewImportResult) => {
    setReviewDiffs(result.diffs)
    setReviewUnknownIds(result.unknown_segment_ids)
  }, [])

  const handleAcceptDiff = useCallback(
    async (diff: ReviewDiffEntry) => {
      if (!project || !selectedItemId) return
      const updated = await updateSegment(project.id, selectedItemId, diff.id, {
        [diff.field]: diff.new_value,
      })
      handleSegmentSaved(updated as Segment)
      setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
    },
    [project, selectedItemId, handleSegmentSaved],
  )

  const handleRejectDiff = useCallback((diff: ReviewDiffEntry) => {
    setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
  }, [])

  const segments = item?.segments ?? []
  const selectedSegment = segments.find((s) => s.id === selectedSegmentId) ?? null
  const selectedIndex = segments.findIndex((s) => s.id === selectedSegmentId)
  const segmentPosition = selectedIndex >= 0 ? `${selectedIndex + 1} / ${segments.length}` : ''
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
        onGlossaryUpdated={handleGlossaryUpdated}
        onReviewImported={handleReviewImported}
        batchModel={batchModel}
        onBatchModelChange={setBatchModel}
      />

      {(activeQueueEntry || transcribeQueue.length > 0) && (
        <p className="hint-text toolbar-warning">
          일괄 전사 진행 중
          {activeQueueEntry &&
            `: ${
              projects
                .find((p) => p.id === activeQueueEntry.projectId)
                ?.items.find((i) => i.id === activeQueueEntry.itemId)?.filename ?? ''
            }`}
          {transcribeQueue.length > 0 && ` (대기 중 ${transcribeQueue.length}개)`}
        </p>
      )}

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

      {project && !item && (
        <p className="empty-hint app-empty-hint">
          이 프로젝트에는 아직 파일이 없습니다. 상단에서 파일을 추가하세요.
        </p>
      )}

      {project && item && (
        <div className="three-column-layout">
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
            canUndo={canUndo}
            canRedo={canRedo}
            onUndo={handleUndo}
            onRedo={handleRedo}
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
      )}
    </div>
  )
}

export default App
