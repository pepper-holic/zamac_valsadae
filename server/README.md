# 릴레이 서버 (로드맵 #44)

로컬 데스크톱 앱의 `ApiTranslator`(`backend/app/services/translation_service.py`)가 OpenAI
직접 호출 대신 이 서버를 거치도록 하는 프록시. `TRANSLATION_API_KEY`/`TRANSLATION_API_BASE_URL`
환경변수를 이 서버 주소로 돌리면 로컬 앱 코드 변경 없이 바로 붙는다.

## 구조

- `GET /healthz` — 인증 불필요, 헬스체크
- `POST /v1/chat/completions` — Supabase JWT(Authorization: Bearer ...) 검증 후 서버가 보관한
  OpenAI 키로 실제 OpenAI를 대신 호출해 응답을 그대로 돌려줌

## 현재 상태 (2026-08-12)

인프라와 코드는 준비됐지만 아래 2가지가 없어서 아직 실제로 동작하지 않는다 (설정 없으면
`/v1/chat/completions`가 각각 501/503로 명확히 응답한다):

- `SUPABASE_JWT_SECRET` — Supabase 프로젝트를 아직 안 만들어서 없음
- `OPENAI_API_KEY` — 아직 발급 전

## 배포 (오라클 클라우드 VM, 168.110.107.78)

```
/opt/relay/            # 이 디렉터리 배포 위치
/opt/relay/.venv/       # python -m venv
systemd unit: relay.service (Restart=on-failure, User=relay)
nginx: 80(→443 예정) → 127.0.0.1:8000 리버스 프록시
도메인: 168-110-107-78.nip.io (소유 도메인 없이 Let's Encrypt 인증서 발급용)
```

## 남은 수동 작업

1. **오라클 클라우드 콘솔** → VCN → Security List에서 80/443 Ingress 룰 추가 (OS 방화벽은 이미
   열어뒀지만 클라우드 레벨 Security List가 별도로 막고 있을 수 있음 — Claude가 OCI API 자격증명이
   없어 대신 열 수 없음)
2. 80 포트가 열리면: `sudo certbot --nginx -d 168-110-107-78.nip.io` 로 TLS 인증서 발급
3. Supabase 프로젝트 생성 후 `SUPABASE_JWT_SECRET`을, OpenAI API 키 발급 후 `OPENAI_API_KEY`를
   서버의 `/opt/relay/.env`에 채우고 `sudo systemctl restart relay`
4. `curl https://168-110-107-78.nip.io/healthz` 로 확인

## 로컬 개발

```bash
cd server
cp .env.example .env   # 값 채우기
uv run --with-requirements requirements.txt uvicorn app.main:app --reload
uv run --with-requirements requirements.txt pytest -q
```
