# Zamak_Valsadae (자막발사대)

영상/오디오 파일에서 Whisper로 자막을 추출하고, 타임라인에서 싱크를 맞추고, 한↔영 번역을 붙이고, API 키 없이 파일을 주고받는 방식으로 AI 검수를 받을 수 있는 로컬 웹 도구입니다.

## 개요

- 백엔드: FastAPI + Whisper + CTranslate2
- 프론트엔드: React + TypeScript + Vite
- 로컬에서 전체 전사/번역/편집/내보내기/검수 워크플로우를 처리합니다.
- `data/`에 모델 캐시와 프로젝트 데이터를 저장하며, 실행 시 자동으로 필요한 모델을 변환하고 캐시합니다.
- Whisper/번역 모델은 각 방향·크기별로 최초 1회만 자동 다운로드되며, 전사/번역 화면에 다운로드 여부와
  진행 상황("모델 다운로드 중" / "처리 중")이 표시됩니다.

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
   - 백엔드가 포터블 런타임으로 자동 실행되고 기본 브라우저가 열립니다.
   - 기본 URL은 `http://localhost:8000`입니다.
3. 종료할 때는 `run.bat`이 띄운 콘솔 창을 닫으면 됩니다.

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

- `backend/` — FastAPI 앱, 서비스 로직, 모델 스키마, 테스트
- `frontend/` — React 애플리케이션, 타입 정의, 컴포넌트
- `data/` — 번역 모델 캐시(`ct2models/`), Whisper 모델 캐시(`whisper_models/`), 프로젝트 저장소(`projects/`)
- `runtime/` — `install.bat` 실행 시 내려받는 포터블 Python/Node.js/ffmpeg (Git에 커밋되지 않음)
- `install.bat`, `install.ps1`, `env.bat`, `run.bat` — Windows 설치/실행 스크립트
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

- `GET /models/status` — Whisper 모델 크기별, 번역 방향별로 이미 다운로드되어 있는지 여부를 반환합니다.
  프론트엔드는 전사/번역 시작 전에 이 값을 조회해 "✓ 다운로드됨" / "⬇ 다운로드 필요" 배지를 보여줍니다.
- 전사/번역 실행 중에는 `Project.stage` 값(`downloading_model` | `processing`)에 따라 진행 표시가
  달라집니다. 모델을 처음 받는 동안은 불확정(인디터미네이트) 진행바가, 실제 처리 중에는 퍼센트 진행바가
  표시됩니다.

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

- 현재 프론트엔드 테스트 스위트는 별도 설정이 없으므로, UI 변경 시 `npm run dev`로 직접 확인합니다.

## 환경변수

| 변수 | 설명 |
|---|---|
| `TRANSLATION_API_KEY` | 설정 시 번역 엔진에서 "API" 옵션 사용 가능 (OpenAI 호환 chat completions) |
| `TRANSLATION_API_BASE_URL` | 기본값 `https://api.openai.com/v1`. 호환 엔드포인트로 교체 가능 |
| `APP_DATA_DIR` | 업로드/프로젝트/모델 캐시 저장 위치. 기본값: 프로젝트 루트의 `data/` |
| `CT2_MODEL_CACHE_DIR` | 번역(CTranslate2) 모델 캐시 위치. 기본값: `data/ct2models/` |
| `WHISPER_MODEL_CACHE_DIR` | Whisper 음성 인식 모델 캐시 위치. 기본값: `data/whisper_models/` (프로젝트 로컬 — 사용자 홈 폴더가 아님) |
| `VITE_API_BASE_URL` | 프론트엔드 개발 환경에서 사용할 백엔드 URL. `frontend/.env.development`에서 관리됩니다. |
| `HF_TOKEN` | 화자 분리 기능(선택)에 필요. HuggingFace 토큰이며, [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) 모델 이용약관에 먼저 동의해야 합니다. 설정하지 않으면 화자 분리 없이 전사만 진행됩니다. |

## 사용 흐름 요약

- 왼쪽: 비디오 플레이어 및 재생/타임라인
- 가운데: 세그먼트 목록
- 오른쪽: 선택한 세그먼트 상세 편집

1. 상단 업로드
2. 전사 실행
3. 번역 실행
4. 세그먼트 수정
5. AI 검수 결과 반영
6. 내보내기

## 모델 캐시 참고

모든 모델은 사용자 홈 폴더가 아닌 이 프로젝트의 `data/` 아래에만 저장됩니다 — `data/` 폴더를
지우면 모델 캐시까지 함께 깨끗이 삭제됩니다.

### 번역 모델

- **한→영**: `Helsinki-NLP/opus-mt-ko-en`
- **영→한**: `facebook/nllb-200-distilled-600M` (언어 태그 `kor_Hang` 사용)
- 최초 실행 시 CTranslate2 int8 포맷으로 변환 후 `data/ct2models/`에 캐시됩니다.

### Whisper 모델

- `tiny` ~ `large-v3` 중 선택한 크기만 최초 전사 실행 시 다운로드됩니다.
- `data/whisper_models/`에 캐시됩니다 (`WHISPER_MODEL_CACHE_DIR`로 위치 변경 가능).
