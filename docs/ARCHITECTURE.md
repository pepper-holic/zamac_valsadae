# 시스템 아키텍처 가이드 (개발자용)

이 저장소 하나에 **서로 독립적으로 배포되는 4개**가 들어있습니다. 코드를 고치기 전에
"이게 어디서 도는 건지"부터 확인하세요 — 예를 들어 `server/`를 고치고 `website/`를
배포하면 아무 일도 안 일어납니다(둘은 완전히 다른 배포 절차입니다).

## 1. 전체 그림

```
사용자 PC (로컬, 각자 다른 기기)
┌─────────────────────────────────────────┐
│  installer/ 로 만든 .exe 또는 install.bat│
│  ┌───────────┐        ┌───────────────┐ │
│  │ frontend/ │◄──────►│   backend/    │ │
│  │ (React UI,│  HTTP  │  (FastAPI,    │ │
│  │  빌드되어 │localhost│   Whisper,    │ │
│  │  backend가│  :8000 │   ffmpeg)     │ │
│  │  직접 서빙)│        │               │ │
│  └───────────┘        └───────┬───────┘ │
│  pywebview 네이티브 창(run.bat)│         │
└─────────────────────────────────┼─────────┘
                                   │ 로그인 시에만, 번역/AI검수 요청
                                   │ (Authorization: Bearer <Supabase JWT>)
                                   ▼
오라클 클라우드 VM (168.110.107.78) — 둘 다 이 VM 하나에 같이 떠 있음, 완전히 별개
┌────────────────────────────┐   ┌─────────────────────────────┐
│  server/  (릴레이 API)      │   │  website/  (마케팅 사이트)    │
│  systemd: relay.service     │   │  nginx 정적 파일 서빙          │
│  /opt/relay, 파이썬 프로세스  │   │  /var/www/website, 프로세스 없음│
│  168-110-107-78.nip.io      │   │  site.168-110-107-78.nip.io  │
│  → Supabase JWT 검증          │   └─────────────────────────────┘
│  → OpenAI/Gemini 대리 호출    │
└────────────────────────────┘
                │
                ▼
        Supabase (외부, 인증만 담당 — 이메일/비번, JWT 발급)
```

**핵심**: `frontend/`+`backend/`는 로그인 없이도 완전히 동작하는 로컬 전용 앱입니다.
`server/`는 "로그인한 사용자가 API 키 없이 번역 쓰게 해주는" 선택적 클라우드 경로일
뿐입니다. `website/`는 이 앱과 코드 한 줄도 공유하지 않는 별개의 정적 사이트입니다.

## 2. 컴포넌트별 상세

### 2.1 `backend/` — 로컬 FastAPI 서버

- `127.0.0.1:8000`에만 바인딩(`backend/app/desktop.py`) — **원격 노출 없음, 인증 없음**이
  설계 전제입니다. 이 앱을 인터넷에 노출하는 변경은 절대 하지 마세요.
- 전사: `faster-whisper`(CTranslate2). CUDA GPU 자동 감지, 실패 시 CPU로 자동 폴백.
- 번역: 로컬 NLLB 모델 또는 API 엔진(`translation_service.get_translator`) — 로그인
  상태면 자동으로 `server/` 릴레이를 거치고, 아니면 `TRANSLATION_API_KEY` 직접 사용.
- 자막 번인 렌더링: `render_service.py`가 ffmpeg를 subprocess로 호출 (커맨드는 리스트
  인자, `shell=True` 없음 — 인젝션 안전).
- 저장: `project_store.py` — DB 없이 `data/projects/<uuid>/project.json` 파일 기반.
  **동시성 규칙은 4절 참고 — 반드시 읽으세요.**
- `run.bat`이 켜면 브라우저 탭이 아니라 `pywebview` 기반 네이티브 창이 뜹니다(백그라운드는
  여전히 이 FastAPI 서버).

### 2.2 `frontend/` — React + Vite UI

- `backend/`가 서빙하는 정적 빌드 산출물. 개발 중엔 Vite dev 서버(`:5173`)가 `backend/`
  (`:8000`)로 프록시.
- `src/api/client.ts` — 모든 API 호출이 `apiFetch()` 래퍼(타임아웃 포함, 기본 30초·업로드
  10분)를 거칩니다. 새 API 호출 추가 시 이 패턴을 따르세요.
- `src/hooks/useAuth.ts` — Supabase 세션을 구독하고, 로그인/로그아웃 시 백엔드
  `/auth/session`에 토큰을 동기화합니다.
- 테스트: Vitest + React Testing Library, 순수 로직/훅 위주(`npm run test`).

### 2.3 `server/` — 클라우드 릴레이 (오라클 VM)

- `POST /v1/chat/completions`: Supabase JWT 검증(`app/auth.py`, JWKS 우선·HS256 폴백) →
  통과하면 서버가 보관한 OpenAI/Gemini 키로 대리 호출. 클라이언트는 자기 API 키를
  절대 안 가집니다.
- `app/rate_limit.py`: 계정당 분당 요청 수 제한(기본 20, `CHAT_RATE_LIMIT_PER_MINUTE`) +
  요청 바디 크기 제한(기본 300KB, `CHAT_MAX_BODY_BYTES`). **단일 프로세스 메모리 상태라서
  전제 조건은 "uvicorn 워커 1개"** — `--workers` 옵션을 늘리면 사용자마다 다른 프로세스로
  갈 수 있어 이 제한이 무력화됩니다. `relay.service`에 워커 수를 추가하기 전에 이 부분을
  Redis 등 공유 저장소 기반으로 바꿔야 합니다.
- `.env`(실제 키, Supabase 시크릿)는 배포 스크립트가 절대 건드리지 않습니다 — 서버에서
  수동으로만 관리(`server/.env.example` 참고).
- 지금 실제로는 결제 안 걸린 **Gemini 무료 티어**를 가리키고 있습니다
  (`OPENAI_MODEL_OVERRIDE`로 클라이언트가 보내는 `gpt-4o-mini`를 서버가 바꿔침) — 실제
  OpenAI로 바꾸려면 `.env`의 `OPENAI_API_KEY`/`OPENAI_BASE_URL`만 바꾸면 됩니다(코드 변경
  불필요).

### 2.4 `website/` — 마케팅/서비스 페이지

- `backend/`/`frontend/`와 완전히 독립된 Vite + React Router SPA. 코드/의존성 공유 없음.
- 정적 빌드(`dist/`)를 그대로 nginx가 서빙 — 서버 프로세스가 없어서 `server/`보다 배포가
  훨씬 단순(재시작 개념 자체가 없음).
- 이용약관/개인정보처리방침/가격 정책 등 여러 페이지에 **더미 데이터**가 남아있습니다
  (사업자 등록 전이라 실제 값을 넣을 수 없음) — 각 페이지 상단 배너로 표시됨.

### 2.5 `installer/` — Windows 배포 패키지

- Inno Setup(`installer.iss`)이 소스 코드 + 네이티브 런처(PyInstaller)를 묶어 `.exe`로
  만듭니다. Python/Node/ffmpeg나 AI 모델은 **포함하지 않음** — 최초 실행 시 `run.bat`
  경로로 자동 다운로드.
- `installer.iss`가 루트의 `install.bat`/`install.ps1`/`run.bat`/`env.bat`/
  `kill-servers.bat`을 **고정 상대경로로 직접 참조**합니다 — 이 파일들을 다른 디렉터리로
  옮기면 설치 프로그램 빌드가 깨집니다. (반대로 `deploy/`의 스크립트들은 이 참조가 없어서
  자유롭게 옮길 수 있었습니다.)
- 코드 서명이 안 되어 있어 실행 시 Windows SmartScreen 경고가 뜹니다 — 알려진 상태,
  유료 인증서 구매 전까지는 정상입니다.

## 3. 인증 흐름 (전체 시퀀스)

```
1. 사용자가 앱에서 로그인/회원가입 (AuthModal.tsx)
2. Supabase가 이메일 인증 요구 → 확인 메일 클릭 → JWT(access token) 발급
3. useAuth.ts가 로그인 상태 변화를 감지해 POST /auth/session (backend, 127.0.0.1)
   → auth_state.py가 인메모리로 세션 보관 ("프로세스 하나 = 사용자 한 명" 전제)
4. 번역 요청 시 translation_service.get_translator()가 세션이 있으면
   ApiTranslator(base_url=hosted_relay_base_url, token=session.access_token)로 전환
5. 릴레이(server/)가 Authorization 헤더의 JWT를 검증 → 통과하면 OpenAI/Gemini 대리 호출
```

로그인하지 않아도 3~5단계 없이 기존 로컬 모델/수동 API 키 흐름이 그대로 동작합니다 —
로그인은 선택 사항입니다.

## 4. 데이터 동시성 규칙 (반드시 지킬 것)

`backend/app/services/project_store.py`가 파일 기반 저장소를 관리합니다. **프로젝트를
수정하는 코드는 절대 아래처럼 쓰면 안 됩니다:**

```python
# 절대 이렇게 쓰지 말 것
project = store.get(project_id)
project.items[0].status = "..."
store.save(project)   # 그 사이에 다른 곳(전사 큐, 다른 렌더링 작업 등)이
                       # 같은 프로젝트를 건드렸으면 그 변경을 통째로 덮어씀
```

**항상 이렇게 씁니다:**

```python
# 단일 아이템만 바꿀 때
store.update_item(project_id, item_id, lambda item: setattr(item, "status", "..."))

# 프로젝트 단위(여러 아이템/필드)를 바꿀 때
store.update(project_id, lambda project: ...)
```

`update()`/`update_item()`은 프로젝트별 락을 잡고 "다시 읽기 → 수정 → 저장"을 하나로
묶어서, 오래 걸리는 작업(렌더링·번역·전사) 도중 다른 요청이 같은 프로젝트를 편집해도
서로 덮어쓰지 않습니다. 2026-08-18 감사에서 렌더링/번역 두 경로가 이 규칙을 어기고 있던
게 실제로 발견돼 수정됐습니다(`export.py`, `translate.py`) — 전사 큐(`transcription_queue.py`)는
처음부터 올바른 패턴을 쓰고 있었으니 그걸 참고하세요.

저장 자체(`ProjectStore.save()`)는 temp 파일 + `os.replace`로 원자적입니다 — 중간에
크래시 나도 `project.json`이 반쪽으로 깨지지 않습니다.

## 5. 배포

| 스크립트 | 대상 | 언제 |
|---|---|---|
| `deploy\deploy-website.ps1` | `website/` → `/var/www/website` | 웹사이트 콘텐츠/디자인만 바꿨을 때 |
| `deploy\deploy-relay.ps1` | `server/app` → `/opt/relay/app` | 릴레이 서버 코드를 바꿨을 때. 로컬 테스트 실패 시 배포 안 함, 배포 후 `/healthz` 실패 시 자동 롤백 |
| `deploy\deploy-release.ps1` | 설치 프로그램 + 웹사이트 | 앱 자체(`backend/`/`frontend/`)를 바꿔서 새 설치 프로그램이 필요할 때. 내부적으로 `deploy-website.ps1` 재사용 |

`backend/`/`frontend/`만 고쳤다면 **배포 스크립트가 필요 없습니다** — 사용자가 각자
`install.bat`/설치 프로그램으로 직접 받아서 씁니다(중앙 서버가 코드를 서빙하지 않음).
새 버전을 배포하려면 `deploy-release.ps1`로 새 설치 프로그램(`.exe`)을 만들어 웹사이트
다운로드 링크에 올리는 것뿐입니다 — 완전 자동 업데이트 체계는 없고, 앱 실행 시
`website/public/latest-version.json`을 조회해 "새 버전 있음" 배너만 띄워줍니다
(`frontend/src/hooks/useUpdateCheck.tsx`).

**버전 올릴 때 3곳을 함께 갱신할 것** (자동 동기화 없음, 수동 체크리스트):
1. `installer/installer.iss`의 `MyAppVersion`
2. `frontend/src/version.ts`의 `APP_VERSION`
3. `website/public/latest-version.json`의 `version`/`url`
4. `CHANGELOG.md`에 릴리스 항목 추가

셋 다 `-KeyPath`로 오라클 VM SSH 개인키를 받습니다. 자세한 서버 쪽 구조(systemd, nginx,
백업/롤백 동작)는 `server/README.md`에 있습니다.

## 6. 로컬 개발 환경

| 대상 | 명령 | 기본 포트 |
|---|---|---|
| `backend/` | `cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000` | 8000 |
| `frontend/` | `cd frontend && npm run dev` | 5173 |
| `server/` | `cd server && uv run --with-requirements requirements.txt uvicorn app.main:app --reload` | 8000 (backend와 겹치므로 동시 실행 시 포트 조정) |
| `website/` | `cd website && npm run dev` | 5173 (frontend와 겹치므로 `--port`로 조정) |

## 7. 환경변수 (서비스별)

**`backend/`** (`.env` 또는 시스템 환경변수)

| 변수 | 설명 |
|---|---|
| `TRANSLATION_API_KEY` | 로그인 없이 번역 쓸 때. 로그인 세션 있으면 불필요 |
| `TRANSLATION_API_BASE_URL` | 기본 `https://api.openai.com/v1` |
| `HOSTED_RELAY_BASE_URL` | 로그인 시 사용할 릴레이 주소. 기본 `https://168-110-107-78.nip.io/v1` |
| `APP_DATA_DIR` | 기본 `data/` |
| `WHISPER_MODEL_CACHE_DIR` | 기본 `data/whisper_models/` |
| `HF_TOKEN` | 화자 분리(선택). 없으면 화자 분리 없이 전사만 |
| `MAX_UPLOAD_BYTES` | 업로드 파일 크기 상한, 기본 20GB |
| `RENDER_STALL_TIMEOUT_SECONDS` | ffmpeg가 이 시간(기본 120초) 동안 무응답이면 중단 |

**`server/`** (`.env`, 절대 커밋 금지 — `server/.env.example` 참고)

| 변수 | 설명 |
|---|---|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 실제로 호출할 업스트림. 지금은 Gemini 가리키는 중 |
| `OPENAI_MODEL_OVERRIDE` | 클라이언트가 보내는 모델명을 서버가 바꿔치기(제공자 다를 때) |
| `SUPABASE_URL` / `SUPABASE_JWT_SECRET` | JWT 검증용 (URL 있으면 JWKS 우선, 없으면 HS256 폴백) |
| `CHAT_RATE_LIMIT_PER_MINUTE` | 기본 20, 0이면 비활성화 |
| `CHAT_MAX_BODY_BYTES` | 기본 300000 |
| `CHAT_MAX_COMPLETION_TOKENS` | 기본 1024. 클라이언트가 `max_tokens`를 안 보내도(현재 데스크톱 앱이 그럼) 이 값으로 강제 주입/클램프 — 없으면 응답 길이(=비용)가 무제한 |
| `CHAT_DAILY_LIMIT_PER_USER` | 기본 300. 사용자별 24시간 롤링 요청 수 상한, 0이면 비활성화. 분당 제한만으로는 하루 총 요청 수가 사실상 무제한이라 별도로 둠 |
| `CHAT_DAILY_TOKEN_LIMIT_PER_USER` | 기본 200000. 사용자별 24시간 롤링 누적 토큰(프롬프트+응답) 상한, 응답의 `usage.total_tokens`로 집계, 0이면 비활성화. 요청 "횟수" 상한(`CHAT_DAILY_LIMIT_PER_USER`)은 요청 하나의 프롬프트 크기까지는 안 막아서, 실제 비용 기준 상한은 이 값 |

**`frontend/`** — `frontend/.env.development`에서 `VITE_API_BASE_URL` 관리.
**`website/`** — 별도 필수 환경변수 없음(순수 정적 빌드).

## 8. 테스트

```powershell
cd backend && python -m pytest -q     # 314개
cd server  && python -m pytest -q     # 16개 (venv 없으면 먼저 만들고 requirements.txt 설치)
cd frontend && npm run test           # 66개 (Vitest)
cd website  && npm run test           # App 라우팅
```

새 API 엔드포인트/서비스 로직을 추가하면 최소 성공 경로 + 실패 경로 테스트를 같이
추가하세요 — 이 저장소는 테스트를 신뢰의 기준으로 삼습니다(변경 후 반드시 전체 스위트
통과 확인).

## 9. 더 읽을거리

- [`docs/feature-roadmap.md`](./feature-roadmap.md) — 기능별 "왜 이렇게 만들었는지" 의사결정
  히스토리. 이 문서보다 훨씬 길고 상세하지만, 지금은 지나간 논의가 대부분입니다 — 새로
  뭔가 결정할 때 참고용.
- [`DESIGN.md`](../DESIGN.md) — 데스크톱 앱(`frontend/`)의 색상/타이포그래피/컴포넌트
  디자인 시스템. `website/`는 색상 팔레트를 공유하지만 별도 CSS입니다.
- [`CHANGELOG.md`](../CHANGELOG.md) — 사용자 대상 변경 이력.
- [`server/README.md`](../server/README.md) — 릴레이 서버 배포/운영 상세.
- [`website/README.md`](../website/README.md) — 웹사이트 구조/배포 상세.
