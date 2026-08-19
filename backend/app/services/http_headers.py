from urllib.parse import quote


def content_disposition_attachment(filename: str) -> str:
    """Builds a safe `Content-Disposition: attachment` header value.

    `filename` here always originates from the *original* uploaded file's
    name (see project_store.add_item), which is attacker-controlled input
    (a raw multipart field, not restricted to the local OS's actual
    filename rules) - interpolating it into `filename="..."` directly would
    let a crafted upload filename (containing `"`) break out of the quoted
    attribute and inject extra Content-Disposition parameters.

    Mirrors what Starlette's FileResponse already does internally
    (starlette.responses.FileResponse.__init__): percent-encode and fall
    back to the RFC 5987 `filename*=UTF-8''...` form whenever the filename
    isn't already a safe plain ASCII token - this also correctly handles
    the Korean filenames this app expects as normal input, not just the
    attack case.
    """
    encoded = quote(filename)
    if encoded == filename:
        return f'attachment; filename="{filename}"'
    return f"attachment; filename*=utf-8''{encoded}"
