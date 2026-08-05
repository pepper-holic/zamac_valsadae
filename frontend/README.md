# Zamak_Valsadae Frontend

이 폴더는 React + TypeScript + Vite 기반의 프로젝트 UI를 담당합니다.

## 주요 역할

- 영상/오디오 업로드 UI
- 세그먼트 목록, 상세 편집, 리뷰/검수 결과 표시
- 자막 내보내기(SRT/VTT/JSON)
- 백엔드 API와 통신하여 전사/번역/검수 워크플로우를 연결

## 실행 방법

```powershell
cd frontend
npm install
npm run dev
```

- 개발 서버: `http://localhost:5173`
- 기본 API 엔드포인트: `http://localhost:8000`
- `frontend/.env.development`에서 `VITE_API_BASE_URL`을 관리합니다.

## 빌드

```powershell
npm run build
```

프로덕션 빌드 결과물은 백엔드가 직접 서빙할 수 있습니다.

## 폴더 구조

- `src/App.tsx` — 앱 진입점, 프로젝트/세그먼트 상태, 리뷰 diff 처리
- `src/api/` — 타입 정의 및 HTTP 클라이언트
- `src/components/` — UI 컴포넌트
- `src/utils/` — 시간 변환 등 공용 유틸
- `public/` — 정적 아이콘 및 HTML 템플릿

## 내부 가이드

- `App.tsx`에서 `reviewDiffs`와 `selectedSegment` 상태를 관리합니다.
- `SegmentList.tsx`는 필터 탭(`unreviewed`, `needsCheck`, `ok`, `reviewed`)과 선택 기능을 구현합니다.
- `frontend/.env.development`를 통해 개발 중 백엔드 URL을 일관되게 유지하세요.
- `frontend/.gitignore`에는 빌드 결과, 노드 모듈, 환경 파일 등을 제외하도록 설정되어 있습니다.
- 코드 스타일은 TypeScript/React 표준을 따르되, 컴포넌트 경계와 상태 의존성을 명확히 유지합니다.

## 테스트

현재 프론트엔드에는 별도 테스트 스크립트가 포함되어 있지 않습니다. UI 변경 시 `npm run dev`로 직접 동작을 확인하세요.

## 참고

- 프론트엔드는 로컬에서 `http://localhost:8000` 백엔드를 호출합니다.
- 백엔드 실행 없이 프론트엔드를 실행하면 일부 기능이 동작하지 않습니다.
