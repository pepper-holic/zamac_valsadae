import type { MediaItem, ProjectStatus } from '../api/types'
import { formatClock } from '../utils/time'
import { useElapsedSeconds } from '../utils/useElapsedSeconds'

export type QueuedTask = {
  projectId: string
  projectName: string
  item: MediaItem
}

type Props = {
  tasks: QueuedTask[]
  onSelectTask: (projectId: string, itemId: string) => void
}

const STATUS_LABEL: Partial<Record<ProjectStatus, string>> = {
  queued: '대기 중',
  transcribing: '전사 중',
  translating: '번역 중',
  rendering: '렌더링 중',
}

type ChipProps = {
  task: QueuedTask
  onSelect: () => void
}

function TaskQueueChip({ task, onSelect }: ChipProps) {
  const elapsedSeconds = useElapsedSeconds(task.item.started_at)

  return (
    <button
      type="button"
      className="task-queue-chip"
      onClick={onSelect}
      data-tip={`${task.projectName} · ${task.item.filename}`}
    >
      <span className="task-queue-chip-name">{task.item.filename}</span>
      <span className="task-queue-chip-status">{STATUS_LABEL[task.item.status] ?? task.item.status}</span>
      {elapsedSeconds != null && (
        <span className="task-queue-chip-elapsed">{formatClock(elapsedSeconds)}</span>
      )}
      {task.item.progress != null && (
        <span className="task-queue-chip-progress">
          <span
            className="task-queue-chip-progress-fill"
            style={{ width: `${Math.round(task.item.progress * 100)}%` }}
          />
        </span>
      )}
    </button>
  )
}

export function TaskQueuePanel({ tasks, onSelectTask }: Props) {
  if (tasks.length === 0) return null

  return (
    <div className="task-queue-panel" role="status" aria-live="polite">
      <span className="task-queue-label">진행 중인 작업 ({tasks.length})</span>
      <ul className="task-queue-list">
        {tasks.map((task) => (
          <li key={`${task.projectId}:${task.item.id}`}>
            <TaskQueueChip task={task} onSelect={() => onSelectTask(task.projectId, task.item.id)} />
          </li>
        ))}
      </ul>
    </div>
  )
}
