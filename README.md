# Zamak_Valsadae (자막발사대)

영상/오디오 파일에서 Whisper로 자막을 추출하고, 타임라인에서 싱크를 맞추고, 한↔영 번역을 붙이고, API 키 없이 파일을 주고받는 방식으로 AI 검수를 받을 수 있는 로컬 웹 도구입니다.

## 개요

- 백엔드: FastAPI + Whisper + CTranslate2
- 프론트엔드: React + TypeScript + Vite
- 로컬에서 전체 전사/번역/편집/내보내기/검수 워크플로우를 처리합니다.
- `data/`에 모델 캐시와 프로젝트 데이터를 저장하며, 실행 시 자동으로 필요한 모델을 변환하고 캐시합니다.

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
- `data/` — CTranslate2 모델 캐시(`ct2models/`) 및 프로젝트 저장소(`projects/`)
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
| `APP_DATA_DIR` | 업로드/프로젝트/CTranslate2 모델 캐시 저장 위치. 기본값: 프로젝트 루트의 `data/` |
| `VITE_API_BASE_URL` | 프론트엔드 개발 환경에서 사용할 백엔드 URL. `frontend/.env.development`에서 관리됩니다. |

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

## 번역 모델 참고

- **한→영**: `Helsinki-NLP/opus-mt-ko-en`
- **영→한**: `facebook/nllb-200-distilled-600M` (언어 태그 `kor_Hang` 사용)
- 최초 실행 시 CTranslate2 int8 포맷으로 변환 후 `data/ct2models/`에 캐시됩니다.
