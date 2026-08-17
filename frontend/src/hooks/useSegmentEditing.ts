import { useCallback, useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import {
  bulkDeleteSegments,
  bulkUpdateSegments,
  findReplaceSegments,
  mergeSegments,
  splitSegment,
  undoItem,
  redoItem,
  updateSegment,
} from '../api/client'
import type { Project, Segment } from '../api/types'
import { updateItemInProject } from '../utils/projectHelpers'

type HistoryState = { canUndo: boolean; canRedo: boolean }

export function useSegmentEditing(
  project: Project | null,
  setProject: Dispatch<SetStateAction<Project | null>>,
  selectedItemId: string | null,
  selectedSegmentId: string | null,
  setSelectedSegmentId: Dispatch<SetStateAction<string | null>>,
) {
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

  const resetHistory = useCallback(() => setHistoryByItem({}), [])

  // Applies any number of updated segments in a single setProject call -
  // used directly for batch operations (e.g. accepting a whole AI-review
  // diff package) instead of calling handleSegmentSaved once per segment,
  // which would do one O(segments) array scan *and* one re-render per
  // segment instead of one of each for the whole batch.
  const handleSegmentsSaved = useCallback(
    (segments: Segment[]) => {
      if (!selectedItemId || segments.length === 0) return
      const bySegmentId = new Map(segments.map((segment) => [segment.id, segment]))
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => ({
              ...i,
              segments: i.segments.map((s) => bySegmentId.get(s.id) ?? s),
            }))
          : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [selectedItemId, setProject, setItemHistoryState],
  )

  const handleSegmentSaved = useCallback(
    (segment: Segment) => handleSegmentsSaved([segment]),
    [handleSegmentsSaved],
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
    [selectedItemId, selectedSegmentId, setProject, setSelectedSegmentId, setItemHistoryState],
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
    [project, selectedItemId, selectedSegmentId, setProject, setSelectedSegmentId, setItemHistoryState],
  )

  const handleMergeSegments = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      const merged = await mergeSegments(project.id, selectedItemId, segmentIds)
      setProject((prev) =>
        prev
          ? updateItemInProject(prev, selectedItemId, (i) => {
              const idsToMerge = new Set(segmentIds)
              const insertIndex = i.segments.findIndex((s) => idsToMerge.has(s.id))
              const remaining = i.segments.filter((s) => !idsToMerge.has(s.id))
              remaining.splice(insertIndex, 0, merged)
              return { ...i, segments: remaining }
            })
          : prev,
      )
      setSelectedSegmentId(merged.id)
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId, setProject, setSelectedSegmentId, setItemHistoryState],
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
    [project, selectedItemId, setProject, setItemHistoryState],
  )

  const handleBulkDelete = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      // One request for the whole batch (not N concurrent calls) so the
      // backend records it as a single undo step and there's no read-modify-
      // write race between segments landing at once.
      const remaining = await bulkDeleteSegments(project.id, selectedItemId, segmentIds)
      setProject((prev) =>
        prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: remaining })) : prev,
      )
      setItemHistoryState(selectedItemId, { canUndo: true, canRedo: false })
    },
    [project, selectedItemId, setProject, setItemHistoryState],
  )

  const handleBulkMarkReviewed = useCallback(
    async (segmentIds: string[]) => {
      if (!project || !selectedItemId) return
      const updates = await bulkUpdateSegments(
        project.id,
        selectedItemId,
        segmentIds.map((id) => ({ id, update: { reviewed: true } })),
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
    [project, selectedItemId, setProject, setItemHistoryState],
  )

  const handleUndo = useCallback(async () => {
    if (!project || !selectedItemId || !canUndo) return
    const result = await undoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canUndo, setProject, setItemHistoryState])

  const handleRedo = useCallback(async () => {
    if (!project || !selectedItemId || !canRedo) return
    const result = await redoItem(project.id, selectedItemId)
    setProject((prev) =>
      prev ? updateItemInProject(prev, selectedItemId, (i) => ({ ...i, segments: result.segments })) : prev,
    )
    setItemHistoryState(selectedItemId, { canUndo: result.can_undo, canRedo: result.can_redo })
  }, [project, selectedItemId, canRedo, setProject, setItemHistoryState])

  const handleResizeSegment = useCallback(
    async (segmentId: string, edge: 'start' | 'end', time: number) => {
      if (!project || !selectedItemId) return
      const updated = await updateSegment(project.id, selectedItemId, segmentId, { [edge]: time })
      handleSegmentSaved(updated as Segment)
    },
    [project, selectedItemId, handleSegmentSaved],
  )

  return {
    canUndo,
    canRedo,
    resetHistory,
    handleSegmentSaved,
    handleSegmentsSaved,
    handleSegmentDeleted,
    handleSplitSegment,
    handleMergeSegments,
    handleFindReplace,
    handleBulkDelete,
    handleBulkMarkReviewed,
    handleUndo,
    handleRedo,
    handleResizeSegment,
  }
}
