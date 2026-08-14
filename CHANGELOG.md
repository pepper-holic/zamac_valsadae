# Changelog

이 프로젝트의 주요 변경사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를
따릅니다. 별도 버전 태그가 아직 없어 지금까지의 작업을 하나의 `[Unreleased]` 항목으로 소급 정리했습니다 —
이후 배포 시점부터 버전을 나누어 관리합니다.

## [Unreleased]

### Added

- Whisper(faster-whisper/CTranslate2) 기반 로컬 전사, 한↔영 번역(로컬 모델 + API 엔진 선택).
- 세그먼트 목록 검수 UI — 필터(미작업/검토 필요/괜찮음/완료), 찾기·바꾸기, 필러워드 자동 감지,
  다중 선택 일괄 작업(검토완료 표시/삭제/병합).
- 타임라인 파형 표시 + 드래그로 세그먼트 시작/종료 시간 조절.
- 자막 미리보기 오버레이, 자막 스타일 편집기(폰트/색상/위치/페이드/카라오케 하이라이트) + 실시간 미리보기.
- 자막 번인(burn-in) 렌더링 및 영상 내보내기, 텍스트 삭제와 연동되는 컷 편집(잘라낸 문장 구간을
  최종 영상에서도 제거).
- 항목별 Undo/Redo(Ctrl+Z / Ctrl+Shift+Z).
- AI 검수 파일 내보내기/불러오기 워크플로우(외부 AI 챗에 검수를 맡기고 결과를 diff로 반영).
- 단어별(word-level) 타임스탬프 저장 — 카라오케 하이라이트 정밀도 개선.
- Whisper `large-v3-turbo` 모델 옵션 (large-v3 대비 약 5배 빠름).
- 진행 중인 작업을 항상 보여주는 작업 큐 패널, 실제 시작 시각 기반 경과 시간 표시(브라우저를
  새로고침해도 초기화되지 않음).
- CapCut·Vrew 벤치마킹 기반 UI 개편 — 좌측 아이콘 레일(전사/번역/스타일/AI검수), 상단 고정
  "내보내기"/실행취소·다시실행 버튼, 확대된 라벨 타임라인, 번호 매긴 세그먼트 리스트(hover 시에만
  보조 액션 노출).
- 리사이즈 가능한 도구 패널/영상 컬럼 너비, 세그먼트 상세 패널의 오버레이 전환.
- 드래그 앤 드롭 업로드, 온보딩 안내 문구.
- 포터블 설치(`install.bat`/`run.bat`, 격리된 Python/Node/ffmpeg 런타임) 및 Windows 설치
  프로그램(`installer/installer.iss` → `.exe`).
- Whisper 전사 GPU 자동 감지 + CPU 폴백 — `ctranslate2`로 CUDA GPU를 감지해 우선 사용하고,
  모델 로드나 실행 중 어느 단계에서 실패하든(cuBLAS/cuDNN DLL 누락 등) 자동으로 CPU로 재시도.
  CUDA Toolkit 없이도 GPU를 쓸 수 있도록 `nvidia-cublas-cu12`/`nvidia-cudnn-cu12`(선택 의존성)의
  DLL 경로를 자동으로 PATH에 등록.
- `GET /models/status`에 `whisper_device`(`cuda`|`cpu`) 필드 추가, 전사 패널에 감지된 장치
  표시("🚀 GPU(CUDA) 감지됨" / "🖥 GPU 미감지").
- 화자 분리(diarize) 활성화 시 전사와 화자 분리를 별도 스레드에서 동시에 실행해 전체 처리
  시간 단축("이중전사" 최적화).
- 7초를 넘는 긴 문장을 단어별 타임스탬프 기반 자연스러운 침묵 구간에서 자동 분할.
- 타임라인에서 Ctrl(⌘)+스크롤로 확대/축소.
- 작업 큐 패널의 진행률 표시줄 옆에 퍼센트 숫자 표시.
- 상단 메뉴바(파일/도움말 드롭다운) 방식 툴바, 전사/번역 도구를 툴바 드롭다운으로 이동.
- 좌상단 영상 미리보기 + 우상단 스타일/상세검수 탭 + 하단 전체 폭 검수 목록 + 별도 행 타임라인
  스크러버로 레이아웃 재편, 위/아래 영역 높이 리사이즈.
- 영상 미리보기 프레임을 16:9로 고정하고, 화면비율 변경 시 프레임 안에서 레터박스/필러박스로 표시.

### Changed

- 프로젝트 자체 라이선스를 비공개(All rights reserved)로 결정, 루트 `LICENSE` 추가.
- 상단 도구 모음을 세그먼트 컨트롤 + 드롭다운 방식에서 좌측 아이콘 레일 + 슬라이드 패널 방식으로 재구성.
- `run.bat` 실행 시 Chrome 등 브라우저 탭 대신 `pywebview`(WebView2) 기반 네이티브 프로그램
  창으로 뜨도록 변경(`backend/app/desktop.py`) — 백엔드는 여전히 로컬에서 실행, 사용자에게는
  일반 설치형 프로그램처럼 보이도록 함.
- 서비스 웹페이지(소개/다운로드/가격 정책/이용약관 등)를 앱에서 완전히 분리해 별도
  `website/` 프로젝트로 이동 — 앱 안에는 웹사이트로 가는 링크(아이콘)와 "프로그램 정보"
  모달만 남기고, 순수 기능(전사/번역/스타일/검수/내보내기)에 집중하도록 정리.
- `docs/pages/` 디렉터리 삭제 — 이관 완료된 `website/src/content/`와 내용이 어긋날 위험이
  있는 중복 원본이라 정리(`learn.md`는 `HelpModal`과 중복이라 이관 없이 삭제).
- 프론트엔드 전체 리팩토링 — `App.css`(2013줄)를 13개 기능별 파일로 분리
  (`src/styles/`), `App.tsx`(730줄)를 커스텀 훅(`useProjectWorkspace`,
  `useSegmentEditing`, `useReviewDiffs`, `useKeyboardShortcuts`, `usePanelWidths`)으로
  분리해 314줄로 축소, `VideoStage.tsx`(461줄)를 `Timeline`/`TransportControls`
  컴포넌트와 `useTimelineZoom`/`useVideoAspectRatio` 훅으로 분리. 이제 프론트엔드
  소스 파일 전부 400줄 이하.
- `Timeline`, `useSegmentEditing`, `useProjectWorkspace`에 대한 테스트 17개 추가
  (총 6개 파일, 40개 테스트 통과).
- 세그먼트 선택 시 스크롤 위치를 항상 목록 상단으로 통일(`scrollIntoView({block:'start'})`),
  sticky 검수 툴바 높이를 `ResizeObserver`로 추적해 선택한 줄이 툴바에 가려지지 않도록 함.
- 툴바/검수 패널 등 전반적인 UI 밀도(패딩·폰트 크기) 조정.

### Fixed

- 작업 진행 경과 시간이 브라우저 새로고침 시 실제 시작 시각이 아닌 새로고침 시점부터 다시 세던 문제 —
  백엔드가 작업 시작 시각(`started_at`)을 내려주도록 수정.
- 패널 일부(찾기/바꾸기, 필러워드 감지 등)가 스타일 클래스 없이 브라우저 기본 스타일로 렌더링되던 문제.
- `overflow-y`만 지정되고 `overflow-x`가 없어 브라우저가 암묵적으로 가로 스크롤을 만들던 패널들
  (도구 패널, 영상 컬럼, 세그먼트 상세 오버레이, 도움말 모달 등).
- 툴바에 `overflow-x:auto`+`overflow-y:visible` 조합을 쓰면 브라우저가 암묵적으로
  `overflow-y:auto`를 적용해 툴바 내용 위아래가 잘려 보이던 버그(`overflow-y:clip`으로 교체).
- 홈 화면 콘텐츠가 다 보이는데도 불필요한 세로 스크롤바가 뜨던 문제(여백 과다로 인한 미세한 오버플로).
- GPU는 감지되지만 cuBLAS/cuDNN DLL이 없어 전사 자체가 실패하던 문제 — 실행 시점 실패도 감지해
  CPU로 자동 재시도.
