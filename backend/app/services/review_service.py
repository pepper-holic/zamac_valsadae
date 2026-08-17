from app.models.schemas import (
    CompactReviewGroup,
    CompactReviewPackage,
    ReviewDiffEntry,
    ReviewImportResult,
    ReviewPackage,
    ReviewSegment,
    Segment,
)

REVIEW_INSTRUCTIONS = (
    "이 파일은 자막 전사 및 번역 검수용 패키지입니다. "
    "각 segment의 text(원문)와 translation(번역문)의 정확성을 검토하고, "
    "필요한 경우 값을 수정한 뒤 동일한 JSON 스키마로 파일을 저장해 다시 업로드해 주세요. "
    "id, start, end는 자막 싱크와 연결되어 있으니 변경하지 마세요(타이밍 자체를 조정할 의도가 아니라면)."
)

COMPACT_REVIEW_INSTRUCTIONS = (
    "이 파일은 AI 검수용으로 압축된 패키지입니다(토큰 절약을 위해 start/end 타이밍은 제외됨). "
    "groups는 동일한 text+translation을 가졌던 segment들을 하나로 묶은 것으로, ids에 원래 segment id들이 들어 있습니다. "
    "text 또는 translation을 수정하면 그 그룹에 속한 ids 전부에 동일하게 적용됩니다. "
    "그룹을 나누거나 합치지 말고(ids 배열은 그대로 유지), text/translation 값만 교정한 뒤 동일한 JSON 스키마로 저장해 다시 업로드해 주세요."
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


def build_compact_review_package(
    item_id: str, media_filename: str, segments: list[Segment]
) -> CompactReviewPackage:
    groups: dict[tuple[str, str | None], CompactReviewGroup] = {}
    order: list[tuple[str, str | None]] = []

    for segment in segments:
        key = (segment.text, segment.translation)
        group = groups.get(key)
        if group is None:
            group = CompactReviewGroup(text=segment.text, translation=segment.translation)
            groups[key] = group
            order.append(key)
        group.ids.append(segment.id)

    return CompactReviewPackage(
        item_id=item_id,
        media_filename=media_filename,
        instructions=COMPACT_REVIEW_INSTRUCTIONS,
        groups=[groups[key] for key in order],
    )


def diff_compact_review_import(
    current_segments: list[Segment], imported_groups: list[dict]
) -> ReviewImportResult:
    current_by_id = {segment.id: segment for segment in current_segments}
    diffs: list[ReviewDiffEntry] = []
    unknown_ids: list[str] = []

    for group in imported_groups:
        new_text = group.get("text")
        new_translation = group.get("translation")

        for raw_id in group.get("ids") or []:
            segment_id = str(raw_id)
            current = current_by_id.get(segment_id)
            if current is None:
                unknown_ids.append(segment_id)
                continue

            for field, new_value in (("text", new_text), ("translation", new_translation)):
                old_value = getattr(current, field)
                if old_value != new_value:
                    diffs.append(
                        ReviewDiffEntry(
                            id=segment_id, field=field, old_value=old_value, new_value=new_value
                        )
                    )

    return ReviewImportResult(diffs=diffs, unknown_segment_ids=unknown_ids)


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