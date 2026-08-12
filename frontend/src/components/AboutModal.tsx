// 소유 도메인이 정해지면 이 오라클 VM의 nip.io 임시 주소를 교체하세요.
const WEBSITE_URL = 'https://site.168-110-107-78.nip.io'
const ISSUES_URL = 'https://github.com/pepper-holic/zamac_valsadae/issues'

type Props = {
  onClose: () => void
}

export function AboutModal({ onClose }: Props) {
  return (
    <div className="help-overlay" onClick={onClose}>
      <div className="help-modal" onClick={(event) => event.stopPropagation()}>
        <div className="help-header">
          <h2>프로그램 정보</h2>
          <button type="button" className="help-close" onClick={onClose} data-tip="닫기">
            ✕
          </button>
        </div>

        <div className="help-body">
          <section className="help-section">
            <h3>자막발사대</h3>
            <p>
              영상/오디오에서 자막을 뽑고, 번역하고, 검수하고, 자막까지 구운 영상으로
              내보내는 로컬 도구입니다. 전사는 이 PC에서 직접 처리되며, 업로드한 파일과
              결과물은 서버로 전송되지 않고 <code>data/</code> 폴더에만 저장됩니다.
            </p>
          </section>

          <section className="help-section">
            <h3>링크</h3>
            <p>
              <a href={WEBSITE_URL} target="_blank" rel="noopener noreferrer">
                서비스 웹사이트 (소개 · 다운로드 · 가격 정책 · 이용약관 등)
              </a>
            </p>
            <p>
              <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">
                버그 리포트 / 기능 요청 (GitHub Issues)
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
