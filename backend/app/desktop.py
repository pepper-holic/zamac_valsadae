"""Native desktop window entry point.

Launches the FastAPI backend in a background thread and shows the app in
a WebView2-based native window (via pywebview) instead of a Chrome/Edge
browser tab, so the packaged app feels like a normal Windows program.

Runs under pythonw.exe (no console), so failures are written to a log
file and surfaced via a message box instead of stderr.
"""

import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000
READY_URL = f"http://{HOST}:{PORT}/projects"
APP_URL = f"http://{HOST}:{PORT}"
# The very first cold start imports torch/transformers/pyannote-audio before
# uvicorn can bind the port - well over a minute in testing before the OS
# has any of that on disk cache. Must stay >= the native launcher's own
# STARTUP_TIMEOUT_SEC (installer/launcher.py), which independently waits on
# this same readiness check from outside this process.
STARTUP_TIMEOUT_SEC = 240
LOG_PATH = Path(__file__).resolve().parent.parent / "desktop_error.log"

# webview.start(icon=...)'s docstring claims GTK/QT only, but on Windows
# "edgechromium"/"mshtml" both resolve to the winforms platform module, which
# does honor it (webview/platforms/winforms.py sets self.Icon from it) -
# without it, the window/taskbar icon falls back to extracting one from
# sys.executable, i.e. the portable runtime's generic pythonw.exe icon.
# icon.ico lives at the app root when installed (installer.iss copies it
# there) but under installer/ in this dev checkout - try both.
_APP_ROOT = Path(__file__).resolve().parent.parent.parent
_ICON_CANDIDATES = [_APP_ROOT / "icon.ico", _APP_ROOT / "installer" / "icon.ico"]


def _find_icon() -> str | None:
    for candidate in _ICON_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def _ensure_pywebview_installed() -> None:
    try:
        import webview  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview>=5.3"])


def _run_server() -> None:
    import uvicorn
    from app.main import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_until_ready() -> bool:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(READY_URL, timeout=1)
            return True
        except OSError:
            time.sleep(0.4)
    return False


def _report_failure(message: str) -> None:
    LOG_PATH.write_text(message, encoding="utf-8")
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            f"Zamak_Valsadae 실행 중 오류가 발생했습니다.\n\n자세한 내용: {LOG_PATH}",
            "Zamak_Valsadae",
            0x10,  # MB_ICONERROR
        )


def main() -> None:
    _ensure_pywebview_installed()
    import webview

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    if not _wait_until_ready():
        raise RuntimeError(
            f"백엔드 서버가 {STARTUP_TIMEOUT_SEC}초 안에 응답하지 않았습니다 ({READY_URL})."
        )

    webview.create_window(
        "Zamak_Valsadae",
        APP_URL,
        width=1440,
        height=900,
        min_size=(1024, 640),
    )
    webview.start(gui="edgechromium", icon=_find_icon())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _report_failure(traceback.format_exc())
        raise
