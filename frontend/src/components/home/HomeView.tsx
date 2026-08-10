import { useRef, useState } from 'react'
import type { Project } from '../../api/types'
import { ProjectManager } from './ProjectManager'
import './home.css'

type Props = {
  projects: Project[]
  onSelectProject: (projectId: string) => void
  onCreateProject: (name: string) => Promise<void>
  onFilesUploaded: (files: File[]) => Promise<void>
  onProjectDeleted: (projectId: string) => void
}

const FEATURES = [
  { icon: '🎙', title: '전사', body: 'Whisper로 음성을 문장 단위 자막으로 인식합니다.' },
  { icon: '🌐', title: '번역', body: '인식된 문장을 한↔영으로 번역합니다.' },
  { icon: 'Aa', title: '스타일', body: '자막 글꼴/색상/위치를 설정하고 바로 미리봅니다.' },
  { icon: '✓', title: '검수·내보내기', body: 'AI 검수를 반영하고 자막 파일/영상으로 내보냅니다.' },
]

export function HomeView({
  projects,
  onSelectProject,
  onCreateProject,
  onFilesUploaded,
  onProjectDeleted,
}: Props) {
  const [isUploading, setIsUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

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

  function handleNewProject() {
    const name = window.prompt('새 프로젝트 이름 (선택 사항, 비워두면 이름 없이 생성됩니다)')
    if (name === null) return
    onCreateProject(name.trim())
  }

  return (
    <div className="home-view">
      <section className="home-hero">
        <p className="home-hero-icon" aria-hidden="true">🎬</p>
        <h1 className="home-hero-title">Zamak_Valsadae</h1>
        <p className="home-hero-subtitle">
          영상/오디오에서 자막을 뽑고, 번역하고, 검수하고, 자막까지 구운 영상으로 내보내는
          로컬 도구입니다.
        </p>

        <div className="home-hero-actions">
          <label
            className={isDragOver ? 'home-upload-drop drag-over' : 'home-upload-drop'}
            onDragOver={(event) => {
              event.preventDefault()
              setIsDragOver(true)
            }}
            onDragLeave={(event) => {
              event.preventDefault()
              setIsDragOver(false)
            }}
            onDrop={(event) => {
              event.preventDefault()
              setIsDragOver(false)
              const files = event.dataTransfer.files
              if (!files || files.length === 0 || isUploading) return
              uploadFiles(Array.from(files))
            }}
          >
            {isUploading ? '업로드 중...' : '+ 영상/오디오 업로드'}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,audio/*"
              multiple
              hidden
              disabled={isUploading}
              onChange={(event) => {
                const files = event.target.files
                if (files) uploadFiles(Array.from(files))
              }}
            />
          </label>
          <button type="button" className="home-secondary-button" onClick={handleNewProject}>
            + 이름 있는 프로젝트로 시작
          </button>
        </div>
        <p className="home-hint-text">파일을 이 창 어디에나 끌어다 놓아도 됩니다.</p>
      </section>

      <section className="home-features">
        {FEATURES.map((feature) => (
          <div className="home-feature-card" key={feature.title}>
            <span className="home-feature-icon" aria-hidden="true">{feature.icon}</span>
            <b>{feature.title}</b>
            <span>{feature.body}</span>
          </div>
        ))}
      </section>

      <section className="home-projects">
        <h2 className="home-section-title">내 프로젝트</h2>
        <ProjectManager
          projects={projects}
          onSelectProject={onSelectProject}
          onProjectDeleted={onProjectDeleted}
        />
      </section>
    </div>
  )
}
