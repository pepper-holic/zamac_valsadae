import { createPortal } from 'react-dom'

type Props = {
  onClose: () => void
}

const MODEL_SIZES = [
  { size: 'tiny', speed: '매우 빠름', accuracy: '낮음', note: '빠른 테스트용. 실사용 비권장.' },
  { size: 'base', speed: '빠름', accuracy: '낮음~보통', note: '짧고 명료한 음성엔 쓸만함.' },
  { size: 'small', speed: '보통', accuracy: '보통~좋음', note: '속도/정확도 균형. 기본 권장.' },
  { size: 'medium', speed: '느림', accuracy: '좋음', note: '배경 소음/사투리에 더 강함.' },
  { size: 'large-v3', speed: '매우 느림 (CPU)', accuracy: '최고', note: '언어 전환/짧은 발화가 많은 소스는 turbo보다 안정적.' },
  { size: 'large-v3-turbo', speed: '빠름 (GPU)', accuracy: '최고', note: 'large-v3보다 빠르지만 짧은 발화·언어 전환에서 환각 가능성 있음.' },
]

export function HelpModal({ onClose }: Props) {
  return createPortal(
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
              <li><b>번역</b> 탭에서 번역 시작을 누르면 붙습니다(로그인 또는 API 키 필요, 언어는 자동 감지). 용어집은 프로젝트 안의 모든 파일이 함께 씁니다.</li>
              <li>가운데 문장 목록에서 클릭 → 오른쪽 패널에서 시작/종료 시간, 원문, 번역문을 수정합니다.</li>
              <li><b>내보내기</b>에서 SRT/VTT 파일을 받거나, 같은 패널의 <b>AI 검수</b> 섹션으로 교정을 받습니다. (현재 선택한 파일 기준입니다.)</li>
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
                    붙입니다. <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer">HuggingFace 토큰(HF_TOKEN)</a> 설정과 최초 1회 모델 다운로드가 필요하며, 처리
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
                    담겨 관리됩니다. 업로드만으로는 전사가 시작되지 않으며, 파일을 선택하고
                    <b> 전사</b> 탭에서 직접 시작해야 합니다 — 진행 중인 작업은 화면 상단 작업 큐에서
                    항상 확인할 수 있습니다.
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
                <tr><td className="mono">Ctrl+Z</td><td>되돌리기</td></tr>
                <tr><td className="mono">Ctrl+Shift+Z</td><td>다시 실행</td></tr>
              </tbody>
            </table>
          </section>

          <section className="help-section">
            <h3>데이터 보호</h3>
            <p>
              업로드한 영상/오디오, 전사·번역 결과는 <b>이 컴퓨터의 <code>data/</code> 폴더 안에만</b>
              저장됩니다 — 별도 서버로 업로드되지 않으며, 사용 현황을 수집하는 분석/추적 코드도
              들어있지 않습니다.
            </p>
            <table className="help-table">
              <tbody>
                <tr>
                  <td className="mono">전사(Whisper)</td>
                  <td>완전히 로컬에서 처리됩니다. 모델 파일 자체는 최초 1회 HuggingFace에서
                    내려받아 <code>data/whisper_models/</code>에 캐시되며, 이후로는 인터넷 연결
                    없이도 동작합니다.</td>
                </tr>
                <tr>
                  <td className="mono">번역</td>
                  <td>로그인하면 서버가 대신 보관한 API 키로, 또는 <code>TRANSLATION_API_KEY</code>를
                    직접 설정했다면 그 키로 처리됩니다. 문장 텍스트가 해당 API로 전송되어
                    원문 교정과 번역을 함께 받아옵니다(영상/오디오 원본은 전송되지 않음).</td>
                </tr>
                <tr>
                  <td className="mono">AI 검수</td>
                  <td>자동 전송이 아니라, 검수용 파일을 내려받아 사용자가 직접 원하는 AI 챗에
                    올리고 결과를 다시 불러오는 방식입니다 — 어떤 서비스에 무엇을 보낼지는
                    전적으로 사용자가 결정합니다.</td>
                </tr>
                <tr>
                  <td className="mono">데이터 완전 삭제</td>
                  <td><code>data/</code> 폴더를 지우면 업로드한 파일, 프로젝트, 모델 캐시까지
                    한 번에 모두 삭제됩니다.</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section className="help-section">
            <h3>문제 해결</h3>
            <table className="help-table">
              <tbody>
                <tr>
                  <td className="mono">Whisper 모델 다운로드가 멈춘 것 같음</td>
                  <td>
                    Whisper 모델은 최초 1회만 자동 다운로드되며 크기에 따라 수 분이 걸릴 수
                    있습니다. 진행바가 인디터미네이트(불확정) 상태로 오래 유지되면 네트워크 연결을
                    확인하세요. 중단 후 다시 시작해도 이미 받은 부분은 다시 받지 않습니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">화자 분리가 안 됨 / 오류</td>
                  <td>
                    <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer">HuggingFace 토큰(HF_TOKEN)</a>이 설정되어 있는지, 그리고
                    <a href="https://huggingface.co/pyannote/speaker-diarization-3.1" target="_blank" rel="noopener noreferrer"> pyannote/speaker-diarization-3.1 모델 페이지</a>에서 이용약관에 동의했는지
                    확인하세요. 둘 다 없으면 화자 분리 없이 전사만 진행됩니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">영상 내보내기(번인 렌더링)가 실패함</td>
                  <td>
                    시스템에 ffmpeg가 설치되어 있어야 합니다(포터블 설치를 썼다면 <code>install.bat</code>이
                    자동으로 받아둡니다). 렌더링은 영상 길이에 비례해 몇 분~십몇 분 걸릴 수 있으니
                    진행률 표시가 남아있는 동안은 기다려주세요. 실패가 반복되면 원본 파일의 코덱을
                    의심해볼 수 있습니다.
                  </td>
                </tr>
                <tr>
                  <td className="mono">전사/번역 진행이 "error" 상태로 멈춤</td>
                  <td>
                    서버가 재시작되면 진행 중이던 작업은 이어받지 못하고 오류로 표시됩니다 — 해당
                    파일을 다시 선택해 전사/번역을 재시작하세요.
                  </td>
                </tr>
                <tr>
                  <td className="mono">번역이 이상하게 나옴(한/영 섞임 등)</td>
                  <td>위 &quot;한/영이 섞인 영상은?&quot; 섹션을 참고하세요.</td>
                </tr>
              </tbody>
            </table>
            <p className="help-hint">
              여기서 해결되지 않는 문제는 <b>버그 리포트</b>로 남겨주세요 — README 하단에
              GitHub Issues 링크가 있습니다.
            </p>
          </section>
        </div>
      </div>
    </div>,
    document.body,
  )
}
