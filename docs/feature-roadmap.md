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
