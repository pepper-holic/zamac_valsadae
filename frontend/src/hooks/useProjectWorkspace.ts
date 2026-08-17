import { useCallback, useEffect, useRef, useState } from 'react'
import { addItem, createProject, deleteItem, getProject, getProjectStatus, listProjects } from '../api/client'
import type { MediaItem, Project, ProjectStatus, ProjectStatusSummary } from '../api/types'
import type { QueuedTask } from '../components/TaskQueuePanel'
import { projectLabel, updateItemInProject } from '../utils/projectHelpers'

const POLL_INTERVAL_MS = 1500
const ACTIVE_STATUSES = new Set<ProjectStatus>(['queued', 'transcribing', 'translating', 'rendering'])

export function useProjectWorkspace(onProjectLoaded: () => void) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null)

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
      onProjectLoaded()
    })
    // onProjectLoaded is a stable reset callback from the caller - including it
    // would re-run this effect every render since the caller can't easily
    // memoize a callback that closes over other hooks' setters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
  //
  // 매 틱마다 프로젝트 전체(세그먼트/단어 포함)를 다시 받아오는 대신, 상태
  // 값만 담긴 가벼운 엔드포인트를 폴링합니다 - 자막이 많은 파일일수록 매번
  // 수백 KB~1MB를 다시 파싱/전송하는 낭비가 커지고, 그때마다 세그먼트 배열의
  // identity가 바뀌면서 화면 전체가 다시 렌더링됩니다. 실제 세그먼트 결과가
  // 필요한 시점(전사/번역/렌더링이 막 끝난 시점)에만 해당 프로젝트를 한 번
  // 전체로 다시 불러옵니다.
  useEffect(() => {
    if (activeTasks.length === 0) return
    const projectIds = Array.from(new Set(activeTasks.map((t) => t.projectId)))
    // Snapshot of which items were active when this interval was set up -
    // used below to detect a status transition purely from the poll
    // response, without reading back potentially-stale React state inside
    // the interval callback (a setState functional updater isn't guaranteed
    // to run synchronously, so a "did it change" flag set as a side effect
    // inside one couldn't be read reliably right after).
    const trackedItemIds = new Set(activeTasks.map((t) => t.item.id))
    const interval = setInterval(async () => {
      // 한 프로젝트 조회가 실패해도(일시적 오류, 다른 탭에서의 삭제 등) 나머지
      // 활성 프로젝트들의 진행률 갱신까지 함께 누락되지 않도록 개별적으로 처리합니다.
      const results = await Promise.allSettled(projectIds.map((id) => getProjectStatus(id)))
      const statuses = results
        .filter((r): r is PromiseFulfilledResult<ProjectStatusSummary> => r.status === 'fulfilled')
        .map((r) => r.value)
      if (statuses.length === 0) return

      const needsFullRefetch = new Set<string>()
      for (const summary of statuses) {
        for (const status of summary.items) {
          if (trackedItemIds.has(status.id) && !ACTIVE_STATUSES.has(status.status)) {
            // 전사/번역/렌더링이 막 끝났거나 실패함 - 실제 결과(세그먼트)를
            // 반영하려면 이 프로젝트는 한 번 전체로 다시 불러와야 합니다.
            needsFullRefetch.add(summary.id)
          }
        }
      }

      const mergeStatus = (p: Project): Project => {
        const summary = statuses.find((s) => s.id === p.id)
        if (!summary) return p
        let changed = false
        const items = p.items.map((item) => {
          const status = summary.items.find((s) => s.id === item.id)
          if (!status) return item
          if (
            item.status === status.status &&
            item.progress === status.progress &&
            item.stage === status.stage &&
            item.error === status.error &&
            item.started_at === status.started_at
          ) {
            return item
          }
          changed = true
          return { ...item, ...status }
        })
        return changed ? { ...p, items } : p
      }

      setProjects((prev) => prev.map(mergeStatus))
      setProject((prev) => (prev ? mergeStatus(prev) : prev))

      if (needsFullRefetch.size === 0) return
      const fullResults = await Promise.allSettled(
        Array.from(needsFullRefetch).map((id) => getProject(id)),
      )
      const refreshed = fullResults
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

  return {
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
  }
}
