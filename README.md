# Zamak_Valsadae (자막발사대)

영상/오디오 파일에서 Whisper로 자막을 추출하고, 타임라인에서 싱크를 맞추고, 한↔영 번역을 붙이고, API 키 없이 파일을 주고받는 방식으로 AI 검수를 받을 수 있는 로컬 웹 도구입니다.

## 빠른 시작 (초보자용, Windows)

1. 이 폴더에서 **`install.bat`** 을 더블클릭 — Python/Node.js/ffmpeg가 없으면 자동 설치를 시도하고, 필요한 패키지를 전부 설치합니다. (torch/Whisper/번역 모델 포함, 수 GB — 처음 한 번은 시간이 꽤 걸립니다.)
   - 중간에 "이 창을 닫고 다시 실행해 주세요"라고 나오면, 안내대로 창을 닫고 `install.bat`을 다시 실행하세요 (새로 설치된 프로그램의 PATH를 인식시키기 위함입니다).
2. 설치가 끝나면 **`run.bat`** 을 더블클릭 — 서버가 별도 창에서 실행되고 브라우저가 자동으로 열립니다 (`http://localhost:8000`).
3. 프로그램을 끝내려면 `run.bat`이 띄운 검은 서버 창을 닫으면 됩니다.

이후에는 `run.bat`만 실행하면 됩니다 (`install.bat`은 최초 1회, 또는 의존성이 바뀌었을 때만).

## 요구사항 (수동 설치 시 / 개발자용)

- Python 3.11+ (본 프로젝트는 3.14로 테스트)
- Node.js 20+
- **ffmpeg** — Whisper가 오디오 추출에 사용합니다. `winget install Gyan.FFmpeg` 로 설치 후 새 터미널을 열어야 PATH가 적용됩니다.
- (선택) GPU + CUDA — 없어도 동작하지만, CPU에서 large 모델은 느립니다. 번역은 CTranslate2로 가속되어 CPU에서도 충분히 빠릅니다.

## 개발 모드로 실행 (핫 리로드)

백엔드와 프론트엔드를 각각 별도 포트로 띄워 개발합니다.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt   # openai-whisper, torch, ctranslate2 등 포함 (용량 큼)
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173` 접속 (프론트는 `frontend/.env.development`에 설정된 `http://localhost:8000` 백엔드를 바라봅니다). 프로덕션 빌드(`npm run build`)는 대신 `frontend/.env.development`가 적용되지 않아 같은 오리진(`''`)을 기본값으로 사용하며, 이는 백엔드가 빌드 결과물을 직접 서빙하는 `run.bat` 흐름과 맞습니다.

### 테스트

```bash
cd backend
python -m pytest
```

### 환경변수 (선택 — API 번역/검수 자동화용)

| 변수 | 설명 |
|---|---|
| `TRANSLATION_API_KEY` | 설정 시 번역 엔진에서 "API" 옵션 사용 가능 (OpenAI 호환 chat completions) |
| `TRANSLATION_API_BASE_URL` | 기본값 `https://api.openai.com/v1`. 호환 엔드포인트로 교체 가능 |
| `APP_DATA_DIR` | 업로드/프로젝트/CTranslate2 모델 캐시 저장 위치. 기본값: 프로젝트 루트의 `data/` |

## 사용 흐름

3단 레이아웃: **왼쪽** 비디오 플레이어(타임라인/재생 컨트롤), **가운데** 검수 대상 문장 목록(페이지당 20개), **오른쪽** 선택한 문장 상세 편집.

1. 상단 툴바에서 영상/오디오 업로드
2. **전사**: Whisper 모델 크기(tiny~large-v3) 선택 후 실행 — 실시간 진행률 표시
3. **번역**: 방향(한→영/영→한)과 엔진(로컬/API) 선택 후 실행 — 로컬 엔진은 CTranslate2로 가속되어 수십 초 내 완료됩니다
4. **자막 편집**: 가운데 목록에서 문장 클릭 → 오른쪽 패널에서 시작/종료 시간, 원문, 번역문 수정(자동 저장), 잘못된 문장은 삭제 가능
5. **내보내기**: SRT/VTT/JSON 다운로드
6. **AI 검수**: 검수 패키지(JSON) 다운로드 → Claude/ChatGPT 등에 직접 업로드해 검수 요청 → 결과 파일을 다시 업로드하면 세그먼트별 변경사항이 표시되고, "반영" 버튼으로 개별 적용 가능. API 키 불필요.

**단축키**: Space(재생/일시정지), ←/→(1초 이동), ↑/↓(이전/다음 문장)

## 번역 엔진 참고

- **한→영**: `Helsinki-NLP/opus-mt-ko-en` (직접 양방향 모델)
- **영→한**: `facebook/nllb-200-distilled-600M` (다국어 모델, 언어 태그 `kor_Hang` 사용)
- 둘 다 최초 실행 시 CTranslate2 int8 포맷으로 자동 변환되어 `data/ct2models/`에 캐시되며, 이후 실행은 훨씬 빠릅니다.
