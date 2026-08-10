import { useCallback, useState } from 'react'
import { updateSegment } from '../api/client'
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
    toasts,
  }
}
