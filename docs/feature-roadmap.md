# 기능 로드맵 — 전사/번역 도구 개선안

웹 리서치(WhisperX, subtitle-translator, Netflix Timed Text Style Guide 등)를 바탕으로
현재 구조(faster-whisper 로컬 전사 → CTranslate2 ko↔en 번역 → 세그먼트 검수 → SRT/VTT/JSON 내보내기)에
붙일 수 있는 기능들의 상세 실행 계획입니다. 우선순위 순으로 정리했습니다.

## 우선순위 요약

| # | 기능 | 임팩트 | 난이도 | 주요 신규 의존성 |
|---|---|---|---|---|
| 1 | 화자 분리 | 높음 | 중 | `pyannote-audio` |
| 2 | CPS/CPL 가독성 검사 | 높음 | 낮음 | 없음 |
| 3 | 용어집(Glossary) | 높음 | 낮음 | 없음 |
| 4 | Forced Alignment | 중 | 중 | `wav2vec2` (또는 CTranslate2 alignment) |
| 5 | ASS/TTML 내보내기 | 중 | 낮음 | 없음 |
| 6 | 번역 메모리(TM) | 중 | 낮음 | 없음 |
| 7 | 다국어 확장 | 낮음 | 높음 | 언어별 번역 모델 |
| 8 | VAD 무음 스킵 | 낮음 | 낮음 | `silero-vad` (faster-whisper 내장 옵션 활용 가능) |

---

## 1. 화자 분리 (Speaker Diarization)

**목표**: 세그먼트마다 `speaker` 라벨(`SPEAKER_00`, `SPEAKER_01`…)을 붙여 인터뷰/회의 영상에서 누가 말했는지 구분.

**변경 범위**
- `backend/requirements.txt`: `pyannote-audio` 추가 (HuggingFace 토큰 필요 — `.env`에 `HF_TOKEN` 항목 추가, `core/config.py`의 `Settings`에 `hf_token` 필드 추가)
- `backend/app/services/diarization_service.py` (신규): `pyannote.audio.Pipeline`을 로드해 오디오에서 화자 구간을 추출하는 `diarize(media_path) -> list[SpeakerSegment]` 함수. `whisper_service._get_model`과 동일한 캐시 패턴(`_PIPELINE_CACHE`) 사용.
- `backend/app/models/schemas.py`: `Segment`에 `speaker: str | None = None` 필드 추가.
- `backend/app/services/whisper_service.py` 또는 `transcribe.py`의 `_run_transcription`: 전사 완료 후 화자 분리 결과와 세그먼트를 시간 겹침 기준으로 매칭하는 `_assign_speakers(segments, speaker_turns)` 헬퍼 추가.
- `backend/app/api/transcribe.py`: `TranscribeRequest`에 `diarize: bool = False` 옵션 추가 (무거운 모델이라 기본 off, 필요할 때만 켜기).
- `frontend/src/components/SegmentList.tsx`, `SegmentDetailPanel.tsx`: 화자 라벨 표시 및 편집 UI.
- `frontend/src/api/types.ts`: `Segment.speaker` 타입 추가.

**주의점**
- pyannote 모델은 HuggingFace 게이트 모델이라 최초 사용 시 토큰 동의 절차 필요 → README에 안내 추가.
- CPU 추론 시 전사보다 느릴 수 있음 → 별도 진행 단계(`stage: "diarizing"`)로 노출.

**테스트**: `backend/tests/test_diarization_service.py` — 화자 구간과 세그먼트 매칭 로직을 목(mock) 파이프라인으로 단위 테스트 (실제 모델 다운로드 없이).

---

## 2. CPS/CPL 가독성 자동 검사

**목표**: Netflix 기준(17 CPS 권장, 줄당 42자, 세그먼트 최소 5/6초~최대 7초)을 참고해 자막이 너무 빠르거나 길면 기존 `quality` 플래그 패턴처럼 경고 표시.

**변경 범위**
- `backend/app/models/schemas.py`: `Segment`에 `readability_flag: QualityFlag | None`, `readability_reason: str | None` 추가 (기존 `transcription_quality` 패턴과 동일한 형태).
- `backend/app/services/readability_service.py` (신규):
  ```python
  MAX_CPS = 17
  MAX_CHARS_PER_LINE = 42
  MIN_DURATION_SEC = 5 / 6
  MAX_DURATION_SEC = 7.0

  def assess_readability(segment: Segment, use_translation: bool) -> tuple[str | None, str | None]:
      ...
  ```
  `whisper_service._assess_transcription_quality`와 동일한 리스트-누적 방식으로 구현.
- 적용 시점: 전사 직후(원문 기준)와 번역 직후(번역문 기준) 둘 다 재계산 — `transcribe.py`/`translate.py`의 후처리 단계에서 호출.
- `frontend/src/components/SegmentList.tsx`: 기존 quality 뱃지 옆에 가독성 경고 아이콘 추가.

**설정값**: CPS/CPL 기준을 하드코딩하지 않고 `core/config.py`에 상수로 분리해 추후 언어별(한글/영문 CPS 기준이 다름) 조정 가능하게.

**테스트**: `backend/tests/test_readability_service.py` — 경계값(정확히 17 CPS, 42자) 케이스 위주 AAA 테스트.

---

## 3. 용어집 (Glossary / Termbase)

**목표**: 프로젝트별 고유명사·전문용어를 등록해두고 번역 시 일관되게 적용.

**변경 범위**
- `backend/app/models/schemas.py`: `Project`에 `glossary: dict[str, str] = Field(default_factory=dict)` 추가 (원문 용어 → 지정 번역).
- `backend/app/api/projects.py`: `PUT /projects/{id}/glossary` 엔드포인트 추가 (glossary 저장).
- `backend/app/services/translation_service.py`:
  - `ApiTranslator.translate`: 프롬프트에 용어집을 few-shot 형태로 주입 (`"다음 용어는 항상 이렇게 번역: {term} -> {translation}"`).
  - `LocalTranslator`: 로컬 모델은 프롬프트 주입이 안 되므로, 번역 후 후처리로 원문에 등장한 용어를 강제 치환하는 `_apply_glossary(translated_text, glossary)` 헬퍼 적용 (완전한 일관성은 API 엔진에서만 보장, 로컬은 best-effort로 문서화).
- `frontend/src/components/TranslationPanel.tsx`: 용어집 편집 UI(테이블 형태: 원문/번역 쌍 추가·삭제).

**테스트**: `backend/tests/test_translation_service.py`에 용어집 적용 케이스 추가.

---

## 4. Forced Alignment (단어 타임스탬프 정밀화)

**목표**: 현재도 `word_timestamps=True`로 단어 단위 타임스탬프를 얻고 있지만, wav2vec2 기반 forced alignment를 얹으면 정확도가 더 올라감(WhisperX 벤치마크 기준 약 85%→93%).

**변경 범위**
- `backend/requirements.txt`: alignment용 경량 모델 의존성 검토 (`ctc-forced-aligner` 또는 `wav2vec2` 계열 — 한국어/영어 지원 여부 사전 확인 필요).
- `backend/app/services/alignment_service.py` (신규): `align(media_path, segments) -> list[Segment]` — 세그먼트 텍스트와 오디오를 다시 정렬해 `start`/`end` 보정.
- `whisper_service.transcribe`에 `on_stage("aligning")` 단계 추가, `should_cancel` 체크 지점 유지.

**주의점**: 이 항목은 리서치 단계에서 한국어 지원 모델 검증이 먼저 필요합니다(영어 대비 한국어 forced-alignment 모델 생태계가 얕음). 우선순위 3(용어집)까지 먼저 붙인 뒤 별도 스파이크로 진행 권장.

---

## 5. ASS/TTML 내보내기 추가

**목표**: 현재 SRT/VTT/JSON만 지원 — 방송/OTT 납품(TTML), 스타일링 필요 시(ASS) 요구에 대응.

**변경 범위**
- `backend/app/models/schemas.py`: `ExportFormat`에 `"ass"`, `"ttml"` 추가.
- `backend/app/services/subtitle_format.py`: `to_ass(segments, use_translation)`, `to_ttml(segments, use_translation)` 함수 추가 (`to_srt`/`to_vtt`와 동일한 `_pick_text`/`_format_timestamp` 헬퍼 재사용; TTML은 프레임레이트 개념이 없으므로 별도 타임코드 포맷 필요).
- `backend/app/api/export.py`: `_CONTENT_TYPES`에 두 포맷 추가, 분기 로직 확장.
- `frontend/src/components/ExportPanel.tsx`: 포맷 선택 옵션 추가.

**테스트**: `backend/tests/test_subtitle_format.py`에 두 포맷 라운드트립(생성 → 파싱 검증) 케이스 추가.

---

## 6. 번역 메모리 (Translation Memory)

**목표**: 동일/유사 문장을 다시 번역하지 않고 재사용 — 반복 편집 프로젝트에서 속도·일관성 개선.

**변경 범위**
- `backend/app/services/project_store.py`: 프로젝트 저장 디렉토리 아래 `translation_memory.json` (원문 → 번역 매핑) 관리 함수 추가.
- `backend/app/services/translation_service.py`의 `translate_segments`: 배치 전송 전에 TM 조회, 정확히 일치하는 원문은 API/로컬 모델 호출 없이 즉시 재사용 (완전 일치만 우선 지원 — 유사도 매칭은 범위 밖으로 명시).
- 번역 완료 후 새로 번역된 쌍을 TM에 append.

**테스트**: TM 히트/미스 케이스, 동시성(같은 프로젝트 여러 번역 실행) 케이스.

---

## 7. 다국어 확장

**목표**: 현재 ko↔en 고정 방향을 다른 언어 쌍으로 확장할지 검토.

**변경 범위**
- `TranslationDirection` Literal 확장, `_LOCAL_MODEL_CONFIGS`에 언어쌍별 모델 추가 (NLLB-200은 이미 다국어 지원이라 target_prefix만 추가하면 확장 용이).
- Whisper는 이미 다국어 모델이므로 전사 쪽 변경 불필요.

**주의점**: 언어쌍마다 모델 캐시 용량 증가(`data/ct2models/`) — README의 디스크 사용량 안내 갱신 필요. **우선순위가 명확한 실제 사용자 요구가 있을 때 착수 권장** (현재는 낮은 우선순위).

---

## 8. VAD 무음 스킵

**목표**: 무음/배경음 구간을 전사 전에 잘라내 처리 속도 개선.

**변경 범위**
- `backend/app/services/whisper_service.py`의 `transcribe()`: faster-whisper는 내장 VAD 옵션(`vad_filter=True`)을 지원하므로 `active_model.transcribe(..., vad_filter=True)`로 우선 시도 — 별도 의존성 없이 가능.
- 효과 측정 후 필요하면 `silero-vad` 별도 통합 검토.

**테스트**: 무음 구간이 포함된 샘플 오디오로 세그먼트 수/처리 시간 비교.

---

## 9~14. 편의 기능 (올인원 툴 강화, 2026-08-08 추가)

Subtitle Edit/Aegisub/Descript 등 외부 툴 조사 결과를 바탕으로, "이 앱 하나로 정밀 편집까지 끝낼 수 있는가"
관점에서 뽑은 UX 갭입니다. 상태 체크박스는 진행하며 갱신합니다.

| # | 기능 | 상태 |
|---|---|---|
| 9 | 문장 분할/병합 | [x] 완료 (2026-08-08) |
| 10 | 찾기/바꾸기 (원문·번역 전체) | [x] 완료 (2026-08-08) |
| 11 | 타임라인 드래그로 시작/종료 조절 (+ 파형 표시) | [x] 완료 (2026-08-08) |
| 12 | 자막 미리보기 오버레이 | [x] 완료 (2026-08-08) |
| 13 | 업로드 드래그 앤 드롭 | [x] 완료 (2026-08-08) |
| 14 | 다중 선택 일괄 작업 (검토완료/삭제) | [x] 완료 (2026-08-08) |

### 9. 문장 분할/병합

- `backend/app/api/segments.py`: `POST /projects/{id}/segments/{segment_id}/split` (body: `split_at_ratio` 또는 `split_at_time` — 시간 기준으로 텍스트를 앞/뒤 절반으로 나누고 두 개의 새 세그먼트로 교체), `POST /projects/{id}/segments/merge` (body: `segment_ids: list[str]` — 시간순 인접 세그먼트들을 하나로 합침, 텍스트는 공백으로 연결).
- `frontend/src/components/SegmentDetailPanel.tsx`: "분할"/"병합" 버튼 추가.

### 10. 찾기/바꾸기

- `backend/app/api/segments.py`: `POST /projects/{id}/segments/find-replace` (body: `field: "text"|"translation"`, `find: str`, `replace: str`) — 일치하는 모든 세그먼트를 한 번에 치환하고 변경된 세그먼트 목록을 반환.
- `frontend`: 문장 목록 상단에 찾기/바꾸기 바 추가, 미리보기(몇 건 매치) 후 일괄 적용.

### 11. 타임라인 드래그 편집 (+ 파형)

- `frontend/src/components/VideoStage.tsx`: 세그먼트 마커 좌우 끝에 드래그 핸들 추가, 드래그 종료 시 `updateSegment` 호출.
- 파형은 Web Audio API(`decodeAudioData`)로 피크를 뽑아 canvas에 그리는 방식 — 백엔드 변경 불필요.

### 12. 자막 미리보기 오버레이

- `frontend/src/components/VideoStage.tsx`: 현재 재생 시간이 포함된 세그먼트의 텍스트/번역을 비디오 위에 오버레이로 표시.

### 13. 업로드 드래그 앤 드롭

- `frontend/src/components/Toolbar.tsx`: 업로드 영역에 `onDragOver`/`onDrop` 핸들러 추가.

### 14. 다중 선택 일괄 작업

- `frontend/src/components/SegmentList.tsx`: 체크박스로 다중 선택 → "선택 항목 검토완료로 표시" / "선택 항목 삭제" 버튼. 기존 `updateSegment`/`deleteSegment`를 반복 호출.

## 4. Forced Alignment — 리서치 스파이크 결과 (2026-08-08)

한국어 지원 여부를 웹에서 조사한 결과, 실제 코드 착수가 가능한 후보를 확인했습니다.

- **[`ctc-forced-aligner`](https://github.com/MahmoudAshraf97/ctc-forced-aligner)** (PyPI 배포) — Meta의 MMS(Massively Multilingual Speech) CTC 모델을 사용해 1000개 이상 언어(한국어 포함)의 텍스트-오디오 강제 정렬을 지원. 별도 언어별 모델 학습 없이 바로 사용 가능해 가장 유력한 후보입니다.
- 대안으로 한국어 전용 `w11wo/wav2vec2-xls-r-300m-korean` (HuggingFace) 같은 모델도 있으나, forced-alignment 전용으로 검증된 것은 아니라서 CTC 정렬 파이프라인에 직접 연결하려면 추가 작업이 필요합니다.
- Montreal Forced Aligner(MFA) 계열은 전통적으로 강력하지만 한국어 발음 사전(G2P) 별도 구축이 필요해 진입장벽이 더 높습니다.

**결론 및 다음 단계**: `ctc-forced-aligner`가 가장 적은 추가 작업으로 한국어를 지원하므로, 실제 구현 시 이 라이브러리를 `alignment_service.py`의 기반으로 채택하는 것을 권장합니다. 다만 아직 다음이 검증되지 않았습니다 — (1) 실제 한국어 샘플에서의 정렬 정확도, (2) faster-whisper 세그먼트 출력과의 결합 방식, (3) CPU 추론 속도. 이 항목은 계획대로 **별도 스파이크(실제 샘플로 정확도/속도 검증)를 먼저 진행한 뒤 착수**하기로 결정했습니다 — 이번 라운드에서는 코드를 붙이지 않았습니다.

## 권장 진행 순서

1. **CPS/CPL 검사(#2)** + **VAD 스킵(#8)** — 기존 패턴 재사용, 신규 의존성 없음, 즉시 착수 가능.
2. **용어집(#3)** — API 번역 엔진부터 먼저 지원.
3. **ASS/TTML 내보내기(#5)** — `subtitle_format.py` 확장만으로 완결.
4. **화자 분리(#1)** — 별도 스파이크로 pyannote 모델 검증 후 진행.
5. **번역 메모리(#6)** → **Forced Alignment(#4)** → **다국어 확장(#7)** 순.

---

## 15~18. 서비스화 대비 개선 (2026-08-09 추가)

경쟁 서비스(Vrew 등) 대비 포지셔닝 논의 결과, "번역 품질 검수 + 원클릭 편의성"을 핵심 차별점으로 잡기로
했습니다. 이를 뒷받침하려면 자막 스타일 편집(시각적 표현)과 편집 안전장치(Undo)가 서비스화 전 최우선
과제입니다. 상태 체크박스는 진행하며 갱신합니다.

| # | 기능 | 임팩트 | 난이도 | 상태 |
|---|---|---|---|---|
| 15 | Undo/Redo (편집 안전장치) | 높음 | 낮음 | [x] 완료 (2026-08-09) |
| 16 | 자막 스타일 편집기 + 실시간 미리보기 | 높음 | 중 | [x] 완료 (2026-08-09) |
| 17 | 자막 번인 렌더링 + 영상 내보내기 | 중 | 높음 | [x] 완료 (2026-08-09) |
| 18 | 온보딩 + 진행률 UX | 중 | 낮음 | [x] 완료 (2026-08-09, 샘플 프로젝트 버튼 제외) |

### 15. Undo/Redo

**목표**: split/merge/delete/bulk-delete/텍스트 수정이 즉시 반영되는 현재 구조에서, 실수 편집을 1~n단계
되돌릴 수 있게 함.

**변경 범위**
- `backend/app/services/project_store.py`: 아이템별 세그먼트 스냅샷 스택(`_history: dict[item_id, list[list[Segment]]]`, 최대 20개)을 관리하는 `push_history(item_id, segments)` / `undo(item_id) -> list[Segment] | None` / `redo(item_id) -> list[Segment] | None` 추가. 세그먼트를 바꾸는 모든 경로(update/delete/split/merge/find-replace/bulk)가 변경 직전 상태를 push.
- `backend/app/api/segments.py`: `POST /projects/{id}/items/{item_id}/undo`, `POST /projects/{id}/items/{item_id}/redo` 엔드포인트 추가 — 갱신된 세그먼트 목록을 반환.
- `frontend/src/api/client.ts`, `types.ts`: `undoItem`/`redoItem` 함수 추가.
- `frontend/src/App.tsx`: `Ctrl+Z`/`Ctrl+Shift+Z` 키보드 단축키(기존 `handleKeyDown`에 분기 추가), 세그먼트 목록 갱신은 기존 `setProject` 패턴 재사용.
- `frontend/src/components/Toolbar.tsx` 또는 `SegmentList.tsx`: 되돌리기/다시하기 버튼 (히스토리 없으면 비활성화).

**주의점**: 스냅샷은 세그먼트 배열 전체를 복사하는 단순한 방식으로 시작 — 메모리 사용량이 문제 되면 diff 기반으로 전환 검토(지금 규모에선 불필요).

**테스트**: `backend/tests/test_project_store.py` — push 후 undo/redo 반복, 스택 최대치 초과 시 가장 오래된 항목 제거 검증.

### 16. 자막 스타일 편집기 + 실시간 미리보기

**목표**: 폰트/크기/색상/외곽선/배경/위치와 페이드·하이라이트 효과를 프로젝트 단위로 설정하고, 12번(자막
미리보기 오버레이)에 바로 반영해서 결과를 보면서 편집.

**변경 범위**
- `backend/app/models/schemas.py`: `SubtitleStyle` 모델 신규 추가 —
  ```python
  class SubtitleStyle(BaseModel):
      font_family: str = "Pretendard"
      font_size: int = 32
      font_weight: Literal["normal", "bold"] = "bold"
      color: str = "#FFFFFF"
      outline_color: str = "#000000"
      outline_width: int = 2
      background: str | None = None
      position: Literal["bottom", "top", "custom"] = "bottom"
      fade_in_ms: int = 0
      fade_out_ms: int = 0
      karaoke_highlight: bool = False
  ```
  `Project`에 `subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)`, `style_presets: list[NamedSubtitleStyle] = Field(default_factory=list)` (프리셋은 `name: str` + `SubtitleStyle` 조합) 추가.
- `backend/app/api/projects.py`: `PUT /projects/{id}/style` (현재 스타일 갱신), `POST /projects/{id}/style/presets` / `DELETE /projects/{id}/style/presets/{name}` (프리셋 저장·삭제·적용은 클라이언트가 `PUT /style`로 값 복사).
- `backend/app/services/project_store.py`: 위 필드 영속화만 추가(기존 저장 로직 재사용).
- `frontend/src/components/`: 신규 `SubtitleStylePanel.tsx` — 폰트/크기/색상 피커, 위치 라디오, 효과 토글, 프리셋 드롭다운(저장/불러오기). Toolbar의 메뉴 항목으로 노출(ExportPanel/HelpModal과 같은 패턴).
- `frontend/src/components/VideoStage.tsx`: 기존 자막 오버레이(12번 항목) 렌더링에 `project.subtitle_style`을 인라인 스타일로 적용 (font-family/size/color/text-shadow(외곽선)/background/bottom·top 위치). `fade_in_ms`/`fade_out_ms`는 CSS `transition` + 세그먼트 진입/이탈 시점 계산으로 구현. `karaoke_highlight`는 word-level timestamp(이미 `word_timestamps=True`로 존재)를 이용해 현재 재생 시점까지의 단어만 강조.
- `frontend/src/api/types.ts`, `client.ts`: `SubtitleStyle` 타입, `updateSubtitleStyle`/프리셋 CRUD 함수 추가.

**주의점**: 미리보기는 CSS로만 구현(실제 렌더링 결과와 폰트 렌더러 차이가 있을 수 있음 — 17번 번인 렌더링 시 동일 스타일을 ffmpeg `subtitles`/`ass` 필터에 매핑해야 오차 최소화).

**테스트**: 프론트는 스타일 값 변경 시 오버레이 인라인 스타일이 올바르게 계산되는지 유닛 테스트(순수 함수로 스타일→CSS 변환 로직 분리해서 테스트하기 쉽게 구성). 백엔드는 `test_project_store.py`에 스타일/프리셋 저장·조회 케이스 추가.

### 17. 자막 번인 렌더링 + 영상 내보내기

**목표**: 16번에서 만든 스타일을 실제 영상 파일에 구워서(burn-in) 다운로드 가능하게 함 — 지금 ExportPanel은 자막 파일(SRT/VTT/JSON)만 내보내는 것으로 보이므로, "완성된 영상"을 출력하는 새 경로가 필요.

**변경 범위**
- `backend/requirements.txt`: 시스템 `ffmpeg` 바이너리 의존(README에 설치 안내 추가, Python 패키지는 `ffmpeg-python` 또는 subprocess 직접 호출 중 택1 — 기존 코드 스타일상 subprocess 직접 호출이 일관적).
- `backend/app/services/render_service.py` (신규): `SubtitleStyle` + `segments`를 `subtitle_format.to_ass()`(5번 항목에서 추가 예정인 ASS 포맷)로 변환 → `ffmpeg -i input.mp4 -vf "ass=styled.ass" output.mp4` 형태로 subprocess 실행. `whisper_service`/`translation_service`와 동일한 진행률 콜백 패턴(`progress_reporter.py`) 재사용, `cancellation.py`로 중단 지원.
- `backend/app/api/export.py`: `POST /projects/{id}/items/{item_id}/render` (job 시작, item status를 `"rendering"`으로), `GET`은 기존 상태 폴링 패턴 재사용. 완료 후 결과 파일은 기존 `mediaUrl`과 유사한 경로로 다운로드 제공.
- `frontend/src/components/ExportPanel.tsx`: "영상으로 내보내기(자막 포함)" 버튼 추가, 렌더링 중 진행률 표시(18번 진행률 UX와 공유 컴포넌트로).
- `frontend/src/App.tsx`: 렌더링 중인 아이템도 기존 `ACTIVE_STATUSES` 폴링 로직에 `"rendering"` 추가.

**주의점**: 이 항목이 이번 로드맵 중 공수가 가장 큼 — ffmpeg 설치 여부 확인/에러 처리, 렌더링 시간(영상 길이 비례, 몇 분~십몇 분 소요 가능)에 대한 사용자 기대치 관리(예상 소요시간 안내) 필요. 16번(스타일 편집기)이 먼저 끝나야 스타일→ASS 매핑이 가능하므로 순서상 16번 다음.

**테스트**: `render_service`의 ASS 생성 부분은 실제 ffmpeg 실행 없이 단위 테스트 가능(스타일 → ASS 문자열 변환 검증). 실제 ffmpeg 호출은 통합 테스트에서 짧은 샘플 영상으로 1건만 검증(CI 시간 고려).

### 18. 온보딩 + 진행률 UX

**목표**: 첫 사용자 경험과 처리 중 상태 피드백을 텍스트 배너 수준에서 격상.

**변경 범위**
- `frontend/src/components/Toolbar.tsx`: 업로드 드롭존(13번에서 이미 구현됨)에 빈 프로젝트일 때 안내 일러스트/문구 강화, "샘플 프로젝트 열기" 버튼(고정 샘플 미디어+자막 데이터를 프로젝트로 복제) 추가 검토.
- `frontend/src/App.tsx`: 현재 `toolbar-warning` 텍스트 배너(전사 대기열, 알 수 없는 세그먼트 ID 경고)를 공용 `ProgressToast.tsx` 컴포넌트로 교체 — 진행률(%)은 faster-whisper 콜백에서 이미 세그먼트 단위 진행 정보를 받고 있다면 그대로 매핑, 없다면 "n/m 파일 처리 중" 수준으로 표시.
- `frontend/src/App.css`: 토스트 등장/소멸 트랜지션(opacity/transform, compositor-friendly 속성만 사용).

**주의점**: 이 항목은 다른 세 항목과 독립적이라 병렬로 진행 가능 — 우선순위상 마지막이지만 일정이 맞으면 15/16번과 동시 진행해도 무방.

**테스트**: 프론트 컴포넌트 테스트(React Testing Library)로 토스트 표시/자동 소멸 타이밍 검증.

## 권장 진행 순서 (15~18)

1. **Undo/Redo(#15)** — 리스크 방지, 다른 항목과 무관하게 즉시 착수.
2. **자막 스타일 편집기(#16)** — 차별화 핵심 기능, 미리보기까지 완성.
3. **자막 번인 렌더링(#17)** — 16번 완료 후 착수(스타일 스키마 의존).
4. **온보딩/진행률 UX(#18)** — 병렬 진행 가능, 일정 여유 있을 때.

---

## 19~22. 경쟁 툴 벤치마킹 + 전사 속도 개선 (2026-08-09 추가)

Vrew / Subtitle Edit / Aegisub / Descript / CapCut·VEED·Kapwing / Maestra·Happy Scribe를
웹 리서치로 조사한 결과를 바탕으로 뽑은 항목입니다. 시각/디자인 관련 항목(스타일 프리셋
갤러리 UI, DESIGN.md, 다크모드 톤 등)은 별도 디자인 산출물(Claude Design 경로 전달 예정)을
반영해 진행하기로 하고, 이 섹션은 **기능적 개발 사항만** 다룹니다.

| # | 기능 | 임팩트 | 난이도 | 참고 벤치마크 | 상태 |
|---|---|---|---|---|---|
| **19** | **Whisper `large-v3-turbo` 모델 옵션 추가 (최우선)** | 높음 | **매우 낮음** | faster-whisper/CTranslate2 자체 지원 | [x] 완료 (2026-08-09) |
| 20 | 필러워드/무음 구간 자동 감지·일괄 제거 | 높음 | 낮음 | Vrew, Descript | [x] 완료 (2026-08-09) |
| 21 | 단어별(word-level) 타임스탬프 저장 | 중간(기반 작업) | 중간 | Vrew, Aegisub 카라오케 | [x] 완료 (2026-08-09) |
| 22 | 텍스트 삭제 시 영상도 함께 잘리는 컷 편집 | 높음(차별화) | 높음 | Vrew, Descript | [x] 완료 (2026-08-09) |

### 19. Whisper `large-v3-turbo` 모델 옵션 추가 (최우선)

**목표**: 전사 속도 개선을 웹 리서치한 결과, 지금 쓰는 faster-whisper(CTranslate2) 파이프라인을
그대로 유지한 채 모델 크기만 `large-v3-turbo`로 추가하면 **large-v3 대비 약 5배 빠르면서
정확도(WER)는 0.3%p 정도만 낮아지는** 것으로 확인됨. 디코더가 32층→4층으로 줄어든 구조라
속도가 크게 개선되지만 여전히 같은 Whisper 계열이라 한국어를 포함한 다국어 지원은 그대로
유지됨. 이미 `_COMPUTE_TYPE = "int8"`, 전체 CPU 스레드 사용 등 CTranslate2 쪽 최적화는
되어 있으므로, 남은 레버는 모델 자체 선택뿐 — 코드 변경이 거의 없어 최우선으로 처리.

**변경 범위**
- `backend/app/core/config.py`: `WHISPER_MODEL_SIZES` 튜플에 `"large-v3-turbo"` 추가.
  faster-whisper의 `download_model()`이 이 모델명을 이미 인식해서 맞는 CTranslate2 변환
  체크포인트를 자동으로 받아오므로 `whisper_service.py` 쪽은 수정 불필요.
- `frontend/src/api/types.ts`: `WHISPER_MODELS` 배열에 `'large-v3-turbo'` 추가해 모델 선택
  드롭다운에 노출.

**주의점**: distil-whisper(영어 전용이라 한국어 미지원)나 NVIDIA Parakeet(한국어 지원
불확실, 엔진 전체 교체 필요)는 리서치 결과 이번 스코프에서 제외 — turbo가 "코드 변경
최소 + 한국어 유지 + 확실한 속도 향상"을 모두 만족하는 유일한 선택지였음.

**테스트**: `backend/tests/test_whisper_service.py`(또는 `test_api.py`의 모델 검증 테스트)에
`"large-v3-turbo"`가 `WHISPER_MODEL_SIZES`에 포함되어 허용되는지, `/models/status`가 이
모델의 캐시 상태를 정상적으로 반환하는지 검증하는 케이스 추가.

### 20. 필러워드/무음 구간 자동 감지·일괄 제거

**목표**: "음", "어", "그니까" 같은 필러워드와 무음 구간을 자동으로 찾아 표시하고, 사용자가
검토 후 일괄 삭제할 수 있게 함. 로드맵 8번(VAD 무음 스킵)과 10번(찾기/바꾸기)의 자연스러운
확장.

**변경 범위**
- `backend/app/core/config.py`: 언어별 필러워드 사전(`FILLER_WORDS_KO`, `FILLER_WORDS_EN`)을
  상수로 분리 — 사용자가 추후 커스텀 추가할 수 있게 리스트 형태로 관리.
- `backend/app/services/segment_edit_service.py`: `find_filler_segments(segments, language) -> list[str]`
  — 세그먼트 텍스트가 필러워드 사전과 거의 일치하는(예: 텍스트 전체가 "음" 또는 "어" 단독인)
  세그먼트의 id 목록을 반환. 무음 구간은 `whisper_service.transcribe()`가 이미 `vad_filter=True`로
  스킵하므로, 여기서는 필러워드 텍스트 패턴 매칭에 집중.
- `backend/app/api/segments.py`: `POST /projects/{id}/items/{item_id}/segments/detect-fillers`
  — 필러워드로 추정되는 세그먼트 id 목록을 반환(삭제는 하지 않음, 미리보기 전용). 실제 삭제는
  기존 다중 선택 일괄 삭제(#14) 엔드포인트를 그대로 재사용.
- `frontend/src/components/SegmentList.tsx`: "필러워드 자동 찾기" 버튼 → 감지된 세그먼트를
  자동으로 체크박스 선택 상태로 만들어서, 사용자가 확인 후 기존 "선택 항목 삭제" 버튼으로
  일괄 삭제하게 함(자동 삭제 대신 확인 단계를 거치도록 설계 — 오탐 방지).

**주의점**: 필러워드 오탐(정상 발화가 "음..."으로 끝나는 문장 등) 가능성이 있으므로 자동
삭제가 아니라 반드시 사용자 확인을 거치는 흐름으로 구현.

**테스트**: `backend/tests/test_segment_edit_service.py`에 한국어/영어 필러워드 감지 케이스,
오탐 방지(필러워드가 포함되어 있지만 실제 문장인 경우는 감지되지 않아야 함) 케이스 추가.

### 21. 단어별(word-level) 타임스탬프 저장

**목표**: faster-whisper가 `word_timestamps=True`로 이미 내부적으로 계산하고 있는 단어별
시작/종료 시간을 실제로 저장 — 지금은 계산만 하고 버리고 있음. 이게 있어야 카라오케
하이라이트(16번)가 근사치가 아니라 정확해지고, forced alignment(4번)·애니메이션 캡션과도
연결됨.

**변경 범위**
- `backend/app/models/schemas.py`: `Word(BaseModel)` — `text: str`, `start: float`, `end: float`.
  `Segment`에 `words: list[Word] = Field(default_factory=list)` 추가.
- `backend/app/services/whisper_service.py`: `transcribe()`에서 `raw_segment.words`(faster-whisper가
  이미 반환하는 값)를 그대로 `Word` 리스트로 변환해 `Segment.words`에 채움.
- `backend/app/services/segment_edit_service.py`: `split_segment`/`merge_segments`/
  `find_replace`처럼 텍스트를 바꾸는 편집 함수들은 `words`를 보존하지 않고 비움
  (`words=[]`) — 편집 후에는 단어 정렬이 깨지므로 "재생 시 하이라이트 안 됨" 정도로 degrade,
  잘못된 타이밍을 보여주는 것보다 안전.
- `frontend/src/api/types.ts`, `frontend/src/utils/subtitleStyle.ts`: `Word` 타입 추가,
  `karaokeHighlightLength`를 근사치 계산 대신 실제 `segment.words`의 `start`/`end`와
  `currentTime`을 비교하는 정확한 방식으로 교체(word가 없는 세그먼트는 기존 근사 로직으로
  폴백).
- `backend/app/services/render_service.py`: `_karaoke_text()`도 균등 분할 대신 실제
  `segment.words` 간격을 사용하도록 교체(폴백 유지).

**주의점**: 세그먼트를 수정(텍스트 편집/분할/병합)하면 단어 정렬이 무효화되므로 `words`를
비우는 정책 — "일부만 정확하고 일부는 근사"인 상태를 사용자가 인지할 수 있게 UI에서 구분
표시할지는 후속 논의.

**테스트**: `backend/tests/test_whisper_service.py`에 `words` 필드 매핑 케이스,
`backend/tests/test_segment_edit_service.py`에 편집 후 `words`가 비워지는지 검증하는 케이스 추가.

### 22. 텍스트 삭제 시 영상도 함께 잘리는 컷 편집

**목표**: 세그먼트 리스트에서 문장을 삭제하면, 자막만 사라지는 게 아니라 해당 구간의
영상/오디오도 최종 출력물(17번 번인 렌더링 결과물)에서 실제로 잘려나가게 함 — Vrew/Descript의
"문서 편집하듯 영상 편집" 핵심 기능.

**변경 범위**
- `backend/app/services/render_service.py`: `build_cut_list(segments, deleted_ranges) -> list[tuple[float, float]]`
  — 삭제되지 않고 남은 구간들의 (start, end) 리스트 생성.
- `backend/app/services/render_service.py`의 `render()`: ffmpeg `-vf`에 더해 `select`/`concat`
  필터(또는 `-ss`/`-t` 다중 구간 후 `concat` demuxer)를 이용해 남은 구간만 이어붙인 영상을
  생성 — 자막 번인과 동시에 적용되므로 필터 그래프 구성이 복잡해짐(스파이크 필요).
- `backend/app/models/schemas.py`: `MediaItem`에 삭제된(컷된) 세그먼트를 별도로 추적할지,
  아니면 `segments` 리스트에서 완전히 제거된 것을 그대로 "삭제=컷"으로 취급할지 정책 결정
  필요 — 후자가 단순하지만 15번(Undo/Redo)과 조합해 "되돌리기"가 컷 복구까지 포함하는지
  명확히 해야 함.
- `frontend/src/components/ExportPanel.tsx`: "영상으로 내보내기" 시 "삭제된 구간도 영상에서
  잘라내기" 체크박스 추가(기본 off — 기존 번인 렌더링과 호환 유지, on으로 켜면 컷 편집 모드).

**주의점**: 공수가 가장 큼 — ffmpeg 필터 그래프 조합(자막 번인 + 다중 구간 컷)을 먼저
스파이크로 검증 필요. 15번(Undo/Redo)·17번(번인 렌더링)과의 상호작용 정의가 선행되어야 함.
착수 전 별도 설계 문서 필요.

**테스트**: `render_service`의 컷 구간 계산(`build_cut_list`)은 순수 함수라 단위 테스트 가능.
실제 ffmpeg 컷+번인 조합은 통합 테스트에서 짧은 샘플 영상으로 검증(17번과 동일한 방식).

**스파이크 결과 및 구현 노트 (2026-08-09)**:
- ffmpeg 필터 그래프 실현 가능성 검증: `testsrc2`로 생성한 10초 샘플 영상에 `trim`/`atrim` +
  `setpts`/`asetpts` + `concat`(다중 구간 컷) + `ass=` 필터(자막 번인)를 하나의
  `-filter_complex`로 결합해 단일 ffmpeg 호출로 실행 — (0-3초, 6-9초) 두 구간을 유지하도록
  요청했을 때 정확히 6.0초짜리 출력 영상이 생성되고 자막 타임코드도 출력 타임라인 기준으로
  올바르게 이동했음을 확인. `render_service.render()`에 실제 배선한 뒤에도(mock 없이 실제
  ffmpeg 서브프로세스 실행) 동일하게 6.0초 출력을 재확인 — 실현 가능성 확인 완료, 별도 2단계
  렌더링(컷 먼저 → 번인 나중) 없이 한 번의 ffmpeg 실행으로 충분함.
- **정책 결정**: "삭제=컷"으로 확정 — `MediaItem`에 별도 컷 추적 필드를 추가하지 않고, 렌더링
  시점의 `item.segments`에 남아있는 세그먼트들의 시간 구간만 `build_cut_list()`로 합쳐서 유지
  구간으로 사용. 15번(Undo/Redo)은 세그먼트 배열 스냅샷을 그대로 복원하므로 삭제를 되돌리면
  컷도 자동으로 함께 복구됨(추가 구현 불필요, `project_store.py`의 히스토리 스택 재사용).
- **알려진 트레이드오프**: 세그먼트 사이의 무음/미전사 구간(VAD가 애초에 세그먼트로 잡지 않은
  부분)도 "유지 구간에 포함되지 않음"이라는 이유로 함께 잘려나감 — 즉 사용자가 명시적으로
  삭제한 문장뿐 아니라 문장 사이 자연스러운 pause도 컷 대상에 포함됨. 체크박스 기본값은
  off이고 툴팁에 이 동작을 명시해 두었지만, 사용자가 "내가 지운 문장만" 잘릴 것으로 기대할
  경우 체감 차이가 있을 수 있어 후속 UX 검토 대상으로 남겨둠.
- **알려진 한계**: 유지 구간 수만큼 `trim`/`atrim` 필터 쌍이 늘어나므로, 문장이 매우 잘게
  쪼개진 긴 영상에서는 `-filter_complex` 문자열과 명령줄 길이가 커질 수 있음(Windows 명령줄
  길이 제한 ~32K자). 현재 규모에서는 문제되지 않았으나, 실사용에서 걸리면 구간을 청크로
  나눠 처리하거나 `select`/`aselect` 기반 필터로 교체하는 것을 검토.

## 권장 진행 순서 (19~22)

1. **Whisper `large-v3-turbo` 모델 옵션 추가(#19, 최우선)** — 공수 거의 없음(설정값 1줄),
   리스크 없음, 체감 효과(속도 5배) 즉시 확인 가능. 다른 항목보다 먼저 착수.
2. **필러워드 자동 감지(#20)** — 공수 낮음, 기존 인프라 재사용.
3. **단어별 타임스탬프(#21)** — 사용자에게 직접 보이진 않지만 카라오케(16번)·정밀 타이밍의
   기반이 되므로 20번 다음 우선.
4. **텍스트 기반 컷 편집(#22)** — 가장 크고 리스크 높음, 별도 스파이크/설계 문서 선행 후 착수.

---

## 23~28. 로컬 배포 제품화 대비 (2026-08-09 추가)

"기능을 위한 페이지 말고, 제품화를 위한 메인/관리/도움 페이지는 뭐가 필요한가"를 논의한 결과,
현재는 **로컬에서만 실행/배포**하기로 결정 — 클라우드 SaaS 파트(로그인, 과금, 사용량 대시보드,
관리자 콘솔, 상태 페이지)는 지금 범위에서 전부 제외합니다. 로컬 배포 기준으로 실제 필요한
페이지/문서만 추립니다. 나중에 클라우드 하이브리드로 확장할 때 이 섹션에 SaaS 항목을 추가합니다.

| # | 항목 | 임팩트 | 난이도 | 상태 |
|---|---|---|---|---|
| 23 | 소개/랜딩 화면 (앱 첫 진입 시 또는 정적 페이지) | 높음 | 낮음 | [x] 완료 (2026-08-09) |
| 24 | 도움말 콘텐츠 확장 (기존 HelpModal → 전체 가이드) | 중간 | 낮음 | [x] 완료 (2026-08-09) |
| 25 | 변경 로그 (CHANGELOG.md) | 중간 | 낮음 | [x] 완료 (2026-08-09) |
| 26 | 설치/실행 가이드 (README 정비) | 높음 | 낮음 | [x] **거의 완료** — `install.bat`/`run.bat` 포터블 설치, `installer/installer.iss`(Inno Setup) 기반 `.exe` 설치 프로그램(`installer/dist/Zamak_Valsadae_Setup.exe`)까지 이미 존재. README에 빠른 시작/개발자 설치/테스트/환경변수 표까지 정리되어 있음. 남은 건 코드 서명(아래 참고) 정도. |
| 27 | 라이선스/서드파티 고지 (LICENSE + NOTICE) | 중간 | 낮음 | [x] 완료 (2026-08-09) — **비공개(All rights reserved)로 결정**, 루트 `LICENSE` 추가 |
| 28 | 문의/피드백 경로 (GitHub Issues 안내) | 낮음 | 매우 낮음 | [x] 완료 (2026-08-09) — README에 링크 추가, 이슈 템플릿 2종 추가 |
| 29 | 설치 프로그램 코드 서명 | 중간 | 낮음(비용 발생) | [ ] 보류 — 배포 규모/일정 확정 후 착수(유료 인증서 필요) |
| 30 | 프론트엔드 자동 테스트 | 중간 | 중간 | [x] 완료 (2026-08-09) — Vitest + React Testing Library 도입, 순수 로직 12개 테스트 통과 |

### 23. 소개/랜딩 화면

**목표**: 처음 앱을 실행했을 때 지금은 바로 빈 프로젝트 화면(업로드 유도 문구)만 보임 —
"이 도구가 뭘 하는지"를 한눈에 설명하는 소개 화면이 없음. 로컬 배포라 웹 랜딩 페이지 대신
**앱 안의 첫 화면**을 소개 화면으로 겸용하는 것을 권장(별도 웹 호스팅 불필요).

**변경 범위**
- `frontend/src/App.tsx`: 프로젝트가 하나도 없을 때(`projects.length === 0`) 지금의
  `app-empty-hint-onboarding`을 확장 — 핵심 기능 3~4개(전사/번역/스타일/내보내기)를
  아이콘+한 줄 설명으로 요약, "새 프로젝트로 시작" CTA는 유지.
- 스크린샷/데모 GIF는 넣지 않고 텍스트+아이콘 위주로 가볍게 — 로컬 앱이라 로딩 비용을
  늘릴 필요 없음.
- 별도 정적 페이지가 필요하면(예: 사내 배포 안내 링크용) `docs/landing.html` 한 장으로
  충분 — 프레임워크 없이 `DESIGN.md` 토큰 그대로 인라인 CSS.

**테스트**: 프로젝트 0개 상태 렌더링 스냅샷/수동 확인.

**구현 노트 (2026-08-09)**: 계획대로 별도 웹 페이지 없이 `app-empty-hint-onboarding`을
확장 — 제목/한 줄 소개 + 전사·번역·스타일·검수/내보내기 4개 기능 카드(아이콘+한 줄 설명)를
추가하고 기존 업로드 안내 문구는 그대로 유지.

### 24. 도움말 콘텐츠 확장

**목표**: 지금 `HelpModal.tsx`가 이미 단축키/기본 사용법을 담고 있음 — 이걸 "제품 도움말"
수준으로 확장(각 도구 탭별 설명, 자주 겪는 오류 — 예: ffmpeg 미설치, HF_TOKEN 필요 — 해결법).

**변경 범위**
- `frontend/src/components/HelpModal.tsx`: 섹션 추가 — 전사/번역/스타일/내보내기/AI검수
  탭별 사용법, 트러블슈팅(모델 다운로드 실패, ffmpeg 없음, 렌더링 실패 시 확인할 것).
- 내용이 길어지면 모달 대신 `docs/user-guide.md`로 분리하고 모달에서는 요약 + "더 보기"
  형태로 링크(로컬 파일 경로 또는 GitHub 문서 링크).

**테스트**: 해당 없음(콘텐츠 작업) — 링크/앵커만 수동 확인.

**구현 노트 (2026-08-09)**: "문제 해결" 섹션을 추가(모델 다운로드 정체, 화자 분리 오류,
번인 렌더링 실패, 서버 재시작으로 인한 작업 중단, 한/영 번역 이상 케이스)하고, GitHub Issues
안내 문구를 마지막에 붙였습니다. 별도 `docs/user-guide.md` 분리는 아직 모달 내용이 그 정도로
길지 않아 보류. 그 김에 "일괄 업로드 시 자동 전사"라고 적혀 있던 오래된(자동 전사 큐 기능이
제거되며 stale해진) 설명도 실제 동작(수동으로 전사 시작 필요)에 맞게 고쳤습니다.

### 25. 변경 로그 (CHANGELOG.md)

**목표**: 로컬 배포 앱은 사용자가 업데이트를 수동으로 받기 때문에, "이번 버전에서 뭐가
바뀌었는지"를 확인할 곳이 없으면 신뢰도가 떨어짐.

**변경 범위**
- 저장소 루트에 `CHANGELOG.md` 추가, [Keep a Changelog](https://keepachangelog.com) 형식
  권장(Added/Changed/Fixed 구분).
- 이번 로드맵의 완료 항목(15~22번)을 첫 릴리스 노트로 소급 작성.
- 이후 커밋 컨벤션(`feat:`/`fix:`)과 연동해 릴리스 시점마다 갱신.

**테스트**: 해당 없음.

**구현 노트 (2026-08-09)**: 루트 `CHANGELOG.md` 추가. 버전 태그가 아직 없어 지금까지의 작업
전체를 `[Unreleased]` 하나로 소급 정리(Added/Changed/Fixed) — 실제 첫 배포 시점부터 버전을
나누기로 함.

### 26. 설치/실행 가이드 (README 정비)

**목표**: 현재 README 상태를 "처음 받은 사람이 바로 실행 가능한 수준"으로 점검 — 요구사항
(Python/Node 버전, ffmpeg, 디스크 용량), 실행 순서(backend/frontend 각각), 흔한 실패 케이스를
명확히 정리.

**변경 범위**
- 루트 `README.md`: 요구사항 표, `pip install -r requirements.txt` / `npm install` +
  실행 커맨드, 모델 다운로드 최초 실행 시 소요 시간/용량 안내, HF_TOKEN(화자분리) 설정
  안내를 한 곳에 모음.
- 스크린샷 1~2장(지금 만든 새 UI) 첨부 권장.

**테스트**: 해당 없음 — 새 환경에서 README만 보고 실행되는지 수동 드라이런 권장.

### 27. 라이선스/서드파티 고지

**목표**: faster-whisper, CTranslate2, pyannote-audio, ffmpeg 등 서드파티 의존성의 라이선스
조건(특히 배포 시 고지 의무가 있는 것들)을 확인하고 명시 — 로컬 배포판을 남에게 공유/판매할
계획이 있다면 필수.

**변경 범위**
- 루트 `LICENSE` 파일 추가(프로젝트 자체 라이선스 결정 필요 — 사용자 확인 필요).
- `NOTICE.md` 또는 README 하단에 주요 의존성과 라이선스 종류 목록화.

**주의점**: 프로젝트 라이선스(공개/비공개, 상업적 배포 여부)는 코드 작업이 아니라 사용자
결정이 먼저 필요 — 착수 전 확인.

**결정 및 구현 노트 (2026-08-09)**:
- **비공개(All rights reserved)로 결정** — 나중에 서버에 올려 유료 SaaS로 운영할 계획이라
  경쟁사 노출 부담이 없는 오픈소스보다 코드 보호가 우선.
- 서드파티 의존성 재검토 결과, 현재 스택(faster-whisper·CTranslate2·pyannote-audio·FastAPI·
  React는 모두 MIT, ffmpeg는 LGPL)에는 **AGPL 라이선스가 없어** 서버 호스팅(SaaS) 형태로
  운영해도 코드 공개 의무는 없음을 확인 — GPL/LGPL은 "배포" 시에만 카피레프트 의무가 발동하고
  네트워크 통한 서비스 제공은 배포로 보지 않기 때문(AGPL만 이 예외를 막음). **앞으로 의존성
  추가 시 AGPL만 피하면** 지금 방향(비공개+유료 SaaS)에 구조적 장애가 없음.
- 번역 모델 `facebook/nllb-200-distilled-600M`(CC-BY-NC-4.0, 비상업적 이용 전용)은 카피레프트가
  아니라 "상업적 이용 자체 금지" 조항이라 공개/비공개와 무관하게 별도 문제였음 — 향후 LLM API
  기반 번역으로 전환할 계획이라 자연히 해소되는 것으로 확인, 로컬 NLLB 경로 제거는 전환 시점에
  진행하기로 함(급하지 않음, 지금 코드에서 건드리지 않음).
- 루트 `LICENSE` 파일을 "All rights reserved" 형태(별도 OSS 라이선스 텍스트 없이 저작권자 고지 +
  사용 제한 명시)로 추가 완료. `NOTICE.md`(서드파티 의존성 목록)는 아직 미작성 — 필요성이
  낮은 항목(비공개 배포는 오픈소스처럼 의존성 고지 의무가 강하지 않음)이라 우선순위 낮춤.

### 28. 문의/피드백 경로

**목표**: 로컬 배포 단계에서는 별도 지원 티켓 시스템 없이, GitHub Issues 하나로 충분.

**변경 범위**
- README에 "버그 리포트/기능 요청은 GitHub Issues로" 안내 문구 + 링크 추가.
- 이슈 템플릿(`.github/ISSUE_TEMPLATE/`) 최소 1개(버그 리포트) 추가 검토.

**테스트**: 해당 없음.

**구현 노트 (2026-08-09)**: README에 "버그 리포트/기능 요청" + GitHub Issues 링크 섹션 추가,
`.github/ISSUE_TEMPLATE/`에 버그 리포트·기능 요청 템플릿 2종 추가.

### 29. 설치 프로그램 코드 서명

**목표**: README에 이미 명시된 대로, 지금 `.exe` 설치 프로그램은 서명이 안 되어 있어 배포 시
Windows SmartScreen이 "PC를 보호했습니다" 경고를 띄움 — "추가 정보 → 실행"을 눌러야 진행되는
번거로움이 있고, 처음 받는 사람 입장에선 신뢰도가 떨어짐.

**변경 범위**
- 코드 서명 인증서 구매(EV 코드 서명이 SmartScreen 평판을 가장 빨리 확보 — 일반 코드 서명은
  일정 다운로드 수가 쌓일 때까지 경고가 남을 수 있음).
- `installer/installer.iss` 빌드 후 `signtool`로 서명하는 단계를 빌드 스크립트에 추가.

**주의점**: 비용이 드는 항목(연 단위 인증서 비용) — 실제 배포/공유 규모가 정해진 뒤 착수할지
사용자 결정 필요.

### 30. 프론트엔드 자동 테스트

**목표**: README에 "현재 프론트엔드 테스트 스위트는 별도 설정이 없다"고 명시되어 있음 — 지금은
UI 변경 시 `npm run dev`로 수동 확인만 하는 상태. 백엔드는 `pytest` 스위트가 있는 것과 대비됨.

**변경 범위**
- Vitest + React Testing Library 도입 (Vite 프로젝트라 통합이 가장 매끄러움).
- 우선순위: `SegmentList`(필터/검색/일괄작업), `useElapsedSeconds`/`subtitleStyle.ts` 같은
  순수 로직 유틸부터 — UI 스냅샷보다 동작 검증 위주로.

**테스트**: 해당 항목 자체가 테스트 인프라 구축.

**구현 노트 (2026-08-09)**: `vitest`/`@testing-library/react`/`@testing-library/jest-dom`/
`@testing-library/user-event`/`jsdom` 설치, `vite.config.ts`에 `test` 블록(jsdom 환경,
`src/setupTests.ts`) 추가, `package.json`에 `npm run test` 스크립트 추가. 첫 테스트로 순수
로직 위주 2개 파일 작성 — `subtitleStyle.test.ts`(페이드 opacity, 카라오케 하이라이트
길이 계산: 단어 타임스탬프 기반/근사 폴백 둘 다), `useElapsedSeconds.test.ts`(서버가 준
`started_at` 기준으로 경과 시간을 계산하는지 — 이번 세션 초반에 고친 "새로고침하면 경과 시간이
초기화되던 버그"의 회귀 테스트 역할도 겸함). 총 12개 테스트, 모두 통과. `SegmentList`
컴포넌트 테스트(필터/검색/일괄작업)는 아직 없음 — 다음 착수 후보로 남겨둠.

## 권장 진행 순서 (23~30)

지금까지 확인된 실제 상태 기준(설치 프로그램 `.exe`, README 이미 준비됨)으로 다시 정리:

1. **라이선스 고지(#27)** — 배포/공유 여부와 무관하게 지금 가장 먼저 결정이 필요한 항목
   (프로젝트 라이선스를 뭘로 할지가 다른 배포 관련 결정에 선행됨).
2. **변경 로그(#25)** — 이미 여러 기능이 릴리스된 상태라 지금 시작해도 소급 작성 가치가 있음.
3. **소개/랜딩 화면(#23)** + **도움말 확장(#24)** — 병렬 진행 가능.
4. **코드 서명(#29)** — 비용이 드는 항목이라 실제 배포 규모/일정이 정해지면 착수.
5. **프론트엔드 테스트(#30)** — 서비스 오픈 자체를 막는 항목은 아니지만, 이후 변경이 잦아질수록
   회귀 방지 가치가 커짐 — 오픈 직후 착수 권장.
6. **문의 경로(#28)** — 가장 가벼움, 아무 때나 끼워 넣어도 무방.

---

## 31~40. 서버 호스팅(SaaS) 전환 시 필요한 법적/회사 페이지 (2026-08-09 작성, 2026-08-09 vrew.ai 실사로 보강, 착수 보류)

Vrew(vrew.ai/ko/)를 실제로 탐색해 상단 내비게이션·푸터·가격 페이지 구조를 확인하고 항목을
구체화했습니다. **지금은 착수하지 않습니다** — 로컬 전용 단계에서는 불필요하고, 아래 항목
다수가 실제 사업자 정보(사업자등록번호, 통신판매업신고번호, 주소, 고객센터 연락처, 가격 정책)를
필요로 해서 사용자가 사업자 등록·가격 정책을 확정한 뒤에야 정확한 내용으로 채울 수 있습니다.
서버 호스팅 착수 시점에 다시 꺼내 진행합니다.

### 참고: vrew.ai 실사 인벤토리 (2026-08-09)

**상단 내비게이션**: 주요 기능 · 인사이트 · 사용법 배우기 · 커뮤니티 · 데이터 보호 · 가격 정책 ·
로그인 · 체험하기(CTA) · 무료 다운로드(CTA)

**푸터 3단 구성**:
- 서비스: 가격 정책 / 다운로드 / 데이터 보호
- 자료실: 인사이트 / 사용법 배우기 / 커뮤니티 / 공지사항
- 회사: 회사 소개 / 이용약관 / 개인정보처리방침 / 환불 안내
- 하단 고지줄: 상호·대표자명·사업자등록번호·통신판매업신고번호, 채팅상담 "문의하기" 링크,
  이메일, 전화번호, 주소를 한 줄로 표기

**가격 페이지 구조**: Free(무료, 무기한) / Light / Standard(추천 배지) / Business 4단계,
월간·연간 토글(연간 시 "20% 할인" 강조), 기능별 제한이 아니라 **크레딧 통합 방식**(모든 기능이
크레딧 하나를 공유), FAQ(해지 정책 등), "전체 가격·기능 비교 보기" 상세 비교 페이지로 링크.

**다운로드**: OS별(macOS / Windows / Ubuntu) 개별 다운로드 버튼.

### 항목 목록

| # | 항목 | 비고 | 상태 |
|---|---|---|---|
| 31 | 이용약관 (Terms of Service) | 전자상거래법상 유료 서비스는 필수 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesLegal.tsx`(TERMS_PAGE), 사업자 정보/요금 조항/관할 법원은 더미(예시) 값, 실제 등록 후 교체 필요 |
| 32 | 개인정보처리방침 (Privacy Policy) | 개인정보보호법상 필수 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesLegal.tsx`(PRIVACY_PAGE), 수집 항목/보유기간/위탁 업체/책임자는 더미(예시) 값 |
| 33 | 환불 안내 (Refund Policy) | 구독/과금 방식이 정해져야 조건 확정 가능 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesLegal.tsx`(REFUND_PAGE) |
| 34 | 회사 소개 + 사업자 정보 푸터 | 대표자/사업자등록번호/통신판매업신고번호/주소/연락처 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesBiz.tsx`(COMPANY_PAGE) |
| 35 | 가격 정책 페이지 | 플랜 구조가 사업 결정 사항 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesBiz.tsx`(PRICING_PAGE) |
| 36 | 다운로드 페이지 | OS별 배포판 | [x] 작성, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesBiz.tsx`(DOWNLOAD_PAGE). Windows는 실제 내용, macOS/Ubuntu는 여전히 빌드 자체가 없어 [T.B.D] |
| 37 | 로그인/체험하기 CTA | 클라우드 계정 시스템 필요 — 콘텐츠가 아니라 기능 | [x] 요구사항 메모 작성, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesBiz.tsx`(LOGIN_PAGE), 실제 UI/구현은 #45 참고 |
| 38 | 데이터 보호 안내 페이지 | 업로드한 영상/오디오가 서버에서 어떻게 저장·삭제되는지 설명 | [x] 완료 (2026-08-09) — `HelpModal`에 "데이터 보호" 섹션 추가 |
| 39 | 인사이트/사용법 배우기(콘텐츠) | 블로그류 콘텐츠 | [x] 인사이트는 `website/src/content/legalPagesBiz.tsx`(INSIGHTS_PAGE)로 이관 완료 (2026-08-10). "사용법 배우기"(옛 `docs/pages/learn.md`)는 `HelpModal`과 내용이 중복되어 별도 이관 없이 삭제 |
| 40 | 커뮤니티/공지사항 | 사용자 규모가 어느 정도 있어야 의미 있음 | [x] 초안 작성, 더미 값 채움, `website/`로 이관 완료 (2026-08-10) — `website/src/content/legalPagesBiz.tsx`(COMMUNITY_PAGE, NOTICES_PAGE) |

**주의점**: `website/src/content/`의 사업자등록번호, 통신판매업신고번호, 요금제 숫자, 관할
법원, 개인정보보호책임자 등은 2026-08-10에 **더미(예시) 값**으로 채워졌습니다 — 실제 사업자 등록·
요금제 설계가 끝나면 진짜 값으로 교체해야 하며, 각 파일 상단에 "더미" 경고 문구를 남겨뒀습니다.
macOS/Linux 빌드처럼 실제로 존재하지 않는 것은 더미로 채우지 않고 사실 그대로 [T.B.D]로
남겼습니다(존재하지 않는 걸 있는 것처럼 채우면 오히려 오해를 유발하므로). **이용약관·
개인정보처리방침·환불안내는 시행 전 반드시 법률 검토를 받으세요** — 여기 작성된 조항은
표준 뼈대일 뿐 법적 효력을 보장하지 않습니다.

---

## 41~48. 다음 단계 (2026-08-10 작성)

앱/웹사이트 분리, 데스크톱 창 전환, 프론트엔드 리팩토링을 마친 뒤 남은 일들을 정리합니다.
우선순위는 대략 위에서 아래 순서입니다.

| # | 항목 | 비고 | 상태 |
|---|---|---|---|
| 41 | `run.bat` 실사용 환경 최종 확인 | 실제 사용자 데스크톱에서 설치 프로그램 실행 → 앱 실행 → 회원가입 → 이메일 인증 → 로그인 → 실제 번역까지 전체 흐름 확인 완료, 문제없음 | [x] 완료 (2026-08-18, 사용자 확인) |
| 42 | `website/` 실제 배포 | 오라클 클라우드 VM(44/45번과 같은 서버)에 nginx 정적 호스팅으로 배포 완료(2026-08-12) — `https://site.168-110-107-78.nip.io`, TLS 포함. `Toolbar.tsx`/`AboutModal.tsx`의 `WEBSITE_URL`을 이 주소로 교체 완료. 소유 도메인이 정해지면 그걸로 재교체 필요 | [x] 완료 (2026-08-12, 임시 도메인) |
| 43 | `docs/pages/*.md`와 `website/src/content/`의 중복 정리 | `website/src/content/`가 유일한 정본이 되도록 `docs/pages/` 디렉터리를 통째로 삭제(2026-08-10). `learn.md`는 `HelpModal`과 중복이라 별도 이관 없이 삭제, 나머지 10개 페이지는 전부 `website/src/content/legalPagesLegal.tsx` / `legalPagesBiz.tsx`로 이미 이관되어 있었음 | [x] 완료 (2026-08-10) |
| 44 | 번역/AI 검수 서버 API 연동 | 오라클 VM 릴레이(`https://168-110-107-78.nip.io`)에서 Supabase 인증 → Gemini(무료) 번역 호출까지 end-to-end 성공 확인(2026-08-13), 실제 사용자 계정으로 데스크톱 앱에서도 재확인 완료(2026-08-18) — 아래 상세 참고. AI 검수 자동화(수동 파일 왕복 → 서버 자동 호출)는 후속 라운드로 분리, 아직 미착수 | [x] 완료 (2026-08-18) |
| 45 | 로그인/계정 시스템 실제 구현 | 데스크톱 앱에 이메일+비밀번호 로그인 UI 추가 완료(2026-08-13) — `Toolbar.tsx`에 로그인/로그아웃, `AuthModal.tsx`(회원가입 토글 포함), `useAuth.ts`(Supabase 세션 ↔ 백엔드 동기화). 백엔드는 `POST/GET/DELETE /auth/session`(인메모리, `auth_state.py`)로 세션 보관, 로그인 상태면 번역 시 자동으로 릴레이 서버를 씀(`get_translator`의 `session_token`). 구글 소셜 로그인은 후속 | [x] 완료 (2026-08-13) |
| 46 | 설치 프로그램 코드 서명 (#29) | 배포 규모 확정 전까지 보류, 유료 인증서 필요 | [ ] 보류 |
| 47 | 사업자 정보·가격 정책 실제 값 확정 | `website/src/content/`와 `docs/pages/`에 흩어진 더미 값(사업자등록번호, 요금제 숫자 등)을 사업자 등록·요금제 설계 완료 후 일괄 교체 | [ ] 사업 결정 대기 |
| 48 | 프론트엔드 테스트 커버리지 확대 | `Timeline`(5개), `useSegmentEditing`(6개), `useProjectWorkspace`(6개) 테스트 추가 완료 (2026-08-10). `Toolbar`(8개), `SubtitleStylePanel`(6개) 테스트 추가 완료 (2026-08-12) — 총 8개 파일 55개 테스트 통과. 남은 후보: `ExportPanel`, `ReviewPanel` | [x] 2차 완료 (2026-08-12) |

**참고**: 44~45번(서버 연동, 계정 시스템)이 이번 로드맵에서 가장 크고 실제 아키텍처 변경이
필요한 작업입니다. 착수 전 별도 설계 문서(API 인증 방식, 요금 정산 방식, 로컬 앱↔서버 통신
프로토콜)를 먼저 작성하는 것을 권장합니다.

### 44~45. 서버 릴레이 인프라 구축 (2026-08-12)

사용자가 보유한 오라클 클라우드 프리티어 VM(168.110.107.78, Oracle Linux 9.7, 2 vCPU, RAM 1GB)을
서버로 쓰기로 결정. 조사 결과 번역 쪽은 이미 서버 경유 구조가 거의 다 되어 있었음 —
`backend/app/services/translation_service.py`의 `ApiTranslator`가 OpenAI 호환
`{base_url}/chat/completions`를 호출하고 `base_url`은 `TRANSLATION_API_BASE_URL` 환경변수로
이미 교체 가능(`backend/app/core/config.py:72`). 즉 "서버 릴레이"는 같은 모양의 프록시 서버를
올리고 로컬 앱 env만 그 주소로 돌리면 됨 — 클라이언트 코드 변경 불필요.

**구축 완료**:
- 신규 `server/` 디렉터리(FastAPI, `backend/`와 동일한 `dataclass` Settings + `os.environ.get`
  컨벤션) — `GET /healthz`(인증 불필요), `POST /v1/chat/completions`(Supabase JWT 검증 후
  서버 보관 OpenAI 키로 대리 호출). 테스트 8개(`server/tests/`) 통과.
- 오라클 VM: 전용 비루트 사용자 `relay`, `/opt/relay`에 앱 배포 + venv, systemd
  `relay.service`(자동 재시작), nginx 리버스 프록시(`80 → 127.0.0.1:8000`), OS 방화벽(firewalld)
  80/443 오픈, SELinux `httpd_can_network_connect` 활성화 — 전부 로컬(127.0.0.1)에서는 정상
  응답 확인.
- 도메인은 소유 도메인 없이 `168-110-107-78.nip.io`(nip.io, 실제 IP를 가리키는 무료 와일드카드
  DNS)를 쓰기로 함 — Let's Encrypt 인증서 발급 가능.

**완료** (2026-08-12, 사용자가 오라클 콘솔에서 VCN Security List에 80/443 Ingress 룰 추가):
`https://168-110-107-78.nip.io/healthz` 외부에서 200 OK 확인, `certbot --nginx`로 TLS 인증서
발급 및 자동 갱신(2026-11-10 만료 전) 설정 완료.

**Supabase 연동 완료** (2026-08-12): 프로젝트 생성 후 `SUPABASE_JWT_SECRET`을 `/opt/relay/.env`에
설정, 서비스 재시작 후 실제 서명된 토큰으로 `POST /v1/chat/completions` 호출 → 인증 통과 확인.

**AI 제공자 연동 완료** (2026-08-13): OpenAI는 결제가 걸려있어 보류하고, 대신 **결제 계정이
연결되지 않은 Google AI Studio 프로젝트(`gen-lang-client-...`)의 Gemini 무료 티어**로 연결.
데스크톱 앱은 항상 `model: "gpt-4o-mini"`로 요청하는데(OpenAI 기준으로 하드코딩됨) Gemini는
모델명 체계가 달라서, 서버가 클라이언트의 model 값을 무시하고 `OPENAI_MODEL_OVERRIDE` 환경변수
값(`gemini-2.5-flash`)으로 바꿔치기하도록 `server/app/api/chat.py`에 로직 추가(`server/app/core/config.py`의
`openai_model_override`). 실제 번역 요청(`"Hello, how are you?"` → `"안녕하세요?"`)까지 성공
확인 — Supabase 인증 → Gemini 번역까지 전체 체인이 실제로 동작한다.

**로그인 UI 완료** (2026-08-13): `frontend/src/components/AuthModal.tsx` + `useAuth.ts`로
이메일/비밀번호 로그인·회원가입 추가(`@supabase/supabase-js`), `Toolbar.tsx`에 로그인 상태
표시. 로그인 성공 시 세션의 `access_token`을 백엔드 `POST /auth/session`으로 전달해
`backend/app/services/auth_state.py`(인메모리, 프로세스 하나=사용자 하나)에 보관. 번역 엔진을
"api"로 놓고 로그인돼 있으면 `translation_service.get_translator()`가 그 토큰과
`hosted_relay_base_url`(오라클 릴레이 주소)로 자동 전환 — 사용자가 `TRANSLATION_API_KEY`를
직접 설정할 필요가 없어짐. 로그인 안 한 상태/`.env` 미설정 상태에서는 기존 로컬 엔진·수동
API 키 흐름이 그대로 동작(로그인 UI는 Supabase 값이 없으면 조용히 숨겨짐).

**남은 것**: 실제 사용자 계정으로 앱을 켜서 로그인 → 번역까지 수동 확인 완료(2026-08-18,
설치 프로그램 실행부터 실제 번역까지 전체 흐름 문제없음 확인). 아직 남은 건 구글 소셜
로그인, OpenAI 실제 키로 교체(`server/.env`의 `OPENAI_API_KEY`/`OPENAI_BASE_URL` 변경 +
`OPENAI_MODEL_OVERRIDE` 비우기 — 코드 변경 불필요), AI 검수 자동화(#44 후반부, 여전히
범위 밖).

**이번에 의도적으로 범위 밖에 둔 것**:
- AI 검수 자동 서버 호출 전환(`backend/app/api/review.py`, `ReviewPanel.tsx`) — 같은 릴레이
  재사용 가능하나 새 백엔드 엔드포인트 + 프론트 UI 작업이 필요해 별도 라운드
- 데스크톱 앱의 실제 로그인 UI(회원가입/로그인 화면, 세션 토큰 저장) — Toolbar/App.tsx를
  건드리는 별도 규모의 프론트엔드 작업

상세 배포 절차와 트러블슈팅 메모는 `server/README.md` 참고.
