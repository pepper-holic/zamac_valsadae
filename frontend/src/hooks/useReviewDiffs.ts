import { useCallback, useState } from 'react'
import { bulkUpdateSegments, updateSegment } from '../api/client'
import type { Project, ReviewDiffEntry, ReviewImportResult, Segment } from '../api/types'
import type { Toast } from '../components/ProgressToast'

export function useReviewDiffs(
  project: Project | null,
  selectedItemId: string | null,
  handleSegmentSaved: (segment: Segment) => void,
) {
  const [reviewDiffs, setReviewDiffs] = useState<ReviewDiffEntry[]>([])
  const [reviewUnknownIds, setReviewUnknownIds] = useState<string[]>([])

  const resetReview = useCallback(() => {
    setReviewDiffs([])
    setReviewUnknownIds([])
  }, [])

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

  const handleAcceptAllDiffs = useCallback(async () => {
    if (!project || !selectedItemId || reviewDiffs.length === 0) return
    // Merge diffs per segment (a segment can have both a text and a
    // translation diff) and send it as one request, so the backend records
    // the whole batch as a single undo step instead of one per diff.
    const changesById = new Map<string, Record<string, unknown>>()
    for (const diff of reviewDiffs) {
      const existing = changesById.get(diff.id) ?? {}
      existing[diff.field] = diff.new_value
      changesById.set(diff.id, existing)
    }
    const updates = [...changesById.entries()].map(([id, update]) => ({ id, update }))
    const updated = await bulkUpdateSegments(project.id, selectedItemId, updates)
    updated.forEach(handleSegmentSaved)
    setReviewDiffs([])
  }, [project, selectedItemId, reviewDiffs, handleSegmentSaved])

  const handleRejectAllDiffs = useCallback(() => {
    setReviewDiffs([])
  }, [])

  const toasts: Toast[] = []
  if (reviewUnknownIds.length > 0) {
    toasts.push({
      id: 'review-unknown-ids',
      tone: 'warning',
      message: `검수 파일에 알 수 없는 세그먼트 ID가 있습니다: ${reviewUnknownIds.join(', ')}`,
      onDismiss: () => setReviewUnknownIds([]),
    })
  }

  return {
    reviewDiffs,
    resetReview,
    handleReviewImported,
    handleAcceptDiff,
    handleRejectDiff,
    handleAcceptAllDiffs,
    handleRejectAllDiffs,
    toasts,
  }
}
