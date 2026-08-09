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
  undoItem,
  updateSegment,
} from './api/client'
import type { MediaItem, Project, ProjectStatus, ReviewDiffEntry, ReviewImportResult, Segment } from './api/types'
import type { Toast } from './components/ProgressToast'
import { ProgressToast } from './components/ProgressToast'
import { SegmentDetailPanel } from './components/SegmentDetailPanel'
import { SegmentList } from './components/SegmentList'
import type { QueuedTask } from './components/TaskQueuePanel'
import { TaskQueuePanel } from './components/TaskQueuePanel'
import { Toolbar } from './components/Toolbar'
import { VideoStage } from './components/VideoStage'

const POLL_INTERVAL_MS = 1500
const ACTIVE_STATUSES = new Set<ProjectStatus>(['transcribing', 'translating', 'rendering'])

type HistoryState = { canUndo: boolean; canRedo: boolean }

function projectLabel(project: Project): string {
  if (project.name) return project.name
  if (project.items[0]) return project.items[0].filename
  return '(이름 없는 프로젝트)'
}

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

  const videoRef = useRef<HTMLVideoElement>(null)
  // Set right before setSelectedProjectId() when we already have the fresh
  // Project object in hand (e.g. one we just created) - tells the effect
  // below to skip its own fetch instead of racing a stale one against it.
  const skipNextProjectFetchRef = useRef<string | null>(null)
  // Set right before setSelectedProjectId() when jumping to a specific item
  // in a *different* project (e.g. from the task queue) - tells the project
  // load effect below which item to select instead of defaulting to the
  // first one.
  const pendingItemIdRef = useRef<string | null>(null)

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
      const wantedItemId = pendingItemIdRef.current
      pendingItemIdRef.current = null
      const resolvedItem =
        (wantedItemId && loaded.items.find((i) => i.id === wantedItemId)) || loaded.items[0]
      setSelectedItemId(resolvedItem?.id ?? null)
      setSelectedSegmentId(resolvedItem?.segments[0]?.id ?? null)
      setReviewDiffs([])
      setReviewUnknownIds([])
      // 새 프로젝트를 불러오면 백엔드 프로세스가 재시작되지 않은 한 서버 히스토리
      // 자체는 남아있을 수 있지만, 프로젝트를 새로 불러왔다는 것은 최신 상태를
      // 신뢰해야 한다는 뜻이므로 세션의 undo/redo 가능 여부 캐시를 초기화합니다.
      setHistoryByItem({})
    })
  }, [selectedProjectId])

  // 프로젝트 전체에서 진행 중(전사/번역/렌더링)인 파일들 - 현재 보고 있는 파일이
  // 아니어도 작업 큐 패널에 표시하고 진행률을 갱신하기 위해 필요합니다.
  const activeTasks: QueuedTask[] = projects.flatMap((p) =>
    p.items
      .filter((i) => ACTIVE_STATUSES.has(i.status))
      .map((i) => ({ projectId: p.id, projectName: projectLabel(p), item: i })),
  )
  const activeTaskKey = activeTasks.map((t) => `${t.projectId}:${t.item.id}`).join(',')

  // 진행 중인 작업이 하나라도 있으면 해당 프로젝트들을 주기적으로 다시 불러와
  // 진행률/완료 여부를 갱신합니다 - 지금 보고 있는 파일이 아니어도 동작합니다.
  useEffect(() => {
    if (activeTasks.length === 0) return
    const projectIds = Array.from(new Set(activeTasks.map((t) => t.projectId)))
    const interval = setInterval(async () => {
      // 한 프로젝트 조회가 실패해도(일시적 오류, 다른 탭에서의 삭제 등) 나머지
      // 활성 프로젝트들의 진행률 갱신까지 함께 누락되지 않도록 개별적으로 처리합니다.
      const results = await Promise.allSettled(projectIds.map((id) => getProject(id)))
      const refreshed = results
        .filter((r): r is PromiseFulfilledResult<Project> => r.status === 'fulfilled')
        .map((r) => r.value)
      if (refreshed.length === 0) return
      setProjects((prev) => prev.map((p) => refreshed.find((r) => r.id === p.id) ?? p))
      setProject((prev) => (prev ? refreshed.find((r) => r.id === prev.id) ?? prev : prev))
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
    // activeTaskKey is a stable summary of activeTasks' identity - re-deriving
    // activeTasks itself every render would restart the interval constantly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTaskKey])

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
      // 업로드만으로는 아무 작업도 자동 시작하지 않습니다 - 각 파일을 선택하고
      // "전사 시작"을 명시적으로 눌러야 처리가 시작됩니다.
    },
    [selectedProjectId],
  )

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
      if (selectedItemId === itemId) {
        const remaining = project.items.filter((i) => i.id !== itemId)
        setSelectedItemId(remaining[0]?.id ?? null)
        setSelectedSegmentId(remaining[0]?.segments[0]?.id ?? null)
      }
    },
    [project, selectedItemId],
  )

  const handleProjectUpdated = useCallback((updated: Project) => {
    setProject((prev) => (prev?.id === updated.id ? updated : prev))
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
    [selectedItemId, setItemHistoryState],
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
    [selectedItemId, selectedSegmentId, setItemHistoryState],
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
    [project, selectedItemId, selectedSegmentId, setItemHistoryState],
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
    [project, selectedItemId, setItemHistoryState],
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
    [project, selectedItemId, setItemHistoryState],
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
    [project, selectedItemId, setItemHistoryState],
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
    [project, selectedItemId, setItemHistoryState],
  )

  const handleUndo = useCallback(async () => {
    if (!project || !selectedItemId || !canUndo) return
    const result = await undoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canUndo, setItemHistoryState])

  const handleRedo = useCallback(async () => {
    if (!project || !selectedItemId || !canRedo) return
    const result = await redoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canRedo, setItemHistoryState])

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

  const handleSelectTask = useCallback(
    (projectId: string, itemId: string) => {
      if (projectId === selectedProjectId) {
        setSelectedItemId(itemId)
        const targetItem = project?.items.find((i) => i.id === itemId)
        setSelectedSegmentId(targetItem?.segments[0]?.id ?? null)
        return
      }
      pendingItemIdRef.current = itemId
      setSelectedProjectId(projectId)
    },
    [selectedProjectId, project],
  )

  const toasts: Toast[] = []
  if (reviewUnknownIds.length > 0) {
    toasts.push({
      id: 'review-unknown-ids',
      tone: 'warning',
      message: `검수 파일에 알 수 없는 세그먼트 ID가 있습니다: ${reviewUnknownIds.join(', ')}`,
      onDismiss: () => setReviewUnknownIds([]),
    })
  }

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
        onGlossaryUpdated={handleProjectUpdated}
        onStyleUpdated={handleProjectUpdated}
        onReviewImported={handleReviewImported}
      />

      <TaskQueuePanel tasks={activeTasks} onSelectTask={handleSelectTask} />
      <ProgressToast toasts={toasts} />

      {!project && (
        <div className="empty-hint app-empty-hint app-empty-hint-onboarding">
          <p className="app-empty-hint-icon" aria-hidden="true">
            🎬
          </p>
          <p>영상이나 오디오 파일을 업로드한 뒤, 파일을 선택하고 "전사 시작"을 눌러주세요.</p>
          <p className="hint-text">상단의 "+ 업로드" 버튼을 누르거나, 파일을 이 창에 끌어다 놓으세요.</p>
        </div>
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
