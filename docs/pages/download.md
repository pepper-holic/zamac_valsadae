# 다운로드

## Windows

지금 바로 사용 가능합니다.

- 설치 프로그램: `installer/installer.iss`(Inno Setup)로 빌드한 `.exe` — 관리자 권한 불필요,
  시작 메뉴/바탕화면 아이콘 생성.
- 코드 서명이 안 되어 있어 실행 시 Windows SmartScreen 경고가 뜹니다 — "추가 정보 → 실행"으로
  진행하세요. (해소하려면 코드 서명 인증서 필요 — [T.B.D], 로드맵 #29 참고)
- 또는 `install.bat` + `run.bat`으로 포터블 방식 실행 (Python/Node/ffmpeg를 프로젝트 폴더
  안에 격리 설치, 시스템 PATH 변경 없음).

**다운로드 링크**: [T.B.D — 실제 배포 시 `installer/dist/Zamak_Valsadae_Setup.exe`를 어디에
호스팅할지 확정 필요(예: GitHub Releases, 자체 서버)]

## macOS

[T.B.D — 아직 macOS용 빌드가 없습니다. faster-whisper/CTranslate2/ffmpeg의 macOS 지원 자체는
가능하나, 포터블 런타임 스크립트(`install.bat` 상당)와 macOS용 패키징(.dmg 등)을 별도로
만들어야 합니다.]

## Ubuntu / Linux

[T.B.D — 아직 Linux용 빌드가 없습니다.]

## 시스템 요구사항 (Windows 기준)

- 디스크 여유 공간: 수 GB (Python/Node/ffmpeg 런타임 + Whisper 모델 캐시)
- 인터넷 연결: 최초 설치 및 모델 최초 다운로드 시 필요, 이후에는 오프라인 사용 가능
- GPU: 없어도 동작(CPU 추론) — 다만 모델 크기가 클수록 느림, 자세한 내용은 앱 내 도움말의
  Whisper 모델 크기별 성능 표 참고
