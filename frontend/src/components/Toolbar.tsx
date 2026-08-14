import { useEffect, useRef, useState } from 'react'
import type { MediaItem, Project, ReviewImportResult } from '../api/types'
import { deleteProject } from '../api/client'
import { useAuth } from '../hooks/useAuth'
import { AboutModal } from './AboutModal'
import { AuthModal } from './AuthModal'
import { ExportPanel } from './ExportPanel'
import { HelpModal } from './HelpModal'
import { ToolbarDropdown } from './ToolbarDropdown'
import { TranscribePanel } from './TranscribePanel'
import { TranslationPanel } from './TranslationPanel'

// 소유 도메인이 정해지면 이 오라클 VM의 nip.io 임시 주소를 교체하세요.
const WEBSITE_URL = 'https://site.168-110-107-78.nip.io'

const IN_PROGRESS_STATUSES = new Set(['transcribing', 'translating', 'rendering'])

type DropdownKey = 'transcribe' | 'translate' | 'export' | 'file-menu' | 'help-menu'

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
  canUndo: boolean
  canRedo: boolean
  onUndo: () => void
  onRedo: () => void
  onGoHome: () => void
  onReviewImported: (result: ReviewImportResult) => void
  reviewDiffCount: number
  onAcceptAllReviewDiffs: () => Promise<void>
  onRejectAllReviewDiffs: () => void
  onGlossaryUpdated: (project: Project) => void
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
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onGoHome,
  onReviewImported,
  reviewDiffCount,
  onAcceptAllReviewDiffs,
  onRejectAllReviewDiffs,
  onGlossaryUpdated,
}: Props) {
  const [openDropdown, setOpenDropdown] = useState<DropdownKey | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [isAboutOpen, setIsAboutOpen] = useState(false)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const { email, isAuthConfigured, signIn, signUp, signOut } = useAuth()
  const [isDeletingProject, setIsDeletingProject] = useState(false)
  const [isDeletingItem, setIsDeletingItem] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const toolbarRef = useRef<HTMLElement>(null)
  const fileMenuTriggerRef = useRef<HTMLButtonElement>(null)
  const helpMenuTriggerRef = useRef<HTMLButtonElement>(null)
  const transcribeTriggerRef = useRef<HTMLButtonElement>(null)
  const translateTriggerRef = useRef<HTMLButtonElement>(null)
  const exportTriggerRef = useRef<HTMLButtonElement>(null)

  const item = project?.items.find((i) => i.id === selectedItemId) ?? null

  useEffect(() => {
    if (!openDropdown) return
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node
      if (toolbarRef.current?.contains(target)) return
      if (target instanceof Element && target.closest('[data-toolbar-portal]')) return
      setOpenDropdown(null)
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [openDropdown])

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
      <div className="toolbar-zone toolbar-zone-brand">
        <button
          type="button"
          className="toolbar-brand-button"
          onClick={onGoHome}
          data-tip="메인 페이지로 돌아갑니다."
          aria-label="메인 페이지로 이동"
        >
          <img className="toolbar-brand-mark" src="/app-icon-glyph.png" alt="" aria-hidden="true" />
        </button>

        <div className="toolbar-menu-wrap">
          <button
            ref={fileMenuTriggerRef}
            type="button"
            className={openDropdown === 'file-menu' ? 'toolbar-menu-trigger active' : 'toolbar-menu-trigger'}
            onClick={() => setOpenDropdown((prev) => (prev === 'file-menu' ? null : 'file-menu'))}
          >
            파일 <span aria-hidden="true">▾</span>
          </button>
          <ToolbarDropdown anchorRef={fileMenuTriggerRef} open={openDropdown === 'file-menu'} className="toolbar-menu">
            <button
              type="button"
              className="toolbar-menu-item"
              onClick={() => {
                setOpenDropdown(null)
                handleNewProject()
              }}
            >
              + 새 프로젝트
            </button>
            {project && (
              <button
                type="button"
                className="toolbar-menu-item danger"
                onClick={() => {
                  setOpenDropdown(null)
                  handleDeleteProject()
                }}
                disabled={isDeletingProject}
              >
                {isDeletingProject ? '삭제 중...' : '프로젝트 삭제'}
              </button>
            )}
            {item && (
              <button
                type="button"
                className="toolbar-menu-item danger"
                onClick={() => {
                  setOpenDropdown(null)
                  handleDeleteItem()
                }}
                disabled={isDeletingItem}
              >
                {isDeletingItem ? '삭제 중...' : '파일 삭제'}
              </button>
            )}
          </ToolbarDropdown>
        </div>

        <div className="toolbar-divider" aria-hidden="true" />
        <select
          className="toolbar-select"
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
      </div>

      {project && (
        <div className="toolbar-zone toolbar-zone-files">
          <div className="toolbar-divider" aria-hidden="true" />
          <select
            className="toolbar-select"
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
            data-tip="새 영상/오디오 파일을 이 프로젝트에 추가합니다. 여러 개를 한 번에 선택하거나 끌어다 놓을 수 있으며, 파일마다 별도로 관리됩니다. 업로드만으로는 전사가 시작되지 않으며, 파일을 선택하고 '전사' 메뉴에서 직접 시작해야 합니다."
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
        </div>
      )}

      {project && item && (
        <div className="toolbar-zone toolbar-zone-workflow">
          <div className="toolbar-divider" aria-hidden="true" />
          <button
            ref={transcribeTriggerRef}
            type="button"
            className={
              openDropdown === 'transcribe'
                ? 'toolbar-ghost-button toolbar-primary-ghost active'
                : 'toolbar-ghost-button toolbar-primary-ghost'
            }
            onClick={() => setOpenDropdown((prev) => (prev === 'transcribe' ? null : 'transcribe'))}
            data-tip="Whisper로 음성을 인식해 문장 목록을 만듭니다."
          >
            🎙 전사
          </button>
          <button
            ref={translateTriggerRef}
            type="button"
            className={
              openDropdown === 'translate'
                ? 'toolbar-ghost-button toolbar-primary-ghost active'
                : 'toolbar-ghost-button toolbar-primary-ghost'
            }
            onClick={() => setOpenDropdown((prev) => (prev === 'translate' ? null : 'translate'))}
            data-tip="추출된 문장을 한↔영으로 번역합니다."
          >
            🌐 번역
          </button>
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

      <div className="toolbar-zone-spacer" />

      {item && (
        <div className="toolbar-history-group">
          <button
            type="button"
            className="toolbar-icon-button"
            onClick={onUndo}
            disabled={!canUndo}
            data-tip="되돌리기 (Ctrl+Z)"
            aria-label="되돌리기"
          >
            ↶
          </button>
          <button
            type="button"
            className="toolbar-icon-button"
            onClick={onRedo}
            disabled={!canRedo}
            data-tip="다시 실행 (Ctrl+Shift+Z)"
            aria-label="다시 실행"
          >
            ↷
          </button>
        </div>
      )}

      {isAuthConfigured && (
        <div className="toolbar-auth-group">
          {email ? (
            <>
              <span className="hint-text" data-tip={email}>
                {email.split('@')[0]}
              </span>
              <button type="button" className="toolbar-ghost-button" onClick={() => void signOut()}>
                로그아웃
              </button>
            </>
          ) : (
            <button
              type="button"
              className="toolbar-ghost-button toolbar-primary-ghost"
              onClick={() => setIsAuthOpen(true)}
              data-tip="로그인하면 서버 제공 번역 엔진을 별도 API 키 없이 쓸 수 있습니다."
            >
              로그인
            </button>
          )}
        </div>
      )}

      <div className="toolbar-menu-wrap">
        <button
          ref={helpMenuTriggerRef}
          type="button"
          className={openDropdown === 'help-menu' ? 'toolbar-menu-trigger active' : 'toolbar-menu-trigger'}
          onClick={() => setOpenDropdown((prev) => (prev === 'help-menu' ? null : 'help-menu'))}
        >
          도움말 <span aria-hidden="true">▾</span>
        </button>
        <ToolbarDropdown
          anchorRef={helpMenuTriggerRef}
          open={openDropdown === 'help-menu'}
          align="right"
          className="toolbar-menu"
        >
          <button
            type="button"
            className="toolbar-menu-item"
            onClick={() => {
              setOpenDropdown(null)
              setIsHelpOpen(true)
            }}
          >
            사용법 가이드
          </button>
          <button
            type="button"
            className="toolbar-menu-item"
            onClick={() => {
              setOpenDropdown(null)
              setIsAboutOpen(true)
            }}
          >
            프로그램 정보
          </button>
          <a
            className="toolbar-menu-item"
            href={WEBSITE_URL}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpenDropdown(null)}
          >
            웹사이트로 이동 ↗
          </a>
        </ToolbarDropdown>
      </div>

      <button
        ref={exportTriggerRef}
        type="button"
        className="toolbar-export-button"
        onClick={() => setOpenDropdown((prev) => (prev === 'export' ? null : 'export'))}
        disabled={!item}
        data-tip={item ? 'SRT/VTT/JSON 자막 파일로 내려받거나 영상을 렌더링합니다.' : '먼저 파일을 선택하세요.'}
      >
        ⭳ 내보내기
      </button>

      {project && item && (
        <ToolbarDropdown anchorRef={transcribeTriggerRef} open={openDropdown === 'transcribe'} className="toolbar-dropdown">
          <TranscribePanel project={project} item={item} onStarted={onItemUpdated} />
        </ToolbarDropdown>
      )}

      {project && item && (
        <ToolbarDropdown anchorRef={translateTriggerRef} open={openDropdown === 'translate'} className="toolbar-dropdown">
          <TranslationPanel
            project={project}
            item={item}
            onStarted={onItemUpdated}
            onGlossaryUpdated={onGlossaryUpdated}
          />
        </ToolbarDropdown>
      )}

      {project && item && (
        <ToolbarDropdown
          anchorRef={exportTriggerRef}
          open={openDropdown === 'export'}
          align="right"
          className="toolbar-dropdown"
        >
          <ExportPanel
            project={project}
            item={item}
            onItemUpdated={onItemUpdated}
            onReviewImported={onReviewImported}
            reviewDiffCount={reviewDiffCount}
            onAcceptAllReviewDiffs={onAcceptAllReviewDiffs}
            onRejectAllReviewDiffs={onRejectAllReviewDiffs}
          />
        </ToolbarDropdown>
      )}

      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
      {isAboutOpen && <AboutModal onClose={() => setIsAboutOpen(false)} />}
      {isAuthOpen && (
        <AuthModal onClose={() => setIsAuthOpen(false)} signIn={signIn} signUp={signUp} />
      )}
    </header>
  )
}
