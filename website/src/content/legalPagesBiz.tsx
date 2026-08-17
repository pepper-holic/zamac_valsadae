import { Dummy, DummyBanner, FieldList, LinkCard, StatusChip, Suggest } from './legalPrimitives'
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

      <h2>Zamak_Valsadae</h2>
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
        <strong>더미 데이터 포함.</strong> 요금제 설계(무료/유료 티어 수, 기능 제한제 vs 크레딧
        통합제)는 사업 결정이 먼저 필요합니다 — 아래 숫자는 논의용 예시입니다.
      </DummyBanner>

      <h2>참고한 구조 (vrew.ai 실사)</h2>
      <p>
        Free(무료, 무기한) / Light / Standard(추천) / Business 4단계, 월간·연간 결제 토글
        (연간 시 할인), <b>기능별 제한이 아니라 크레딧을 모든 기능이 공유하는 방식</b>. 그대로
        베낄 필요는 없지만 참고할 만한 모델입니다.
      </p>

      <h2>플랜 (더미)</h2>
      <div className="legal-table-scroll">
        <table className="legal-plan-table">
          <thead>
            <tr>
              <th>플랜</th>
              <th>가격</th>
              <th>포함 내용</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Free</td>
              <td className="price">무료</td>
              <td>로컬 다운로드형은 계속 무료, 클라우드는 월 60분 처리 크레딧</td>
            </tr>
            <tr>
              <td>Light</td>
              <td className="price">
                월 9,900원
                <br />
                <span className="legal-price-note">연간 결제 20% 할인</span>
              </td>
              <td>월 300분 처리 크레딧, 자막 스타일 프리셋 저장</td>
            </tr>
            <tr className="rec">
              <td>Standard (추천)</td>
              <td className="price">
                월 19,900원
                <br />
                <span className="legal-price-note">연간 결제 20% 할인</span>
              </td>
              <td>월 1,000분 처리 크레딧, 화자 분리, 우선 처리 큐</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2>결정해야 할 것</h2>
      <ul>
        <li>로컬(다운로드형)과 클라우드(SaaS)를 가격 정책에서 어떻게 구분할지</li>
        <li>과금 단위: 구독제(월/연) vs 크레딧(사용량 기반) vs 둘 다</li>
        <li>무료 플랜의 한도(처리 가능 영상 길이/개수 등)</li>
        <li>환불 조건과의 연동</li>
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
      <StatusChip tone="ok">Windows — 사용 가능</StatusChip>
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
      <div className="legal-card-note">
        <a href="/downloads/Zamak_Valsadae_Setup.exe">Zamak_Valsadae_Setup.exe 다운로드</a>
      </div>

      <h2 style={{ marginTop: 24 }}>
        <StatusChip tone="warn">macOS — 빌드 없음</StatusChip>
      </h2>
      <p>
        아직 macOS용 빌드가 없습니다. faster-whisper/CTranslate2/ffmpeg의 macOS 지원 자체는
        가능하나, 포터블 런타임 스크립트와 macOS용 패키징(.dmg 등)을 별도로 만들어야 합니다.
      </p>

      <h2>
        <StatusChip tone="warn">Ubuntu / Linux — 빌드 없음</StatusChip>
      </h2>
      <p>아직 Linux용 빌드가 없습니다.</p>

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
    '이 항목은 콘텐츠 페이지가 아니라 기능 요구사항 메모입니다 — 로그인은 실제 계정 시스템(백엔드 인증)이 있어야 의미가 있어서, 지금 로컬 전용 단계에서는 UI만 만들어봐야 가짜 기능이 됩니다.',
  content: (
    <>
      <h2>결정이 필요한 것</h2>
      <p>아래는 아직 확정되지 않았습니다 — "더미 제안"은 논의를 시작하기 위한 임시 기본값입니다.</p>

      <p>인증 방식: 이메일/비밀번호 vs 소셜 로그인(구글 등) vs 둘 다</p>
      <Suggest>이메일/비밀번호 + 구글 소셜 로그인 둘 다 지원</Suggest>

      <p style={{ marginTop: 16 }}>인증 구현체: 직접 구현 vs 인증 서비스(Auth0, Clerk, Supabase Auth 등)</p>
      <Suggest>Supabase Auth</Suggest>

      <p style={{ marginTop: 16 }}>계정과 로컬 프로젝트 데이터의 관계</p>
      <Suggest>초기엔 완전 별도, 이후 수동 "클라우드로 업로드" 기능 추가</Suggest>

      <p style={{ marginTop: 16 }}>"체험하기"(게스트 체험)를 로그인 없이 제공할지</p>
      <Suggest>제공, 단 처리량/저장 기간 제한</Suggest>

      <h2 style={{ marginTop: 24 }}>참고 (vrew.ai)</h2>
      <p>
        상단 내비게이션에 "로그인"과 "체험하기"(CTA 버튼), "무료 다운로드"(CTA 버튼)를 나란히
        배치 — 클라우드 체험과 로컬 다운로드 두 경로를 동시에 제공하는 구조.
      </p>

      <h2>이 저장소에서 아직 하지 않은 것</h2>
      <ul>
        <li>백엔드에 사용자/세션 모델 없음 (스키마는 Project/MediaItem 등 프로젝트 데이터만 존재)</li>
        <li>프론트엔드에 인증 화면/라우팅 없음</li>
      </ul>
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
        Zamak_Valsadae는 현재 로컬 설치형 도구로 제공되고 있습니다. 서버 기반 서비스(클라우드
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
