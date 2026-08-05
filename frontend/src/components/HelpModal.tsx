type Props = {
  onClose: () => void
}

const MODEL_SIZES = [
  { size: 'tiny', speed: '매우 빠름', accuracy: '낮음', note: '빠른 테스트용. 실사용 비권장.' },
  { size: 'base', speed: '빠름', accuracy: '낮음~보통', note: '짧고 명료한 음성엔 쓸만함.' },
  { size: 'small', speed: '보통', accuracy: '보통~좋음', note: '속도/정확도 균형. 기본 권장.' },
  { size: 'medium', speed: '느림', accuracy: '좋음', note: '배경 소음/사투리에 더 강함.' },
  { size: 'large / large-v2 / v3', speed: '매우 느림 (CPU)', accuracy: '최고', note: 'GPU 없으면 영상 길이만큼 오래 걸릴 수 있음.' },
]

export function HelpModal({ onClose }: Props) {
  return (
    <div className="help-overlay" onClick={onClose}>
      <div className="help-modal" onClick={(event) => event.stopPropagation()}>
        <div className="help-header">
          <h2>사용법 가이드</h2>
          <button type="button" className="help-close" onClick={onClose} data-tip="닫기">
            ✕
          </button>
        </div>

        <div className="help-body">
          <section className="help-section">
            <h3>기본 흐름</h3>
            <ol>
              <li>상단 <b>+ 업로드</b>로 영상/오디오 파일을 올립니다.</li>
              <li><b>전사</b> 탭에서 Whisper 모델 크기를 골라 자막을 추출합니다.</li>
              <li><b>번역</b> 탭에서 방향(한→영/영→한)과 엔진을 골라 번역을 붙입니다.</li>
              <li>가운데 문장 목록에서 클릭 → 오른쪽 패널에서 시작/종료 시간, 원문, 번역문을 수정합니다.</li>
              <li><b>내보내기</b>로 SRT/VTT 파일을 받거나, <b>AI 검수</b>로 교정을 받습니다.</li>
            </ol>
          </section>

          <section className="help-section">
            <h3>Whisper 모델 크기별 성능</h3>
            <div className="help-table-wrap">
              <table className="help-table">
                <thead>
                  <tr>
                    <th>모델</th>
                    <th>속도</th>
                    <th>정확도</th>
                    <th>비고</th>
                  </tr>
                </thead>
                <tbody>
                  {MODEL_SIZES.map((row) => (
                    <tr key={row.size}>
                      <td className="mono">{row.size}</td>
                      <td>{row.speed}</td>
                      <td>{row.accuracy}</td>
                      <td>{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="help-hint">GPU가 없다면 <b>small</b>을 기본으로, 인식이 많이 틀리면 <b>medium</b>으로 올려보세요.</p>
          </section>

          <section className="help-section">
            <h3>한/영이 섞인 영상은?</h3>
            <p>
              Whisper는 영상 전체에 언어를 한 번만 감지하므로, 한국어와 영어가 섞이면 일부 구간이 엉뚱하게
              인식될 수 있습니다 (모델 크기가 클수록 덜합니다). 번역 단계에서는 문장별로 이미 목표 언어로
              되어 있으면 자동으로 건너뛰므로, 중간에 섞인 문장을 다시 이상하게 번역하는 일은 방지됩니다.
              전사 결과가 이상한 구간은 가운데 목록에서 직접 원문을 고치거나, 필요 없는 문장은 삭제하세요.
            </p>
          </section>

          <section className="help-section">
            <h3>키보드 단축키</h3>
            <table className="help-table">
              <tbody>
                <tr><td className="mono">Space</td><td>재생 / 일시정지</td></tr>
                <tr><td className="mono">← / →</td><td>1초 뒤로 / 앞으로</td></tr>
                <tr><td className="mono">↑ / ↓</td><td>이전 / 다음 문장으로 이동</td></tr>
              </tbody>
            </table>
          </section>
        </div>
      </div>
    </div>
  )
}
