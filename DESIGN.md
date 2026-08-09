---
name: Zamak_Valsadae
description: Local subtitle transcription/translation/review tool. Dark-capable, single-accent, minimal-chrome SaaS aesthetic.
tokens:
  color:
    accent:
      light: "#7c3aed"
      dark: "#b794f6"
    bg:
      light: "#f7f6f9"
      dark: "#121017"
    surface:
      light: "#ffffff"
      dark: "#1b1922"
    border:
      light: "#e5e4e7"
      dark: "#2e2b38"
    text:
      light: "#4b4555"
      dark: "#b8b3c2"
    textHigh:
      light: "#08060d"
      dark: "#f3f1f6"
    danger:
      light: "#dc2626"
      dark: "#f87171"
    success:
      light: "#16a34a"
      dark: "#4ade80"
    warning:
      light: "#d97706"
      dark: "#fbbf24"
  typography:
    sans: "'Pretendard', system-ui, 'Segoe UI', Roboto, sans-serif"
    mono: "ui-monospace, Consolas, monospace"
  radius:
    sm: "6px"
    md: "8px"
    lg: "12px"
  spacing:
    xs: "4px"
    sm: "8px"
    md: "12px"
    lg: "20px"
---

# Zamak_Valsadae Design System

이 문서는 사람과 AI 코딩 에이전트 모두를 위한 것입니다. 새 화면/컴포넌트를 만들 때
아래 원칙과 토큰을 기준으로 삼으세요 — 매번 감으로 색을 고르지 않기 위한 문서입니다.

## 왜 이런 결정을 내렸나 (Design Rationale)

- **"다크 기본 + 단일 액센트" 공식을 따릅니다.** 2026년 상위 SaaS 제품(Linear=인디고,
  Raycast=레드, Cursor=시안)의 약 75%가 이 공식을 씁니다. 우리는 이미 보라색 액센트
  (`#7c3aed` 라이트 / `#b794f6` 다크)를 쓰고 있으므로 **색상 자체는 바꾸지 않습니다** —
  이미 트렌드에 부합합니다. 팔레트는 거의 무채색(`--bg`/`--surface`/`--border`/`--text`)이고,
  색은 상태·인터랙션·브랜드에만 씁니다(Linear와 동일한 원칙).
- **"당장 필요한 것 외엔 다 지운다" (Linear 철학).** 버튼 하나하나가 같은 무게로 나열되지
  않게, 1차 액션(accent 채움) / 2차 액션(ghost, hover 시에만 배경) / 위험 액션(ghost + hover
  시 danger 색)을 명확히 구분합니다.
- **네이티브 브라우저 기본 스타일이 그대로 남아있는 버튼이 없어야 합니다.** (과거 버그:
  Toolbar의 "새 프로젝트"/"삭제" 버튼이 스타일 클래스 없이 브라우저 기본 회색 버튼으로
  렌더링되고 있었음 — "도구 모음처럼 조잡해 보인다"는 피드백의 실제 원인 중 하나였습니다.)
- **떠 있는(sticky + translucent) 헤더.** Notion/Linear/Vercel 계열 앱들은 상단바를
  `position: sticky` + 반투명 블러로 처리해 콘텐츠 위에 "떠 있는" 느낌을 줍니다.

## 색상

`frontend/src/index.css`의 `:root` / `@media (prefers-color-scheme: dark)`가 단일
소스입니다. 새 색을 하드코딩하지 말고 반드시 CSS 변수를 참조하세요.

| 토큰 | 라이트 | 다크 | 용도 |
|---|---|---|---|
| `--accent` | `#7c3aed` | `#b794f6` | 브랜드/포커스/1차 액션 — 화면당 이 색 하나만 "튀게" 씁니다 |
| `--bg` | `#f7f6f9` | `#121017` | 페이지 배경 |
| `--surface` | `#ffffff` | `#1b1922` | 카드/패널/드롭다운 배경 |
| `--border` | `#e5e4e7` | `#2e2b38` | 구분선, 입력 테두리 |
| `--text` / `--text-h` | `#4b4555` / `#08060d` | `#b8b3c2` / `#f3f1f6` | 본문 / 강조 텍스트 |
| `--code-bg` | `#f4f3ec` | `#1f1d28` | 세그먼트 컨트롤/칩/코드 배경 (surface보다 한 단계 낮은 톤) |
| `--danger` / `--success` / `--warning` | | | 상태 표시 전용, 장식으로 쓰지 않음 |

## 타이포그래피

- **Pretendard** 하나로 통일 (한글 가독성이 최우선 — Geist/Inter 같은 라틴 전용 폰트로
  분리하지 않습니다. 지금 규모의 앱에서 폰트 페어링은 득보다 복잡도가 큽니다).
- 타임코드/숫자/모노스페이스 요소는 `--mono` (`ui-monospace, Consolas, monospace`).
- 헤딩(`h1`, `h2`)은 `--text-h` 색상 고정.

## 버튼 위계 (3단계)

1. **1차 액션** — 배경 `var(--accent)`, 흰 텍스트. 화면당 1~2개만 (예: "다운로드",
   활성 세그먼트 탭).
2. **고스트(2차) 액션** — 배경 투명, `hover` 시에만 `var(--code-bg)` 배경. 텍스트는
   `var(--text)` → hover 시 `var(--text-h)`. (`.toolbar-ghost-button` 참고)
3. **위험 액션** — 고스트와 동일하되 hover 시 배경/텍스트가 `var(--danger)` 톤으로.
   기본 상태에서는 다른 버튼과 구분되지 않아야 함 — "삭제"가 항상 빨갛게 눈에 띄면
   오히려 실수 클릭을 유발합니다.

버튼에 클래스를 안 주는 것은 금지 — 반드시 위 세 클래스 중 하나(또는 기존 `.panel-row
button`류 로컬 패턴)를 명시적으로 붙입니다.

## 레이아웃 패턴

- **상단바(Toolbar)**: `position: sticky; top: 0` + 반투명 배경(`backdrop-filter: blur`).
  3구역으로 분리 — 좌(브랜드+워크스페이스 전환) / 중(파일 선택+업로드) / 우(도구 세그먼트
  탭 + 아이콘 버튼). 구역 사이는 `.toolbar-divider`(1px 세로선)로 구분, 같은 무게의
  버튼을 한 줄에 나열하지 않습니다.
- **도구 탭**: 개별 버튼이 아니라 **세그먼트 컨트롤**(`.toolbar-segmented`) — 옅은
  `--code-bg` 배경의 알약 모양 컨테이너 안에 탭들이 들어가고, 활성 탭만 `--surface` 배경
  + `--accent` 텍스트 + 옅은 그림자로 "떠 있는" 것처럼 표시(Raycast/Linear 세그먼트
  컨트롤과 동일한 패턴). 과거처럼 활성 탭에 `--accent` 배경을 꽉 채우지 않습니다 —
  화면당 강조색은 아껴 씁니다.
- **패널(Panel)**: `.panel` 클래스, `var(--surface)` 배경 + `var(--border)` 테두리,
  라운드 `12px`(드롭다운 내부는), `8px`(그 외).
- **3단 작업 영역**: 영상(파형+타임라인) / 세그먼트 리스트 / 상세 편집 패널.

## 안 하기로 한 것

- 폰트 페어링(Geist+Inter 등) — Pretendard 단일 유지, 복잡도 대비 이득 적음.
- 글래스모피즘 전면 적용 — 상단바 sticky 블러 정도만 채택, 카드/패널까지 반투명하게
  만들면 텍스트 대비가 떨어져 가독성(이 앱의 핵심 가치)과 충돌.
- 액센트 색상 교체 — 이미 트렌드에 부합하는 보라색을 유지.
