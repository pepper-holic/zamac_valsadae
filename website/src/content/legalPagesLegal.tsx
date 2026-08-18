import { Clause, Dummy, DummyBanner, FieldList } from './legalPrimitives'

export type LegalPageDef = {
  id: string
  group: string
  title: string
  subtitle?: string
  content: React.ReactNode
}

export const TERMS_PAGE: LegalPageDef = {
  id: 'terms',
  group: '법적 문서',
  title: '이용약관',
  content: (
    <>
      <DummyBanner>
        <strong>더미 데이터 포함.</strong> 회사 정보·요금 조항·관할 법원·시행일은 실제 값이
        아닙니다. 시행 전 반드시 법률 검토를 받으세요 — 이 문서는 표준 조항 뼈대만 제공합니다.
      </DummyBanner>

      <FieldList
        items={[
          { k: '회사명', v: <Dummy>제마크발사대 주식회사</Dummy> },
          { k: '대표자', v: <Dummy>홍길동</Dummy> },
          { k: '사업자등록번호', v: <Dummy>000-00-00000</Dummy> },
          { k: '통신판매업신고번호', v: <Dummy>제2026-서울강남-00000호</Dummy> },
          { k: '주소', v: <Dummy>서울특별시 강남구 테헤란로 000, 0층</Dummy> },
          { k: '고객센터', v: <Dummy>contact@zamacvalsadae.example / 02-0000-0000</Dummy> },
          { k: '시행일', v: <Dummy>2026-09-01</Dummy> },
        ]}
      />

      <Clause title="제1조 (목적)">
        <p>
          이 약관은 <Dummy>제마크발사대 주식회사</Dummy>(이하 "회사")가 제공하는 자막발사대
          서비스(이하 "서비스")의 이용과 관련하여 회사와 회원 간의 권리, 의무 및 책임사항을
          규정함을 목적으로 합니다.
        </p>
      </Clause>
      <Clause title="제2조 (정의)">
        <ul>
          <li>"서비스"란 회사가 제공하는 영상/오디오 전사·번역·자막 편집·내보내기 관련 일체의 기능을 말합니다.</li>
          <li>"회원"이란 이 약관에 동의하고 서비스 이용 계약을 체결한 자를 말합니다.</li>
          <li>"콘텐츠"란 회원이 서비스에 업로드하는 영상/오디오 파일 및 그로부터 생성되는 자막 데이터를 말합니다.</li>
        </ul>
      </Clause>
      <Clause title="제3조 (약관의 효력 및 변경)">
        <p>
          회사는 관련 법령을 위반하지 않는 범위에서 이 약관을 변경할 수 있으며, 변경 시
          적용일자 및 변경사유를 명시해 서비스 내 공지 및 이메일(<Dummy>더미</Dummy>)로 사전
          공지합니다.
        </p>
      </Clause>
      <Clause title="제4조 (이용계약의 체결)">
        <p>
          회원은 이메일 가입 또는 소셜 로그인(<Dummy>더미</Dummy>)을 통해 이용계약을 체결합니다.
          회사는 관련 법령을 위반하지 않는 범위에서 가입 신청을 승낙합니다.
        </p>
      </Clause>
      <Clause title="제5조 (서비스의 제공 및 변경)">
        <p>
          회사는 다음과 같은 서비스를 제공합니다: 음성 전사, 자막 번역, 세그먼트 편집, 자막
          스타일링, 자막 파일/영상 내보내기, AI 검수 연동. 회사는 운영상·기술상의 필요에 따라
          서비스의 내용을 변경할 수 있습니다.
        </p>
      </Clause>
      <Clause title="제6조 (요금 및 결제)">
        <p>
          요금제, 결제 수단, 결제 주기는 가격 정책 페이지를 따릅니다. 결제는 신용카드 및
          간편결제(<Dummy>더미</Dummy>)를 지원할 예정입니다.
        </p>
      </Clause>
      <Clause title="제7조 (환불)">
        <p>환불 정책은 환불 안내 페이지를 따릅니다.</p>
      </Clause>
      <Clause title="제8조 (회원의 의무)">
        <p>
          회원은 다음 행위를 해서는 안 됩니다: 타인의 저작권 등 권리를 침해하는 콘텐츠 업로드,
          서비스를 이용한 불법적 목적의 콘텐츠 생성, 서비스 운영을 방해하는 행위, 관련 법령 및
          이 약관이 금지하는 행위.
        </p>
      </Clause>
      <Clause title="제9조 (콘텐츠에 대한 권리)">
        <p>
          회원이 업로드한 콘텐츠에 대한 권리는 회원에게 있습니다. 회사는 서비스 제공을 위해
          필요한 범위에서만 콘텐츠를 처리하며, 이를 회원의 동의 없이 다른 목적으로 이용하지
          않습니다. 콘텐츠 저장/삭제 정책 상세는 개인정보처리방침 및 데이터 보호 안내를
          따릅니다.
        </p>
      </Clause>
      <Clause title="제10조 (서비스 이용의 제한 및 중지)">
        <p>회사는 회원이 이 약관을 위반한 경우 사전 통지 후 서비스 이용을 제한할 수 있습니다.</p>
      </Clause>
      <Clause title="제11조 (면책조항)">
        <p>
          회사는 천재지변, 회원의 귀책사유 등 회사가 통제할 수 없는 사유로 인한 서비스 중단에
          대해 책임을 지지 않습니다. 전사/번역 결과는 자동화된 AI 처리 결과로, 정확도를
          보증하지 않으며 최종 검수 책임은 회원에게 있습니다 (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="제12조 (분쟁 해결)">
        <p>
          이 약관과 관련한 분쟁은 회사 소재지를 관할하는 법원을 관할 법원으로 합니다
          (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="부칙">
        <p>이 약관은 <Dummy>2026-09-01</Dummy>부터 적용됩니다.</p>
      </Clause>
    </>
  ),
}

export const PRIVACY_PAGE: LegalPageDef = {
  id: 'privacy',
  group: '법적 문서',
  title: '개인정보처리방침',
  content: (
    <>
      <DummyBanner>
        <strong>더미 데이터 포함.</strong> 회원가입/결제 시스템 설계 및 사업자 등록 확정 후
        실제 값으로 교체해야 합니다. 시행 전 반드시 법률 검토를 받으세요.
      </DummyBanner>

      <FieldList
        items={[
          { k: '회사명', v: <Dummy>제마크발사대 주식회사</Dummy> },
          { k: '개인정보보호책임자', v: <Dummy>홍길동 / 개발총괄 / privacy@zamacvalsadae.example</Dummy> },
          { k: '시행일', v: <Dummy>2026-09-01</Dummy> },
        ]}
      />

      <Clause title="1. 수집하는 개인정보 항목">
        <h4>로컬 전용 사용 시 (현재)</h4>
        <p>
          서버로 전송되는 개인정보가 없습니다. 업로드한 영상/오디오와 전사·번역 결과는
          사용자의 컴퓨터 안(<code>data/</code> 폴더)에만 저장됩니다.
        </p>
        <h4>클라우드 서비스 전환 시 (예정, 더미)</h4>
        <ul>
          <li>회원가입 시: 이메일 주소, 비밀번호(해시 저장) 또는 소셜 로그인 식별자</li>
          <li>결제 시: 카드 정보는 자체 저장하지 않고 PG사(결제대행사)에 위탁 처리</li>
          <li>서비스 이용 시: 업로드 파일은 처리 완료 후 일정 기간(예: 30일) 뒤 자동 삭제</li>
          <li>자동 수집 항목: 접속 로그(IP, 접속 일시), 쿠키, 기기/브라우저 정보</li>
        </ul>
      </Clause>
      <Clause title="2. 개인정보의 수집 및 이용 목적">
        <p>
          회원 관리(가입 의사 확인, 본인 확인), 서비스 제공(전사/번역/자막 편집 기능 이용),
          요금 정산(결제 및 환불 처리), 고객 문의 대응 및 공지사항 전달을 위해 개인정보를
          수집·이용합니다 (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="3. 개인정보의 보유 및 이용 기간">
        <p>
          원칙적으로 회원 탈퇴 시 지체 없이 파기합니다. 단, 관계 법령에 따라 보존이 필요한
          경우 전자상거래법 등에서 정한 기간(예: 계약/청약철회 기록 5년, 소비자 불만·분쟁처리
          기록 3년) 동안 보관합니다 (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="4. 개인정보의 제3자 제공">
        <p>
          회사는 원칙적으로 이용자의 개인정보를 제3자에게 제공하지 않습니다. 다만 이용자가
          번역 API 엔진을 직접 활성화한 경우, 번역 대상 텍스트가 해당 외부 API 제공업체로
          전송될 수 있습니다.
        </p>
      </Clause>
      <Clause title="5. 개인정보 처리의 위탁">
        <p>
          결제대행사(PG, <Dummy>더미</Dummy>), 클라우드 인프라(호스팅, <Dummy>더미</Dummy>)에
          개인정보 처리 업무를 위탁할 수 있습니다.
        </p>
      </Clause>
      <Clause title="6. 이용자의 권리와 행사 방법">
        <p>
          이용자는 언제든 자신의 개인정보를 조회, 수정, 삭제, 처리 정지를 요청할 수 있습니다.
          요청은 <Dummy>privacy@zamacvalsadae.example</Dummy>로 접수합니다.
        </p>
      </Clause>
      <Clause title="7. 개인정보의 파기 절차 및 방법">
        <p>
          전자적 파일 형태로 저장된 개인정보는 복구 불가능한 방법으로 영구 삭제하며, 종이
          문서에 기록된 개인정보는 분쇄기로 분쇄하거나 소각합니다.
        </p>
      </Clause>
      <Clause title="8. 쿠키(Cookie)의 운용">
        <p>
          로그인 세션 유지 및 서비스 이용 편의를 위해 쿠키를 사용할 수 있습니다
          (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="9. 개인정보보호책임자 및 문의처">
        <ul>
          <li>성명: <Dummy>홍길동</Dummy></li>
          <li>연락처: <Dummy>privacy@zamacvalsadae.example / 02-0000-0000</Dummy></li>
        </ul>
      </Clause>
      <Clause title="부칙">
        <p>이 방침은 <Dummy>2026-09-01</Dummy>부터 적용됩니다.</p>
      </Clause>
    </>
  ),
}

export const REFUND_PAGE: LegalPageDef = {
  id: 'refund',
  group: '법적 문서',
  title: '환불 안내',
  content: (
    <>
      <DummyBanner>
        <strong>더미 데이터 포함.</strong> 결제/구독 방식(정기결제, 크레딧 등)이 확정된 후
        실제 값으로 교체해야 합니다.
      </DummyBanner>

      <Clause title="청약 철회 (구매 취소)">
        <p>
          전자상거래법에 따라 결제일로부터 7일 이내, 서비스를 실제로 이용하지 않은 경우 청약을
          철회하고 전액 환불받을 수 있습니다. 크레딧을 일부라도 사용한 경우, 사용분을 제외한
          나머지 금액을 환불합니다 (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="정기 구독 환불">
        <p>
          월간/연간 구독 모두 지원하며, 중도 해지 시 남은 기간을 일할 계산해 환불합니다
          (<Dummy>더미</Dummy>).
        </p>
      </Clause>
      <Clause title="환불이 제한되는 경우">
        <ul>
          <li>크레딧을 이미 소진한 경우</li>
          <li>서비스 부정 이용(어뷰징, 약관 위반)이 확인된 경우</li>
          <li>무료 체험 기간 중 결제된 유료 플랜을 체험 종료 후 사용한 경우</li>
        </ul>
        <p><Dummy>더미 — 실제 정책 확정 후 교체</Dummy></p>
      </Clause>
      <Clause title="환불 처리 기간">
        <p>환불 요청 확인 후 영업일 기준 <Dummy>3~7일</Dummy> 이내에 결제 수단으로 환불됩니다.</p>
      </Clause>
      <Clause title="환불 신청 방법">
        <p>
          <Dummy>refund@zamacvalsadae.example</Dummy> 또는 고객센터 채팅 상담을 통해 신청할 수
          있습니다.
        </p>
      </Clause>
      <Clause title="부칙">
        <p>이 안내는 <Dummy>2026-09-01</Dummy>부터 적용됩니다.</p>
      </Clause>
    </>
  ),
}
