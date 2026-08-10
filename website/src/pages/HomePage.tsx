import { Link } from 'react-router-dom'
import './home.css'

const FEATURES = [
  { icon: '🎙', title: '전사', body: 'Whisper로 음성을 문장 단위 자막으로 인식합니다.' },
  { icon: '🌐', title: '번역', body: '인식된 문장을 한↔영으로 번역합니다.' },
  { icon: 'Aa', title: '스타일', body: '자막 글꼴/색상/위치를 설정하고 바로 미리봅니다.' },
  { icon: '✓', title: '검수·내보내기', body: 'AI 검수를 반영하고 자막 파일/영상으로 내보냅니다.' },
]

export function HomePage() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <p className="home-hero-icon" aria-hidden="true">🎬</p>
        <h1 className="home-hero-title">Zamak_Valsadae</h1>
        <p className="home-hero-subtitle">
          영상/오디오에서 자막을 뽑고, 번역하고, 검수하고, 자막까지 구운 영상으로 내보내는
          도구입니다. 전사는 여러분의 PC에서 직접 처리해 영상을 서버로 올릴 필요가 없습니다.
        </p>
        <div className="home-hero-actions">
          <Link to="/download" className="home-primary-button">
            지금 다운로드
          </Link>
          <Link to="/pricing" className="home-secondary-button">
            가격 정책 보기
          </Link>
        </div>
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

      <section className="home-note">
        <h2>왜 전사는 로컬에서 처리하나요?</h2>
        <p>
          음성 인식(Whisper)은 무거운 연산이라 서버에 올리려면 영상 파일 자체를 업로드해야
          합니다. Zamak_Valsadae는 이 과정을 사용자의 PC에서 직접 처리해 대역폭과 대기 시간을
          줄이고, 영상이 외부로 나가지 않아도 되게 합니다. 번역과 AI 검수처럼 계정/과금이 걸린
          기능만 서버를 거칩니다.
        </p>
      </section>
    </div>
  )
}
