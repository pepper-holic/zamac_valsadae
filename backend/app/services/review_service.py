from app.models.schemas import ReviewDiffEntry, ReviewImportResult, ReviewPackage, ReviewSegment, Segment

REVIEW_INSTRUCTIONS = (
    "이 파일은 자막 전사 및 번역 검수용 패키지입니다. "
    "각 segment의 text(원문)와 translation(번역문)의 정확성을 검토하고, "
    "필요한 경우 값을 수정한 뒤 동일한 JSON 스키마로 파일을 저장해 다시 업로드해 주세요. "
    "id, start, end는 자막 싱크와 연결되어 있으니 변경하지 마세요(타이밍 자체를 조정할 의도가 아니라면)."
)

_DIFF_FIELDS = ("text", "translation", "start", "end")


def build_review_package(
    item_id: str, media_filename: str, segments: list[Segment]
) -> ReviewPackage:
    return ReviewPackage(
        item_id=item_id,
        media_filename=media_filename,
        instructions=REVIEW_INSTRUCTIONS,
        segments=[
            ReviewSegment(
                id=segment.id,
                start=segment.start,
                end=segment.end,
                text=segment.text,
                translation=segment.translation,
            )
            for segment in segments
        ],
    )


def diff_review_import(
    current_segments: list[Segment], imported_segments: list[dict]
) -> ReviewImportResult:
    current_by_id = {segment.id: segment for segment in current_segments}
    diffs: list[ReviewDiffEntry] = []
    unknown_ids: list[str] = []

    for imported in imported_segments:
        segment_id = imported.get("id")
        
        # 1. ID가 없거나 None인 경우 예외 처리
        if segment_id is None:
            continue

        # 2. 안전하게 string 타입 보장
        segment_id_str = str(segment_id)

        current = current_by_id.get(segment_id_str)
        if current is None:
            unknown_ids.append(segment_id_str)
            continue

        for field in _DIFF_FIELDS:
            old_value = getattr(current, field)
            new_value = imported.get(field)
            if old_value != new_value:
                diffs.append(
                    ReviewDiffEntry(
                        id=segment_id_str,
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                    )
                )

    return ReviewImportResult(diffs=diffs, unknown_segment_ids=unknown_ids)