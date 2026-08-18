import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { RocketLaunch } from '../components/RocketLaunch'
import { useReveal } from '../hooks/useReveal'
import './home.css'

const STEPS = [
  {
    icon: '🎙',
    title: '전사',
    body: 'Whisper로 음성을 문장 단위 자막으로 인식합니다. 처리는 여러분의 PC에서 직접 이뤄져, 여기서부터 모든 단계가 시작됩니다.',
    lead: true,
  },
  {
    icon: '🌐',
    title: '번역',
    body: '인식된 문장을 한↔영으로 번역합니다.',
  },
  {
    icon: 'Aa',
    title: '스타일',
    body: '자막 글꼴·색상·위치를 설정하고 바로 미리봅니다.',
  },
  {
    icon: '✓',
    title: '검수·내보내기',
    body: 'AI 검수를 반영하고 자막 파일 또는 자막까지 구운 영상으로 내보냅니다.',
  },
]

function handleSpotlight(event: MouseEvent<HTMLElement>) {
  const target = event.currentTarget
  const rect = target.getBoundingClientRect()
  target.style.setProperty('--mx', `${((event.clientX - rect.left) / rect.width) * 100}%`)
  target.style.setProperty('--my', `${((event.clientY - rect.top) / rect.height) * 100}%`)
}

export function HomePage() {
  const revealRef = useReveal<HTMLDivElement>()

  return (
    <div className="home-page" ref={revealRef}>
      <section className="home-hero">
        <div className="home-hero-copy" data-reveal>
          <p className="home-hero-eyebrow">
            <span aria-hidden="true">🎬</span> 로컬 우선 자막 도구
          </p>
          <h1 className="home-hero-title">자막발사대</h1>
          <p className="home-hero-subtitle">
            영상·오디오에서 자막을 뽑고, 번역하고, 검수하고, 자막까지 구운 영상으로
            내보내는 도구입니다. 전사는 여러분의 PC에서 직접 처리해 영상을 서버로 올릴
            필요가 없습니다.
          </p>
          <div className="home-hero-actions">
            <Link to="/download" className="home-primary-button">
              지금 다운로드
            </Link>
            <Link to="/pricing" className="home-secondary-button">
              가격 정책 보기
            </Link>
          </div>
        </div>

        <div className="home-hero-visual" data-reveal aria-hidden="true">
          <div className="home-mock-window">
            <div className="home-mock-titlebar">
              <span />
              <span />
              <span />
            </div>
            <div className="home-mock-frame">
              <RocketLaunch />
              <div className="home-mock-caption">지금, 자막이 발사됩니다</div>
            </div>
            <div className="home-mock-row">
              <span className="home-mock-chip">KO → EN</span>
              <span className="home-mock-chip ok">AI 검수 완료</span>
            </div>
          </div>
        </div>
      </section>

      <section className="home-steps" aria-label="처리 단계">
        {STEPS.map((step, index) => (
          <div
            className={step.lead ? 'home-step home-step-lead' : 'home-step'}
            key={step.title}
            data-reveal
            onMouseMove={handleSpotlight}
          >
            <div className="home-step-index" aria-hidden="true">
              {String(index + 1).padStart(2, '0')}
            </div>
            <div className="home-step-body">
              <span className="home-step-icon" aria-hidden="true">
                {step.icon}
              </span>
              <b>{step.title}</b>
              <span>{step.body}</span>
            </div>
          </div>
        ))}
      </section>

      <section className="home-note" data-reveal>
        <h2>왜 전사는 로컬에서 처리하나요?</h2>
        <p>
          음성 인식(Whisper)은 무거운 연산이라 서버에 올리려면 영상 파일 자체를 업로드해야
          합니다. 자막발사대는 이 과정을 사용자의 PC에서 직접 처리해 대역폭과 대기 시간을
          줄이고, 영상이 외부로 나가지 않아도 되게 합니다. 번역과 AI 검수처럼 계정·과금이 걸린
          기능만 서버를 거칩니다.
        </p>
      </section>
    </div>
  )
}
