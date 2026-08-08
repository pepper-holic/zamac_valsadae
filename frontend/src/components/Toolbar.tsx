import { useEffect, useRef, useState } from 'react'
import type { MediaItem, Project, ReviewImportResult } from '../api/types'
import { WHISPER_MODELS } from '../api/types'
import { deleteProject } from '../api/client'
import { ExportPanel } from './ExportPanel'
import { HelpModal } from './HelpModal'
import { ReviewPanel } from './ReviewPanel'
import { SubtitleStylePanel } from './SubtitleStylePanel'
import { TranscribePanel } from './TranscribePanel'
import { TranslationPanel } from './TranslationPanel'

type MenuKey = 'transcribe' | 'translate' | 'style' | 'export' | 'review'

const IN_PROGRESS_STATUSES = new Set(['transcribing', 'translating', 'rendering'])

function formatItemStatus(item: MediaItem): string {
  if (IN_PROGRESS_STATUSES.has(item.status) && item.progress != null) {
    return `${item.status} ${Math.round(item.progress * 100)}%`
  }
  return item.status
}

function projectLabel(project: Project): string {
  if (project.name) return project.name
  if (project.items[0]) return project.items[0].filename
  return '(이름 없는 프로젝트)'
}

type Props = {
  projects: Project[]
  project: Project | null
  selectedProjectId: string | null
  onSelectProject: (projectId: string) => void
  onCreateProject: (name: string) => Promise<void>
  onFilesUploaded: (files: File[]) => Promise<void>
  selectedItemId: string | null
  onSelectItem: (itemId: string) => void
  onItemUpdated: (item: MediaItem) => void
  onItemDeleted: (itemId: string) => Promise<void>
  onProjectDeleted: (projectId: string) => void
  onGlossaryUpdated: (project: Project) => void
  onStyleUpdated: (project: Project) => void
  onReviewImported: (result: ReviewImportResult) => void
  batchModel: string
  onBatchModelChange: (model: string) => void
}

export function Toolbar({
  projects,
  project,
  selectedProjectId,
  onSelectProject,
  onCreateProject,
  onFilesUploaded,
  selectedItemId,
  onSelectItem,
  onItemUpdated,
  onItemDeleted,
  onProjectDeleted,
  onGlossaryUpdated,
  onStyleUpdated,
  onReviewImported,
  batchModel,
  onBatchModelChange,
}: Props) {
  const [openMenu, setOpenMenu] = useState<MenuKey | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [isDeletingProject, setIsDeletingProject] = useState(false)
  const [isDeletingItem, setIsDeletingItem] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const toolbarRef = useRef<HTMLElement>(null)

  const item = project?.items.find((i) => i.id === selectedItemId) ?? null

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

  async function uploadFiles(files: File[]) {
    if (files.length === 0) return
    setIsUploading(true)
    try {
      await onFilesUploaded(files)
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (!files) return
    await uploadFiles(Array.from(files))
  }

  function handleDragOver(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragOver(true)
  }

  function handleDragLeave(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragOver(false)
  }

  async function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragOver(false)
    const files = event.dataTransfer.files
    if (!files || files.length === 0 || isUploading) return
    await uploadFiles(Array.from(files))
  }

  function handleNewProject() {
    const name = window.prompt('새 프로젝트 이름 (선택 사항, 비워두면 이름 없이 생성됩니다)')
    if (name === null) return
    onCreateProject(name.trim())
  }

  async function handleDeleteProject() {
    if (!project) return
    if (
      !window.confirm(
        `"${projectLabel(project)}" 프로젝트를 삭제할까요? 안에 있는 파일 ${project.items.length}개와 모든 자막 데이터가 사라지며 되돌릴 수 없습니다.`,
      )
    ) {
      return
    }
    setIsDeletingProject(true)
    try {
      await deleteProject(project.id)
      onProjectDeleted(project.id)
    } finally {
      setIsDeletingProject(false)
    }
  }

  async function handleDeleteItem() {
    if (!item) return
    if (!window.confirm(`"${item.filename}" 파일을 프로젝트에서 삭제할까요? 되돌릴 수 없습니다.`)) return
    setIsDeletingItem(true)
    try {
      await onItemDeleted(item.id)
    } finally {
      setIsDeletingItem(false)
    }
  }

  return (
    <header className="toolbar" ref={toolbarRef}>
      <div className="toolbar-brand">Zamak_Valsadae</div>

      <div className="toolbar-project-switch">
        <select
          value={selectedProjectId ?? ''}
          onChange={(event) => onSelectProject(event.target.value)}
          data-tip="여러 파일을 묶어 관리하는 프로젝트를 선택합니다."
        >
          <option value="" disabled>
            프로젝트 선택
          </option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {projectLabel(p)} ({p.items.length}개 파일)
            </option>
          ))}
        </select>
        <button
          type="button"
          className="secondary"
          onClick={handleNewProject}
          data-tip="파일 여러 개를 묶어 관리할 새 프로젝트를 만듭니다."
        >
          + 새 프로젝트
        </button>
        {project && (
          <button
            type="button"
            className="project-delete-button"
            onClick={handleDeleteProject}
            disabled={isDeletingProject}
            data-tip="현재 선택된 프로젝트를 통째로 삭제합니다 (안의 모든 파일 포함, 되돌릴 수 없음)."
          >
            {isDeletingProject ? '삭제 중...' : '프로젝트 삭제'}
          </button>
        )}
      </div>

      {project && (
        <div className="toolbar-project-switch">
          <select
            value={selectedItemId ?? ''}
            onChange={(event) => onSelectItem(event.target.value)}
            data-tip="이 프로젝트 안의 파일 중 작업할 파일을 선택합니다."
          >
            <option value="" disabled>
              파일 선택
            </option>
            {project.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.filename} ({formatItemStatus(i)})
              </option>
            ))}
          </select>
          <label
            className={isDragOver ? 'upload-button compact drag-over' : 'upload-button compact'}
            data-tip="새 영상/오디오 파일을 이 프로젝트에 추가합니다. 여러 개를 한 번에 선택하거나 끌어다 놓으면 파일마다 별도로 관리되며 순서대로 자동 전사됩니다. 프로젝트를 선택하지 않은 상태면 새 프로젝트를 만들어 추가합니다."
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            {isUploading ? '업로드 중...' : '+ 파일 추가'}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,audio/*"
              multiple
              onChange={handleFileChange}
              disabled={isUploading}
              hidden
            />
          </label>
          <select
            value={batchModel}
            onChange={(event) => onBatchModelChange(event.target.value)}
            data-tip="여러 파일을 한 번에 올렸을 때 자동 전사에 사용할 Whisper 모델 크기입니다."
          >
            {WHISPER_MODELS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
          {item && (
            <button
              type="button"
              className="project-delete-button"
              onClick={handleDeleteItem}
              disabled={isDeletingItem}
              data-tip="현재 선택된 파일만 프로젝트에서 삭제합니다 (되돌릴 수 없음)."
            >
              {isDeletingItem ? '삭제 중...' : '파일 삭제'}
            </button>
          )}
        </div>
      )}

      {!project && (
        <label
          className={isDragOver ? 'upload-button compact drag-over' : 'upload-button compact'}
          data-tip="새 영상/오디오 파일을 업로드하면 새 프로젝트가 자동으로 만들어집니다. 여러 개를 한 번에 올려도 됩니다."
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {isUploading ? '업로드 중...' : '+ 업로드'}
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*,audio/*"
            multiple
            onChange={handleFileChange}
            disabled={isUploading}
            hidden
          />
        </label>
      )}

      {item && (
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
            className={openMenu === 'style' ? 'toolbar-tab active' : 'toolbar-tab'}
            onClick={() => toggleMenu('style')}
            data-tip="자막의 글꼴/색상/위치/효과를 설정하고 미리보기에 바로 반영합니다."
          >
            자막 스타일
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

      {project && item && openMenu && (
        <div className="toolbar-dropdown">
          {openMenu === 'transcribe' && (
            <TranscribePanel project={project} item={item} onStarted={onItemUpdated} />
          )}
          {openMenu === 'translate' && (
            <TranslationPanel
              project={project}
              item={item}
              onStarted={onItemUpdated}
              onGlossaryUpdated={onGlossaryUpdated}
            />
          )}
          {openMenu === 'style' && (
            <SubtitleStylePanel project={project} onStyleUpdated={onStyleUpdated} />
          )}
          {openMenu === 'export' && (
            <ExportPanel project={project} item={item} onItemUpdated={onItemUpdated} />
          )}
          {openMenu === 'review' && (
            <ReviewPanel project={project} item={item} onImported={onReviewImported} />
          )}
        </div>
      )}

      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
    </header>
  )
}
