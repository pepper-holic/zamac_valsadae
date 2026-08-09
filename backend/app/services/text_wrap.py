import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


def _wrap_long_line(line: str, max_chars: int) -> list[str]:
    """공백 기준 단어 단위로 max_chars를 넘지 않게 그리디 줄바꿈."""
    words = line.split()
    if not words:
        return [line]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def wrap_subtitle_text(text: str, max_chars: int) -> str:
    """자막 한 줄이 max_chars를 넘지 않도록 자동 줄바꿈.

    우선 마침표/물음표/느낌표 등 문장 종결 기준으로 나누어 줄에 담고,
    한 문장 자체가 max_chars를 넘으면 단어 단위로 추가 분할한다.
    """
    stripped = text.strip()
    if not stripped or max_chars <= 0 or len(stripped) <= max_chars:
        return text

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(stripped) if s]

    lines: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = sentence
    if current:
        lines.append(current)

    final_lines: list[str] = []
    for line in lines:
        if len(line) <= max_chars:
            final_lines.append(line)
        else:
            final_lines.extend(_wrap_long_line(line, max_chars))

    return "\n".join(final_lines)
