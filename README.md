# Zamak_Valsadae (자막발사대)

영상/오디오 파일에서 Whisper로 자막을 추출하고, 타임라인에서 싱크를 맞추고, 한↔영 번역(원문 교정 포함)을
붙이는 로컬 웹 도구입니다. 전사는 완전히 로컬에서 처리되고, 번역은 로그인(서버 제공 API 키) 또는
`TRANSLATION_API_KEY` 설정을 통해 OpenAI 호환 API로 처리됩니다.

> **처음이라면**: 이 저장소는 로컬 앱(`backend/`+`frontend/`) 외에도 클라우드 릴레이 서버
> (`server/`)와 별도 마케팅 사이트(`website/`)를 함께 담고 있습니다. 전체 구조·인증 흐름·
> 배포 방법은 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)에 정리되어 있습니다 — 코드를
> 고치기 전에 한 번 읽어보시길 권합니다.

## 개요

- 백엔드: FastAPI + Whisper + CTranslate2
- 프론트엔드: React + TypeScript + Vite
- 전사/편집/내보내기는 로컬에서, 번역은 API를 통해 처리합니다.
- `data/`에 모델 캐시와 프로젝트 데이터를 저장하며, 실행 시 자동으로 Whisper 모델을 다운로드하고 캐시합니다.
- Whisper 모델은 크기별로 최초 1회만 자동 다운로드되며, 전사 화면에 다운로드 여부와
  진행 상황("모델 다운로드 중" / "처리 중")이 표시됩니다.
- 로그인(이메일/비밀번호, Supabase Auth)하면 API 키 설정 없이 클라우드 릴레이(`server/`)를
  통해 번역을 쓸 수 있습니다 — 로그인은 선택 사항이며, 안 해도 로컬 모델/수동 API 키로
  기존처럼 동작합니다.

## 빠른 시작 (Windows 사용자를 위한 권장 방법 — 설치형 포터블 패키지)

이 프로젝트는 시스템에 Python/Node.js/ffmpeg를 설치하지 않는 **포터블 방식**입니다. 모든 실행 도구는
이 폴더 안의 `runtime/`에 내려받아 격리된 상태로 사용되며, 관리자 권한이 필요 없고 시스템 PATH도
건드리지 않습니다.

1. 이 폴더에서 **`install.bat`**을 더블클릭합니다.
   - Python, Node.js, ffmpeg를 `runtime/` 폴더 안에 자동으로 내려받고, 이 세션에서만 PATH에 추가합니다.
   - Whisper/CTranslate2 등 Python 패키지 설치도 함께 진행되므로 초기 설치에 시간이 걸릴 수 있습니다(수 GB).
   - Whisper 음성 인식 모델과 번역 모델 자체는 설치 시점에는 받지 않습니다 — 전사/번역을 처음 실행할 때
     자동으로 다운로드되며, 진행 상황(모델 다운로드 중 / 처리 중)이 화면에 표시됩니다.
   - 이미 받아둔 구성 요소는 재실행 시 다시 받지 않습니다(중단 후 재실행해도 안전).
2. 설치가 완료되면 **`run.bat`**을 더블클릭합니다.
   - 백엔드가 포터블 런타임으로 자동 실행되고, Chrome 같은 브라우저 탭이 아니라 **네이티브
     프로그램 창**(WebView2 기반, `pywebview`)이 뜹니다 — 백그라운드로는 여전히
     `http://127.0.0.1:8000`에서 로컬 서버가 돌지만, 사용자에게는 일반 설치형 프로그램처럼
     보입니다.
   - Windows 10/11에는 보통 WebView2 런타임이 기본 포함되어 있습니다. 없는 구버전 환경이라면
     Microsoft에서 WebView2 런타임을 설치해야 창이 뜹니다.
3. 종료할 때는 프로그램 창을 닫으면 됩니다(백그라운드 서버도 함께 종료됩니다).

> `install.bat`은 처음 한 번 또는 의존성이 변경되었을 때만 실행하면 됩니다.
> `runtime/` 폴더를 지우면 다음 `install.bat` 실행 시 처음부터 다시 내려받습니다.
> `run.bat`은 이제 `runtime/`이 없으면 install.bat 없이도 자동으로 설치를 먼저 진행합니다 —
> 아래 설치 프로그램(`.exe`)의 바탕화면 아이콘을 눌렀을 때도 이 경로를 그대로 탑니다.

## 설치 프로그램(.exe)으로 배포하기

`install.bat`/`run.bat`을 직접 더블클릭하는 대신, 일반 Windows 프로그램처럼 `.exe`를 실행해
설치하고 시작 메뉴·바탕화면 아이콘을 만들 수 있습니다. `installer/installer.iss`가 그 설치
프로그램을 만드는 [Inno Setup](https://jrsoftware.org/isinfo.php) 스크립트입니다.

- 설치 프로그램은 이 프로젝트의 소스 코드와 아이콘만 담고 있으며, Python/Node.js/ffmpeg나
  AI 모델은 포함하지 않습니다 — 그건 설치 후 처음 실행할 때(`run.bat`이 자동으로) 인터넷에서
  받아옵니다. 그래서 설치 파일 자체는 가볍지만, **최초 실행 시에는 인터넷 연결과 수 분~수십 분의
  다운로드 시간**이 필요합니다.
- 빌드 방법: Inno Setup을 설치한 뒤 `installer/installer.iss`를 열어 컴파일하거나,
  ```powershell
  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\installer.iss
  ```
  를 실행하면 `installer/dist/Zamak_Valsadae_Setup.exe`가 생성됩니다.
- 설치 위치는 관리자 권한이 필요 없는 `%LOCALAPPDATA%\Programs\Zamak_Valsadae`입니다.
- **코드 서명이 되어 있지 않습니다.** 다른 사람에게 배포하면 Windows SmartScreen이
  "Windows에서 PC를 보호했습니다" 경고를 띄웁니다 — "추가 정보" → "실행"을 눌러야 설치가
  진행됩니다. 경고를 없애려면 유료 코드 서명 인증서가 필요합니다(이 저장소에는 포함되어 있지
  않음).
- 제거(언인스톨)는 설치 프로그램이 깔았던 소스 파일만 지우고, 실행 중 생성된 `runtime/`과
  `data/`(다운로드한 모델, 프로젝트 데이터)는 그대로 남습니다 — 필요하면 수동으로 지우세요.

## 개발자용 수동 설치

### 백엔드

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate      # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```powershell
cd frontend
npm install
npm run dev
```

- 개발 서버: `http://localhost:5173`
- 프론트엔드는 `frontend/.env.development`에서 기본 백엔드 URL을 `http://localhost:8000`로 설정합니다.
- 프로덕션 빌드(`npm run build`)는 빌드 결과를 백엔드가 직접 서빙하는 방식과 함께 사용할 수 있습니다.

## 프로젝트 구조

이 저장소에는 서로 독립적으로 배포되는 여러 구성 요소가 들어있습니다 — 전체 관계와
데이터 흐름은 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)를 참고하세요.

- `backend/` — FastAPI 앱(로컬 전용, `127.0.0.1:8000`), 서비스 로직, 모델 스키마, 테스트
- `frontend/` — React 애플리케이션(데스크톱 앱 UI), 타입 정의, 컴포넌트
- `server/` — 클라우드 릴레이 서버(FastAPI). 로그인한 사용자의 번역 요청을 Supabase JWT로
  검증한 뒤, 서버가 보관한 OpenAI/Gemini 키로 대리 호출. 오라클 클라우드 VM에 별도 배포.
- `website/` — 서비스 소개·다운로드·가격 정책·이용약관 등 마케팅/서비스 페이지 전용 독립
  웹사이트(Vite + React Router). 앱(`frontend/`)과 별개로 배포합니다. 여러 페이지에 더미
  (예시) 데이터가 포함되어 있으니 상세는 `website/README.md` 참고.
- `deploy/` — `server/`·`website/`를 오라클 VM에 배포하는 PowerShell 스크립트
  (`deploy-website.ps1`, `deploy-relay.ps1`, `deploy-release.ps1`)
- `installer/` — Windows 설치 프로그램(`.exe`) 빌드 스크립트(Inno Setup + PyInstaller 런처)
- `docs/` — 아키텍처 가이드, 기능 로드맵/의사결정 히스토리
- `data/` — Whisper 모델 캐시(`whisper_models/`), 프로젝트 저장소(`projects/`)
- `runtime/` — `install.bat` 실행 시 내려받는 포터블 Python/Node.js/ffmpeg (Git에 커밋되지 않음)
- `install.bat`, `install.ps1`, `env.bat`, `run.bat` — Windows 설치/실행 스크립트
  (`installer/installer.iss`가 이 경로를 고정 참조하므로 옮기지 마세요)
- `kill-servers.bat` — 로컬 개발용 서버 포트 정리 스크립트

## 내부 개발 가이드

### 주요 폴더

- `backend/app/api/` — REST API 엔드포인트
- `backend/app/services/` — 비즈니스 로직과 모델 변환
- `frontend/src/components/` — 화면 컴포넌트
- `frontend/src/api/` — 타입 정의와 HTTP 클라이언트
- `frontend/src/utils/` — 헬퍼 함수

### 실행 흐름

1. 영상/오디오 업로드
2. Whisper 전사 실행
3. 번역 실행
4. 세그먼트 편집 및 AI 검수 결과 반영
5. SRT/VTT/JSON 내보내기

### 모델 다운로드 상태 표시

- `GET /models/status` — Whisper 모델 크기별로 이미 다운로드되어 있는지 여부와
  Whisper 전사에 실제 사용될 장치(`whisper_device`: `"cuda"` | `"cpu"`)를 반환합니다.
  프론트엔드는 전사 시작 전에 이 값을 조회해 "✓ 다운로드됨" / "⬇ 다운로드 필요" 배지와
  "🚀 GPU(CUDA) 감지됨" / "🖥 GPU 미감지" 배지를 보여줍니다.
- 전사 실행 중에는 `Project.stage` 값(`downloading_model` | `processing`)에 따라 진행 표시가
  달라집니다. 모델을 처음 받는 동안은 불확정(인디터미네이트) 진행바가, 실제 처리 중에는 퍼센트 진행바가
  표시됩니다. 번역은 언어를 자동 감지해 API로 처리되므로 모델 다운로드 단계가 없습니다.

### GPU 가속 (선택, Windows)

- `whisper_service`는 시작 시 `ctranslate2`로 CUDA GPU를 자동 감지합니다 — 감지되면 GPU(`float16`)로,
  아니면 CPU(`int8`)로 전사합니다. 별도 설정/토글은 없습니다.
- GPU가 감지돼도 실제 연산에 필요한 cuBLAS/cuDNN DLL이 없으면(NVIDIA 드라이버만 설치되고 CUDA
  Toolkit은 없는 경우) 모델 로드 또는 첫 연산 단계에서 실패할 수 있는데, 이 경우 **자동으로 CPU로
  재시도**합니다 — 전사 자체는 항상 끝까지 진행됩니다.
- CUDA Toolkit을 따로 설치하지 않고도 GPU 가속을 쓰려면 `requirements.txt`에 포함된
  `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`를 설치하면 됩니다(Windows, 수백 MB~1GB 다운로드).
  이 두 패키지가 설치돼 있으면 `whisper_service`가 해당 DLL 경로를 자동으로 PATH에 등록합니다.
- 화자 분리(`diarize=true`)를 함께 켜면 전사와 화자 분리(pyannote)를 별도 스레드에서 **동시에**
  실행해 전체 처리 시간을 줄입니다(`transcription_queue.py`). 단, pyannote 파이프라인은 중간에
  끊는 기능이 없어서, 이 둘이 동시에 도는 중에 취소하면 화자 분리가 끝날 때까지는 기다려야 합니다.
- 7초를 넘는 긴 문장은 단어별 타임스탬프를 이용해 가장 자연스러운 침묵 구간을 기준으로 자동
  분할됩니다(`whisper_service._split_long_segments`) — 자막 가독성 기준(`readability_service`)의
  "지속시간 초과" 경고와 같은 임계값을 씁니다.

### 내부 운영 규칙

- 커밋 메시지: `feat:`, `fix:`, `chore:`, `docs:` 형태로 작성합니다.
- 데이터 디렉토리(`data/`)는 개발용 캐시와 프로젝트 데이터를 담으며, 실제 커밋 대상이 아닙니다.
- 백엔드 의존성은 `backend/requirements.txt`에서 관리합니다.
- 프론트엔드 의존성은 `frontend/package.json`과 `frontend/package-lock.json`에서 관리합니다.
- Windows 개발 환경에서는 CRLF 경고가 발생할 수 있으나, Git은 정상적으로 CRLF를 관리하도록 구성되어 있습니다.

## 테스트

### 백엔드 테스트

```powershell
cd backend
python -m pytest
```

### 프론트엔드 테스트

```powershell
cd frontend
npm run test
```

- Vitest + React Testing Library를 사용합니다. 순수 로직(유틸/훅) 위주로 작성되어 있으며,
  UI 동작은 `npm run dev`로 직접 확인합니다.

## 환경변수

자주 건드리는 것만 요약합니다 — `backend/`·`server/`·`frontend/` 전체 환경변수 표는
[`docs/ARCHITECTURE.md#7-환경변수-서비스별`](docs/ARCHITECTURE.md#7-환경변수-서비스별)에
있습니다.

| 변수 | 설명 |
|---|---|
| `TRANSLATION_API_KEY` | 로그인 없이 번역을 쓰려면 설정 (OpenAI 호환 chat completions). 로그인 세션이 있으면 대신 서버 릴레이를 통해 처리되므로 불필요 |
| `TRANSLATION_API_BASE_URL` | 기본값 `https://api.openai.com/v1`. 호환 엔드포인트로 교체 가능 |
| `APP_DATA_DIR` | 업로드/프로젝트/모델 캐시 저장 위치. 기본값: 프로젝트 루트의 `data/` |
| `WHISPER_MODEL_CACHE_DIR` | Whisper 음성 인식 모델 캐시 위치. 기본값: `data/whisper_models/` (프로젝트 로컬 — 사용자 홈 폴더가 아님) |
| `VITE_API_BASE_URL` | 프론트엔드 개발 환경에서 사용할 백엔드 URL. `frontend/.env.development`에서 관리됩니다. |
| `HF_TOKEN` | 화자 분리 기능(선택)에 필요. HuggingFace 토큰이며, [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) 모델 이용약관에 먼저 동의해야 합니다. 설정하지 않으면 화자 분리 없이 전사만 진행됩니다. |

## 사용 흐름 요약

- 상단 툴바: 파일/도움말 메뉴, 프로젝트·파일 선택, 전사·번역 도구, 내보내기
- 좌상단: 샘플 영상 미리보기 및 재생 컨트롤 (화면비율에 따라 프레임 안에서 레터박스/필러박스 표시)
- 우상단: 스타일 설정 / 선택한 세그먼트 상세 편집 (탭 전환)
- 그 아래: 타임라인 스크러버 (Ctrl+스크롤로 확대/축소)
- 하단: 검수 대상 세그먼트 전체 목록 (찾기/바꾸기, 필러워드 자동 찾기, 필터, 일괄 작업)

1. 상단 업로드
2. 전사 실행
3. 번역 실행
4. 세그먼트 수정
5. AI 검수 결과 반영
6. 내보내기

## 모델 캐시 참고

모든 모델은 사용자 홈 폴더가 아닌 이 프로젝트의 `data/` 아래에만 저장됩니다 — `data/` 폴더를
지우면 모델 캐시까지 함께 깨끗이 삭제됩니다.

### Whisper 모델

- `tiny` / `base` / `small` / `medium` / `large-v3` / `large-v3-turbo` 중 선택한 크기만 최초 전사 실행 시 다운로드됩니다.
- `data/whisper_models/`에 캐시됩니다 (`WHISPER_MODEL_CACHE_DIR`로 위치 변경 가능).

## 버그 리포트 / 기능 요청

이 저장소의 [GitHub Issues](https://github.com/pepper-holic/zamac_valsadae/issues)로 등록해주세요.
버그 리포트는 재현 절차, 기대한 동작, 실제 동작, (가능하면) 스크린샷을 포함해주시면 빠르게
확인할 수 있습니다.

## 라이선스

이 저장소는 비공개(All rights reserved)입니다 — 자세한 내용은 [`LICENSE`](./LICENSE)를 참고하세요.
