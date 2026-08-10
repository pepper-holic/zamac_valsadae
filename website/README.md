# Zamak_Valsadae 서비스 웹사이트

앱(`frontend/`, `backend/`)과는 별개의, 독립 배포 가능한 마케팅/서비스 웹사이트입니다.
소개, 다운로드, 가격 정책, 이용약관/개인정보처리방침 등 "서비스 페이지" 성격의 콘텐츠는
전부 여기에 있습니다 — 설치형 앱 안에는 남기지 않습니다.

## 상태

아직 실제 도메인에 배포되지 않았습니다. 이용약관/개인정보처리방침/가격 정책 등 여러 페이지에
**더미(예시) 데이터**가 포함되어 있습니다 — 사업자 등록·요금제 확정 후 실제 값으로 교체해야
합니다 (각 페이지 상단 배너 참고).

## 개발

```bash
npm install
npm run dev      # http://localhost:5173 (frontend/의 dev 서버와 포트가 겹치면 --port로 조정)
npm run build    # dist/ 에 정적 빌드 생성 — Vercel/Netlify/S3 등 아무 정적 호스팅에 배포 가능
```

## 구조

- `src/pages/HomePage.tsx` — 랜딩 페이지(히어로 + 기능 소개)
- `src/pages/LegalPage.tsx` — `src/content/legalPages.tsx`의 데이터를 받아 렌더링하는 공용 페이지
- `src/content/` — 이용약관/개인정보처리방침/가격정책 등 실제 텍스트 콘텐츠 (원래
  `frontend/src/components/legal/`에 있던 것을 이 프로젝트로 이동)
- `src/components/Layout.tsx` — 상단 내비게이션 + 하단 푸터 공용 레이아웃
