import { useCallback, useState } from 'react'
import { bulkUpdateSegments, updateSegment } from '../api/client'
import type { Project, ReviewDiffEntry, ReviewImportResult, Segment } from '../api/types'
import type { Toast } from '../components/ProgressToast'
import { useErrorToasts } from './useErrorToasts'

export function useReviewDiffs(
  project: Project | null,
  selectedItemId: string | null,
  handleSegmentSaved: (segment: Segment) => void,
  handleSegmentsSaved: (segments: Segment[]) => void,
) {
  const [reviewDiffs, setReviewDiffs] = useState<ReviewDiffEntry[]>([])
  const [reviewUnknownIds, setReviewUnknownIds] = useState<string[]>([])
  const { errorToasts, pushError } = useErrorToasts()

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
      try {
        const updated = await updateSegment(project.id, selectedItemId, diff.id, {
          [diff.field]: diff.new_value,
        })
        handleSegmentSaved(updated)
        setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
      } catch (error) {
        pushError(error)
      }
    },
    [project, selectedItemId, handleSegmentSaved, pushError],
  )

  const handleRejectDiff = useCallback((diff: ReviewDiffEntry) => {
    setReviewDiffs((prev) => prev.filter((entry) => entry !== diff))
  }, [])

  const handleAcceptAllDiffs = useCallback(async () => {
    if (!project || !selectedItemId || reviewDiffs.length === 0) return
    try {
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
      handleSegmentsSaved(updated)
      setReviewDiffs([])
    } catch (error) {
      pushError(error)
    }
  }, [project, selectedItemId, reviewDiffs, handleSegmentsSaved, pushError])

  const handleRejectAllDiffs = useCallback(() => {
    setReviewDiffs([])
  }, [])

  const toasts: Toast[] = [...errorToasts]
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
