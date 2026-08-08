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
              <li>상단 <b>+ 업로드</b>로 영상/오디오 파일을 올립니다. 여러 개를 한 번에 올리면 새 프로젝트 하나에 파일마다 별도로 담겨 관리됩니다.</li>
              <li>같은 시리즈의 다른 영상을 추가하려면, 프로젝트를 선택한 상태에서 <b>+ 파일 추가</b>를 누르세요. 파일 선택 드롭다운에서 작업할 파일을 전환할 수 있습니다.</li>
              <li><b>전사</b> 탭에서 Whisper 모델 크기를 골라 자막을 추출합니다. (여러 파일을 한 번에 올렸다면 자동으로 순서대로 전사됩니다.)</li>
              <li><b>번역</b> 탭에서 방향(한→영/영→한)과 엔진을 골라 번역을 붙입니다. 용어집은 프로젝트 안의 모든 파일이 함께 씁니다.</li>
              <li>가운데 문장 목록에서 클릭 → 오른쪽 패널에서 시작/종료 시간, 원문, 번역문을 수정합니다.</li>
              <li><b>내보내기</b>로 SRT/VTT 파일을 받거나, <b>AI 검수</b>로 교정을 받습니다. (현재 선택한 파일 기준입니다.)</li>
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
            <h3>추가 기능</h3>
            <table className="help-table">
              <tbody>
                <tr>
                  <td className="mono">화자 분리</td>
                  <td>
                    전사 탭의 &quot;화자 분리&quot; 체크박스. 누가 말했는지 문장마다 라벨(SPEAKER_00 등)을
                    붙입니다. HuggingFace 토큰(HF_TOKEN) 설정과 최초 1회 모델 다운로드가 필요하며, 처리
                    시간이 더 걸립니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">가독성 검사</td>
                  <td>
                    전사/번역 후 자동으로 계산됩니다. 초당 글자 수(CPS)가 너무 빠르거나, 한 줄이 너무 길거나,
                    자막이 너무 짧게/길게 떠 있으면 문장 목록에 ⚠ 표시가 붙습니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">용어집</td>
                  <td>
                    번역 탭 하단에서 원문 용어 → 지정 번역 쌍을 등록합니다. 등록한 용어는 번역 결과에서
                    항상 지정한 번역으로 치환됩니다(원문이 그대로 남아있는 경우에 한한 best-effort).
                  </td>
                </tr>
                <tr>
                  <td className="mono">번역 메모리</td>
                  <td>
                    같은 프로젝트에서 동일한 원문 문장을 다시 번역하면, 모델을 다시 호출하지 않고 이전
                    번역을 재사용합니다. 별도 조작 없이 자동으로 동작합니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">ASS / TTML 내보내기</td>
                  <td>
                    내보내기 탭의 형식 선택에서 SRT/VTT/JSON 외에 ASS(스타일링 자막), TTML(방송/OTT 표준
                    포맷)도 선택할 수 있습니다.
                  </td>
                </tr>
              </tbody>
            </table>
          </section>

          <section className="help-section">
            <h3>편집 편의 기능</h3>
            <table className="help-table">
              <tbody>
                <tr>
                  <td className="mono">분할</td>
                  <td>
                    상세 검수 패널에서 재생 위치를 문장 중간에 두고 &quot;현재 위치에서 분할&quot;을
                    누르면 그 지점을 기준으로 문장이 둘로 나뉩니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">병합</td>
                  <td>
                    문장 목록에서 체크박스로 2개 이상 선택하면 나오는 &quot;병합&quot; 버튼으로 시간
                    순서대로 하나의 문장으로 합칩니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">찾기/바꾸기</td>
                  <td>
                    문장 목록 상단에서 원문 또는 번역 전체를 대상으로 텍스트를 한 번에 찾아 바꿉니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">일괄 작업</td>
                  <td>문장을 여러 개 체크하면 검토완료 표시/삭제를 한 번에 적용할 수 있습니다.</td>
                </tr>
                <tr>
                  <td className="mono">타임라인 드래그</td>
                  <td>
                    영상 아래 타임라인의 문장 막대 양 끝을 드래그하면 시작/종료 시간을 직접 조절할 수
                    있습니다. 오디오를 디코딩할 수 있으면 파형도 함께 표시됩니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">자막 미리보기</td>
                  <td>재생 중 현재 문장의 원문/번역이 영상 위에 자막처럼 겹쳐 보입니다.</td>
                </tr>
                <tr>
                  <td className="mono">드래그 업로드</td>
                  <td>파일을 상단 &quot;+ 업로드&quot; 버튼 위로 끌어다 놓아도 업로드됩니다.</td>
                </tr>
                <tr>
                  <td className="mono">일괄 업로드</td>
                  <td>
                    파일을 여러 개 한 번에 선택하거나 끌어다 놓으면 같은 프로젝트 안에 파일마다 따로
                    담겨 관리되면서, 업로드 버튼 옆에서 고른 모델로 순서대로 자동 전사합니다. 화면
                    상단에 진행 상황이 표시됩니다.
                  </td>
                </tr>
              </tbody>
            </table>
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
