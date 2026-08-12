# 릴레이 서버 (로드맵 #44)

로컬 데스크톱 앱의 `ApiTranslator`(`backend/app/services/translation_service.py`)가 OpenAI
직접 호출 대신 이 서버를 거치도록 하는 프록시. `TRANSLATION_API_KEY`/`TRANSLATION_API_BASE_URL`
환경변수를 이 서버 주소로 돌리면 로컬 앱 코드 변경 없이 바로 붙는다.

## 구조

- `GET /healthz` — 인증 불필요, 헬스체크
- `POST /v1/chat/completions` — Supabase JWT(Authorization: Bearer ...) 검증 후 서버가 보관한
  OpenAI 키로 실제 OpenAI를 대신 호출해 응답을 그대로 돌려줌

## 현재 상태 (2026-08-12)

Supabase 프로젝트 생성 완료, `SUPABASE_JWT_SECRET` 설정 완료 — JWT 검증까지 실제로 동작
확인됨(유효한 서명의 토큰으로 호출하면 인증을 통과하고 다음 단계인 OpenAI 호출까지 감).
남은 건 `OPENAI_API_KEY` 뿐 — 없는 동안은 `/v1/chat/completions`가 503을 반환한다.

## 배포 (오라클 클라우드 VM, 168.110.107.78)

```
/opt/relay/            # 이 디렉터리 배포 위치
/opt/relay/.venv/       # python -m venv
systemd unit: relay.service (Restart=on-failure, User=relay)
nginx: 80(→443 예정) → 127.0.0.1:8000 리버스 프록시
도메인: 168-110-107-78.nip.io (소유 도메인 없이 Let's Encrypt 인증서 발급용)
```

## 남은 수동 작업

1. ~~오라클 클라우드 콘솔 → VCN → Security List에서 80/443 Ingress 룰 추가~~ 완료 (2026-08-12)
2. ~~`certbot --nginx`로 TLS 인증서 발급~~ 완료 (2026-08-12, 168-110-107-78.nip.io, 2026-11-10 만료
   전 자동 갱신 설정됨)
3. ~~Supabase 프로젝트 생성 후 `SUPABASE_JWT_SECRET` 설정~~ 완료 (2026-08-12) — HS256 서명
   토큰으로 실제 검증 통과 확인됨(`sub`가 곧 사용자 id)
4. OpenAI API 키 발급 후 `OPENAI_API_KEY`를 `/opt/relay/.env`에 채우고
   `sudo systemctl restart relay` — 이것만 하면 end-to-end 완성
5. `curl https://168-110-107-78.nip.io/healthz` 로 확인 (지금도 200 OK)

## 같은 VM에 호스팅 중인 다른 것: `website/` (로드맵 #42)

`website/`(Vite + React SPA)의 빌드 산출물(`website/dist`)도 이 VM에 정적 파일로 같이 올라가
있다. 배포 절차(수동, 스크립트화 안 됨):

```bash
cd website && npm run build
tar -czf /tmp/website-dist.tar.gz -C dist .
scp -i <key> /tmp/website-dist.tar.gz opc@168.110.107.78:/tmp/
ssh -i <key> opc@168.110.107.78
  sudo rm -rf /var/www/website/*
  sudo tar -xzf /tmp/website-dist.tar.gz -C /var/www/website
  sudo chown -R nginx:nginx /var/www/website
  sudo restorecon -Rv /var/www/website
```

nginx 설정은 `deploy/nginx-website.conf`(SPA라 `try_files $uri /index.html` 필요), 접속 주소는
`https://site.168-110-107-78.nip.io` (certbot으로 별도 인증서 발급, `168-110-107-78.nip.io`와는
다른 서브도메인이라 인증서도 따로 필요했음). 소유 도메인이 정해지면 nginx `server_name`과
`frontend/src/components/Toolbar.tsx`/`AboutModal.tsx`의 `WEBSITE_URL`을 교체.

## 로컬 개발

```bash
cd server
cp .env.example .env   # 값 채우기
uv run --with-requirements requirements.txt uvicorn app.main:app --reload
uv run --with-requirements requirements.txt pytest -q
```
