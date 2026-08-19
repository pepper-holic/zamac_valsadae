# 서드파티 라이선스 고지

이 저장소 자체는 `LICENSE`에 명시된 대로 비공개(All rights reserved)이지만, 앱을 실행하려면
아래 오픈소스 구성요소들이 함께 배포/설치됩니다. 각 구성요소는 원 저작권자의 라이선스를
그대로 따릅니다 — 이 문서는 배포 시 고지 의무를 지키기 위한 목록입니다.

빌드 도구(Vitest, oxlint, pytest 등 개발 전용 의존성)는 최종 사용자에게 배포되지 않으므로
목록에서 제외했습니다.

## 백엔드 (Python)

| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | MIT | |
| [pyannote-audio](https://github.com/pyannote/pyannote-audio) | MIT | 화자 분리(선택 기능). 실제 모델(`pyannote/speaker-diarization-3.1`)은 HuggingFace 게이트 모델이라 별도로 이용약관 동의가 필요합니다 — [HelpModal.tsx](frontend/src/components/HelpModal.tsx) 참고 |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | 데스크톱 네이티브 창(`run.bat`) |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | |
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | |
| [PyJWT](https://github.com/jpadilla/pyjwt) | MIT | `server/`에서 사용 |

## 프론트엔드 (JavaScript/TypeScript)

| 구성요소 | 라이선스 |
|---|---|
| [React / React DOM](https://github.com/facebook/react) | MIT |
| [Vite](https://github.com/vitejs/vite) | MIT |
| [@supabase/supabase-js](https://github.com/supabase/supabase-js) | MIT |

## ffmpeg — 별도 주의 필요 (GPLv3)

`install.ps1`이 `runtime/`에 내려받는 ffmpeg 빌드는 [gyan.dev의 `ffmpeg-release-essentials`
빌드](https://www.gyan.dev/ffmpeg/builds/)(소스: <https://github.com/GyanD/codexffmpeg>)이며,
**이 빌드는 GPLv3로 배포됩니다**(gyan.dev의 모든 빌드가 64비트 정적 빌드 + GPLv3).

이 앱은 `ffmpeg.exe`를 수정 없이 그대로 별도 서브프로세스로만 호출합니다
(`backend/app/services/render_service.py`, `subprocess` 리스트 인자 방식 — 앱 코드와 정적/동적
링크되지 않음). 이런 "별도 프로세스 호출" 형태는 일반적으로 GPL의 "mere aggregation"(단순 병존)
범주로 취급되어 호출하는 애플리케이션 자체를 GPL로 전환할 의무는 없다고 보는 해석이 많지만,
**이는 법률 자문이 필요한 영역이며 이 문서가 법적 결론을 대신하지 않습니다.**

더 보수적으로 가고 싶다면 `install.ps1`의 `$FfmpegDownloadUrl`을 gyan.dev가 함께 제공하는
LGPL 빌드("shared" 계열, 특허/카피레프트 관련 코덱을 제외한 구성)로 교체하는 방법이 있습니다 —
이번 작업에서는 코드를 바꾸지 않고 선택지로만 남겨둡니다.
