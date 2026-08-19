from app.services.http_headers import content_disposition_attachment


def test_content_disposition_plain_ascii_filename():
    assert content_disposition_attachment("sample.srt") == 'attachment; filename="sample.srt"'


def test_content_disposition_escapes_quote_in_filename():
    # A raw f'filename="{name}"' would let this break out of the quoted
    # attribute and inject extra Content-Disposition parameters - the
    # percent-encoded RFC 5987 form sidesteps that entirely.
    header = content_disposition_attachment('evil".mp4')
    assert '"' not in header.split("filename*=utf-8''", 1)[-1]
    assert header.startswith("attachment; filename*=utf-8''")


def test_content_disposition_encodes_korean_filename():
    header = content_disposition_attachment("영상.mp4")
    assert header.startswith("attachment; filename*=utf-8''")
    assert "영상" not in header
