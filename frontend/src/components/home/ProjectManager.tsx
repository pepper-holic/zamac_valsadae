import { useState } from 'react'
import type { Project } from '../../api/types'
import { deleteProject } from '../../api/client'

type Props = {
  projects: Project[]
  onSelectProject: (projectId: string) => void
  onProjectDeleted: (projectId: string) => void
}

function projectLabel(project: Project): string {
  if (project.name) return project.name
  if (project.items[0]) return project.items[0].filename
  return '(이름 없는 프로젝트)'
}

export function ProjectManager({ projects, onSelectProject, onProjectDeleted }: Props) {
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  async function handleDelete(project: Project) {
    if (
      !window.confirm(
        `"${projectLabel(project)}" 프로젝트를 삭제할까요? 안에 있는 파일 ${project.items.length}개와 모든 자막 데이터가 사라지며 되돌릴 수 없습니다.`,
      )
    ) {
      return
    }
    setDeletingId(project.id)
    setDeleteError(null)
    try {
      await deleteProject(project.id)
      onProjectDeleted(project.id)
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : String(error))
    } finally {
      setDeletingId(null)
    }
  }

  if (projects.length === 0) {
    return (
      <p className="home-projects-empty">
        아직 프로젝트가 없습니다. 아래에서 파일을 업로드하면 첫 프로젝트가 자동으로 만들어집니다.
      </p>
    )
  }

  return (
    <>
      {deleteError && <p className="error-text">{deleteError}</p>}
      <ul className="home-project-list">
        {projects.map((project) => (
          <li key={project.id} className="home-project-card">
            <button
              type="button"
              className="home-project-card-main"
              onClick={() => onSelectProject(project.id)}
            >
              <span className="home-project-name">{projectLabel(project)}</span>
              <span className="home-project-meta">
                파일 {project.items.length}개
                {project.items.length > 0 && (
                  <>
                    {' · '}
                    {project.items.filter((i) => i.status === 'rendered' || i.status === 'translated').length}개 완료
                  </>
                )}
              </span>
            </button>
            <button
              type="button"
              className="home-project-delete"
              onClick={() => handleDelete(project)}
              disabled={deletingId === project.id}
              data-tip="이 프로젝트를 삭제합니다 (되돌릴 수 없음)."
            >
              {deletingId === project.id ? '삭제 중...' : '삭제'}
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}
