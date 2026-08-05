import { useEffect, useRef, useState } from 'react'
import type { Project, ReviewImportResult } from '../api/types'
import { deleteProject, uploadProject } from '../api/client'
import { ExportPanel } from './ExportPanel'
import { HelpModal } from './HelpModal'
import { ReviewPanel } from './ReviewPanel'
import { TranscribePanel } from './TranscribePanel'
import { TranslationPanel } from './TranslationPanel'

type MenuKey = 'transcribe' | 'translate' | 'export' | 'review'

function formatStatus(project: Project): string {
  if (
    (project.status === 'transcribing' || project.status === 'translating') &&
    project.progress != null
  ) {
    return `${project.status} ${Math.round(project.progress * 100)}%`
  }
  return project.status
}

type Props = {
  projects: Project[]
  project: Project | null
  selectedProjectId: string | null
  onSelectProject: (projectId: string) => void
  onUploaded: (project: Project) => void
  onProjectUpdated: (project: Project) => void
  onProjectDeleted: (projectId: string) => void
  onReviewImported: (result: ReviewImportResult) => void
}

export function Toolbar({
  projects,
  project,
  selectedProjectId,
  onSelectProject,
  onUploaded,
  onProjectUpdated,
  onProjectDeleted,
  onReviewImported,
}: Props) {
  const [openMenu, setOpenMenu] = useState<MenuKey | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const toolbarRef = useRef<HTMLElement>(null)

  function toggleMenu(key: MenuKey) {
    setOpenMenu((prev) => (prev === key ? null : key))
  }

  useEffect(() => {
    if (!openMenu) return
    function handlePointerDown(event: MouseEvent) {
      if (toolbarRef.current && !toolbarRef.current.contains(event.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [openMenu])

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setIsUploading(true)
    try {
      const created = await uploadProject(file)
      onUploaded(created)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDeleteProject() {
    if (!project) return
    if (!window.confirm(`"${project.filename}" 프로젝트를 삭제할까요? 영상 파일과 자막 데이터가 모두 사라지며 되돌릴 수 없습니다.`)) {
      return
    }
    setIsDeleting(true)
    try {
      await deleteProject(project.id)
      onProjectDeleted(project.id)
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <header className="toolbar" ref={toolbarRef}>
      <div className="toolbar-brand">Zamak_Valsadae</div>

      <div className="toolbar-project-switch">
        <select
          value={selectedProjectId ?? ''}
          onChange={(event) => onSelectProject(event.target.value)}
          data-tip="업로드한 영상/오디오 중 작업할 프로젝트를 선택합니다."
        >
          <option value="" disabled>
            프로젝트 선택
          </option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.filename} ({formatStatus(p)})
            </option>
          ))}
        </select>
        <label
          className="upload-button compact"
          data-tip="새 영상 또는 오디오 파일을 업로드해 프로젝트를 만듭니다."
        >
          {isUploading ? '업로드 중...' : '+ 업로드'}
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*,audio/*"
            onChange={handleFileChange}
            disabled={isUploading}
            hidden
          />
        </label>
        {project && (
          <button
            type="button"
            className="project-delete-button"
            onClick={handleDeleteProject}
            disabled={isDeleting}
            data-tip="현재 선택된 프로젝트를 완전히 삭제합니다 (영상 파일 포함, 되돌릴 수 없음)."
          >
            {isDeleting ? '삭제 중...' : '프로젝트 삭제'}
          </button>
        )}
      </div>

      {project && (
        <div className="toolbar-actions">
          <button
            type="button"
            className={openMenu === 'transcribe' ? 'toolbar-tab active' : 'toolbar-tab'}
            onClick={() => toggleMenu('transcribe')}
            data-tip="Whisper로 음성을 인식해 자막(문장 목록)을 만듭니다."
          >
            전사
          </button>
          <button
            type="button"
            className={openMenu === 'translate' ? 'toolbar-tab active' : 'toolbar-tab'}
            onClick={() => toggleMenu('translate')}
            data-tip="추출된 문장을 한↔영으로 번역합니다."
          >
            번역
          </button>
          <button
            type="button"
            className={openMenu === 'export' ? 'toolbar-tab active' : 'toolbar-tab'}
            onClick={() => toggleMenu('export')}
            data-tip="SRT/VTT/JSON 자막 파일로 내려받습니다."
          >
            내보내기
          </button>
          <button
            type="button"
            className={openMenu === 'review' ? 'toolbar-tab active' : 'toolbar-tab'}
            onClick={() => toggleMenu('review')}
            data-tip="검수용 파일을 내려받아 AI 챗에 올려 교정받고, 결과를 다시 불러옵니다."
          >
            AI 검수
          </button>
        </div>
      )}

      <button
        type="button"
        className="toolbar-help-button"
        onClick={() => setIsHelpOpen(true)}
        data-tip="사용법 가이드를 엽니다."
      >
        ? 도움말
      </button>

      {project && openMenu && (
        <div className="toolbar-dropdown">
          {openMenu === 'transcribe' && (
            <TranscribePanel project={project} onStarted={onProjectUpdated} />
          )}
          {openMenu === 'translate' && (
            <TranslationPanel project={project} onStarted={onProjectUpdated} />
          )}
          {openMenu === 'export' && <ExportPanel project={project} />}
          {openMenu === 'review' && (
            <ReviewPanel project={project} onImported={onReviewImported} />
          )}
        </div>
      )}

      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
    </header>
  )
}
