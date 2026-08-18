import {
  Dummy,
  DummyBanner,
  FieldList,
  LinkCard,
  OsCard,
  PlanCard,
  StatusChip,
  Suggest,
} from './legalPrimitives'
import type { LegalPageDef } from './legalPagesLegal'

export const COMPANY_PAGE: LegalPageDef = {
  id: 'company',
  group: '회사 · 서비스',
  title: '회사 소개',
  content: (
    <>
      <DummyBanner>
        <strong>더미 데이터 포함.</strong> 아래 사업자 정보는 실제 등록 정보가 아닙니다.
        사업자 등록 완료 후 실제 값으로 교체해야 합니다.
      </DummyBanner>

      <h2>자막발사대</h2>
      <p>
        영상/오디오에서 자막을 뽑고, 번역하고, 검수하고, 자막까지 구운 영상으로 내보내는
        도구를 만듭니다. 번역 품질 검수와 원클릭 편의성을 핵심 가치로 삼습니다.
      </p>

      <h2>사업자 정보 (모든 페이지 하단 표기)</h2>
      <FieldList
        items={[
          { k: '상호(회사명)', v: <Dummy>제마크발사대 주식회사</Dummy> },
          { k: '대표자', v: <Dummy>홍길동</Dummy> },
          { k: '사업자등록번호', v: <Dummy>000-00-00000</Dummy> },
          { k: '통신판매업신고번호', v: <Dummy>제2026-서울강남-00000호</Dummy> },
          { k: '주소', v: <Dummy>서울특별시 강남구 테헤란로 000, 0층 (00호)</Dummy> },
          { k: '이메일', v: <Dummy>contact@zamacvalsadae.example</Dummy> },
          { k: '전화번호', v: <Dummy>02-0000-0000</Dummy> },
        ]}
      />

      <h2>문의</h2>
      <LinkCard
        href="https://github.com/pepper-holic/zamac_valsadae/issues"
        sub="github.com/pepper-holic/zamac_valsadae/issues"
      >
        버그 리포트 / 기능 요청
      </LinkCard>
      <p>
        그 외 문의: <Dummy>contact@zamacvalsadae.example</Dummy> (더미 — 실제 채팅 상담/이메일
        채널 확정 후 교체)
      </p>
    </>
  ),
}

export const PRICING_PAGE: LegalPageDef = {
  id: 'pricing',
  group: '회사 · 서비스',
  title: '가격 정책',
  content: (
    <>
      <DummyBanner>
        <strong>더미 데이터 포함, 단 시장 조사 기반으로 추정.</strong> 실제 사업자 등록·가격
        결정 전까지는 예시입니다. 아래 숫자는 임의가 아니라 2026-08 기준 Vrew 실제 요금제를
        조사해 우리 서비스 구조에 맞게 역산한 값입니다 — 근거는 바로 아래 참고.
      </DummyBanner>

      <h2>참고한 구조 (vrew.ai 2026-08 실사)</h2>
      <p>
        Free(무료, 무기한) ₩0 · Light 연 143,000원(월환산 11,917원) · Standard(추천) 연
        229,000원(월환산 19,083원) · Business 연 379,500원(법인용) 4단계. 크레딧 1개 = 음성분석
        1분 = AI 목소리 100자 = 번역 300자로 환산되는 <b>통합 크레딧제</b>이며, Free 플랜은 월
        200크레딧(번역 기준 약 6만 자)을 제공합니다.
      </p>
      <p>
        우리는 Vrew와 달리 <b>전사·스타일·내보내기가 전부 로컬 무료</b>이고, 클라우드로 나가는
        건 번역·AI 검수뿐입니다. 즉 Vrew가 파는 "전사+번역+AI이미지·영상·목소리" 묶음 크레딧
        대비 과금 범위가 훨씬 좁으므로, <b>가격도 그만큼 낮게</b> 잡는 것이 합리적입니다. 아래
        표는 Vrew의 Free 번역 한도(6만 자)를 기준점으로 맞추고, 유료 플랜은 Vrew 대비 약
        40~50% 수준으로 역산했습니다. 크레딧이라는 추상 단위 대신 우리 서비스에 실제로 쓰이는{' '}
        <b>"번역·검수 글자 수"</b>로 바로 표기해 더 직관적으로 만들었습니다.
      </p>

      <h2>플랜 (조사 기반 추정치)</h2>
      <div className="plan-card-grid">
        <PlanCard
          name="Free"
          price="무료"
          priceNote="무기한"
          features={[
            '로컬 전사·스타일·내보내기 무제한',
            '클라우드 번역·AI 검수 월 60,000자',
            '(Vrew Free 번역 한도와 동일하게 맞춤)',
          ]}
        />
        <PlanCard
          name="Light"
          price="월 4,900원"
          priceNote="연간 결제 시 20% 할인 (월환산 3,920원)"
          features={[
            '클라우드 번역·AI 검수 월 400,000자',
            '자막 스타일 프리셋 저장',
            'Vrew Light(월 11,917원) 대비 약 41% 가격',
          ]}
        />
        <PlanCard
          name="Standard"
          price="월 9,900원"
          priceNote="연간 결제 시 20% 할인 (월환산 7,920원)"
          recommended
          features={[
            '클라우드 번역·AI 검수 월 1,200,000자',
            '화자 분리, 우선 처리 큐',
            'Vrew Standard(월 19,083원) 대비 약 52% 가격',
          ]}
        />
      </div>
      <p className="legal-price-note">
        환산 근거: 평균 자막 문장 15자, 영상 1분당 약 150자 기준으로 계산하면 Standard 월
        120만 자는 약 8,000분(133시간) 분량의 번역·검수를 처리할 수 있는 수준입니다.
      </p>

      <h2>아직 결정해야 할 것</h2>
      <ul>
        <li>
          위 추정치를 실제 번역 API 원가(글자당 비용)와 대조해 마진이 남는지 검증 — 지금은
          경쟁사 가격 역산이라 원가 기반 검증 전 단계
        </li>
        <li>환불 조건과의 연동 (환불 안내 페이지와 정합성 확인)</li>
        <li>무료 플랜 한도를 넘겼을 때의 UX (즉시 결제 유도 vs 다음 달까지 대기)</li>
      </ul>

      <h2>FAQ (더미)</h2>
      <p>
        <b>해지는 언제든 가능한가요?</b>
        <br />
        네, 언제든 해지 가능하며 해지 시점까지는 서비스를 계속 이용할 수 있습니다.
      </p>
      <p>
        <b>플랜 변경 시 남은 크레딧/기간은 어떻게 되나요?</b>
        <br />
        남은 크레딧은 다음 결제 주기로 이월되지 않습니다.
      </p>
    </>
  ),
}

export const DOWNLOAD_PAGE: LegalPageDef = {
  id: 'download',
  group: '회사 · 서비스',
  title: '다운로드',
  subtitle: 'OS별 배포판 안내. macOS/Linux 항목은 실제로 빌드가 없어 더미로 채우지 않고 사실대로 남겨뒀습니다.',
  content: (
    <>
      <OsCard icon="🪟" title="Windows" status="ok">
        <ul>
          <li>
            <code>installer/installer.iss</code>(Inno Setup)로 빌드한 <code>.exe</code> — 관리자
            권한 불필요, 시작 메뉴/바탕화면 아이콘 생성.
          </li>
          <li>
            코드 서명이 안 되어 있어 실행 시 Windows SmartScreen 경고가 뜹니다 — "추가 정보 →
            실행"으로 진행하세요. (해소하려면 EV 코드 서명 인증서 구매 필요 —{' '}
            <Dummy>더미: 연 30만 원대</Dummy>)
          </li>
          <li>또는 <code>install.bat</code> + <code>run.bat</code>으로 포터블 방식 실행.</li>
        </ul>
        <a className="legal-download-button" href="/downloads/Zamak_Valsadae_Setup.exe">
          Zamak_Valsadae_Setup.exe 다운로드
        </a>
      </OsCard>

      <OsCard icon="🍎" title="macOS" status="soon">
        <p>
          아직 macOS용 빌드가 없습니다. faster-whisper/CTranslate2/ffmpeg의 macOS 지원 자체는
          가능하나, 포터블 런타임 스크립트와 macOS용 패키징(.dmg 등)을 별도로 만들어야 합니다.
        </p>
      </OsCard>

      <OsCard icon="🐧" title="Ubuntu / Linux" status="soon">
        <p>아직 Linux용 빌드가 없습니다.</p>
      </OsCard>

      <h2>시스템 요구사항 (Windows 기준)</h2>
      <ul>
        <li>디스크 여유 공간: 수 GB (Python/Node/ffmpeg 런타임 + Whisper 모델 캐시)</li>
        <li>인터넷 연결: 최초 설치 및 모델 최초 다운로드 시 필요, 이후에는 오프라인 사용 가능</li>
        <li>GPU: 없어도 동작(CPU 추론) — 다만 모델 크기가 클수록 느림</li>
      </ul>
    </>
  ),
}

export const LOGIN_PAGE: LegalPageDef = {
  id: 'login',
  group: '계정 · 커뮤니티',
  title: '로그인 / 체험하기',
  subtitle:
    '2026-08-13 기준 실제 구현 상태입니다. 이 페이지는 예전엔 "아직 없음" 요구사항 메모였는데, 이후 실제로 로그인 기능이 붙어서 최신 상태로 갱신했습니다.',
  content: (
    <>
      <StatusChip tone="ok">이메일/비밀번호 로그인 — 구현 완료</StatusChip>
      <ul>
        <li>
          <code>Supabase Auth</code>로 이메일/비밀번호 로그인·회원가입 지원. 데스크톱 앱
          툴바에서 로그인 상태를 표시합니다.
        </li>
        <li>
          로그인하면 번역·AI 검수가 자동으로 서버 릴레이(오라클 클라우드)를 거칩니다 — 사용자가
          직접 API 키를 설정할 필요가 없습니다.
        </li>
        <li>
          로그인하지 않아도 기존처럼 로컬 번역 엔진이나 수동 API 키 입력으로 계속 쓸 수
          있습니다 — 로그인은 선택 사항입니다.
        </li>
      </ul>

      <h2>아직 남은 것</h2>
      <ul>
        <li>구글 소셜 로그인 (이메일/비밀번호만 우선 구현, 후속 예정)</li>
        <li>실제 사용자 계정으로 로그인→번역까지 수동 확인 (지금은 자동화 테스트로만 검증)</li>
        <li>"체험하기"(게스트 체험) 전용 UX — 현재는 무로그인 상태와 동일하게 동작</li>
      </ul>

      <h2>참고 (vrew.ai)</h2>
      <p>
        상단 내비게이션에 "로그인"과 "체험하기"(CTA 버튼), "무료 다운로드"(CTA 버튼)를 나란히
        배치 — 클라우드 체험과 로컬 다운로드 두 경로를 동시에 제공하는 구조. 참고했지만 체험하기
        전용 게스트 모드는 아직 별도 구현하지 않았습니다.
      </p>
    </>
  ),
}

export const COMMUNITY_PAGE: LegalPageDef = {
  id: 'community',
  group: '계정 · 커뮤니티',
  title: '커뮤니티',
  content: (
    <>
      <DummyBanner>
        <strong>채널 미개설.</strong> 아래 링크는 실제 채널이 아닌 더미(예시) 형식입니다.
      </DummyBanner>

      <p>사용자들이 서로 질문하고 팁을 공유하는 공간입니다. 후보:</p>
      <LinkCard href="#" sub="discord.gg/zamacvalsadae-example">
        Discord 서버 <Dummy>더미</Dummy>
      </LinkCard>
      <LinkCard href="#" sub="cafe.naver.com/zamacvalsadae-example">
        네이버 카페 / 오픈채팅 <Dummy>더미</Dummy>
      </LinkCard>
      <LinkCard
        href="https://github.com/pepper-holic/zamac_valsadae/issues"
        sub="github.com/pepper-holic/zamac_valsadae/discussions"
      >
        GitHub Discussions (이미 있는 Issues와 연결 가능)
      </LinkCard>

      <h2 style={{ marginTop: 24 }}>착수 우선순위</h2>
      <p>
        낮음 — 사용자 규모가 어느 정도 쌓인 뒤 시작하는 것이 자연스럽습니다(사용자가 거의 없는
        상태의 커뮤니티는 오히려 신뢰도를 깎습니다). 배포 초기에는 GitHub Issues 하나로
        문의/피드백을 받는 것으로 충분합니다.
      </p>
    </>
  ),
}

export const NOTICES_PAGE: LegalPageDef = {
  id: 'notices',
  group: '계정 · 커뮤니티',
  title: '공지사항',
  subtitle:
    '배포 관련 공지를 여기에 쌓습니다. 기능 변경 상세 내역은 CHANGELOG.md — 이 페이지는 사용자 대상 공지, CHANGELOG는 개발자 대상 변경 이력으로 역할을 나눕니다.',
  content: (
    <>
      <h2>
        <Dummy>2026-08-10</Dummy> 서비스 준비 중 안내
      </h2>
      <p>
        자막발사대는 현재 로컬 설치형 도구로 제공되고 있습니다. 서버 기반 서비스(클라우드
        버전)는 준비 중이며, 관련 공지는 이 페이지에 업데이트할 예정입니다.
      </p>
    </>
  ),
}

export const INSIGHTS_PAGE: LegalPageDef = {
  id: 'insights',
  group: '콘텐츠',
  title: '인사이트',
  content: (
    <>
      <DummyBanner>
        <strong>콘텐츠 없음.</strong> 아래는 실제 결정된 내용이 아닌 더미(예시) 계획입니다.
      </DummyBanner>

      <p>
        블로그 성격의 콘텐츠 페이지입니다(자막 제작 팁, 업계 트렌드, 활용 사례 등). vrew.ai는
        "인사이트" 메뉴로 이런 콘텐츠를 운영합니다.
      </p>

      <p style={{ marginTop: 16 }}>운영 여부와 주기</p>
      <Suggest>월 2회, 지속적인 작성 리소스가 확보되면 시작</Suggest>

      <p style={{ marginTop: 16 }}>다루고 싶은 주제 방향</p>
      <Suggest>자막 제작 팁, 번역 품질 검수 노하우, 업데이트 소식</Suggest>

      <h2 style={{ marginTop: 24 }}>착수 우선순위</h2>
      <p>낮음 — 다른 법적/필수 페이지가 먼저 갖춰진 뒤, 콘텐츠 운영 여력이 생기면 시작하는 것을 권장합니다.</p>
    </>
  ),
}
