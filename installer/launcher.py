"""Native .exe launcher for Zamak_Valsadae, replacing run.bat as the shortcut target.

Mirrors run.bat's logic exactly (portable runtime bootstrap -> .pth fixup ->
launch pythonw -m app.desktop) but as a windowed (console-less) executable, so
double-clicking the Start Menu/Desktop shortcut never flashes any window -
including on first launch, when the portable runtime install runs fully
hidden with its output captured to install.log (next to this exe) instead of
a console, so the log is still available if something needs troubleshooting.

Shows a small fading splash (see splash.py) the whole time: on first launch
it tracks install.ps1's "[n/5]" step markers for real progress, and on every
launch it stays up until the backend responds, so there's never a silent gap
between double-click and a visible window.

Built with PyInstaller (see installer/build_launcher.bat) into a standalone
exe - this script has no dependency on the app's own backend/frontend code,
so the build stays small and fast regardless of app size.
"""

import ctypes
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from splash import Splash

CREATE_NO_WINDOW = 0x08000000

# Must match HOST/PORT in backend/app/desktop.py - this process only waits
# for the backend to come up, it doesn't import or run it directly.
HOST = "127.0.0.1"
PORT = 8000
READY_URL = f"http://{HOST}:{PORT}/projects"
STARTUP_TIMEOUT_SEC = 120

_STEP_LINE_RE = re.compile(r"\[(\d+)/(\d+)\]")


def _show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "Zamak_Valsadae", 0x10)


def _ensure_runtime(root_dir: Path, splash: Splash) -> None:
    python_exe = root_dir / "runtime" / "python" / "python.exe"
    if python_exe.exists():
        return

    log_path = root_dir / "install.log"
    install_ps1 = root_dir / "install.ps1"
    splash.update("최초 실행: 필수 구성 요소를 설치하는 중...", percent=0)

    process = subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(install_ps1),
        ],
        cwd=str(root_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
        text=True,
        bufsize=1,
    )
    with log_path.open("w", encoding="utf-8") as log_file:
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            match = _STEP_LINE_RE.search(line)
            if match:
                step, total = int(match.group(1)), int(match.group(2))
                label = line.strip().lstrip("=> ").strip()
                splash.update(label, percent=(step - 1) / total * 100)
    returncode = process.wait()

    if returncode != 0:
        _show_error(
            "런타임 설치에 실패했습니다.\n\n"
            f"자세한 내용: {log_path}\n\n"
            "install.bat을 실행해 다시 시도해 주세요."
        )
        raise RuntimeError("runtime install failed")


def _launch_backend(root_dir: Path) -> None:
    site_packages = root_dir / "runtime" / "python" / "Lib" / "site-packages"
    (site_packages / "zamac_valsadae.pth").write_text(
        str(root_dir / "backend") + "\n", encoding="utf-8"
    )

    pythonw_exe = root_dir / "runtime" / "python" / "pythonw.exe"
    env_bat = root_dir / "env.bat"
    backend_dir = root_dir / "backend"

    subprocess.Popen(
        [
            "cmd",
            "/c",
            f'call "{env_bat}" && cd /d "{backend_dir}" && start "" /B "{pythonw_exe}" -m app.desktop',
        ],
        cwd=str(root_dir),
        creationflags=CREATE_NO_WINDOW,
    )


def _wait_until_backend_ready(splash: Splash) -> None:
    splash.update("앱을 불러오는 중...")
    deadline = time.monotonic() + STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(READY_URL, timeout=1)
            return
        except OSError:
            time.sleep(0.4)


def main() -> int:
    root_dir = Path(sys.executable).resolve().parent
    icon_path = root_dir / "icon.ico"

    splash = Splash(
        "Zamak_Valsadae (자막발사대)",
        icon_path=str(icon_path) if icon_path.exists() else None,
    )

    done = threading.Event()
    failure: dict[str, str] = {}

    def worker() -> None:
        try:
            _ensure_runtime(root_dir, splash)
            _launch_backend(root_dir)
            _wait_until_backend_ready(splash)
        except Exception as exc:  # surfaced to caller via `failure`, not raised on this thread
            failure["message"] = str(exc)
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()
    splash.fade_in()
    splash.run_until(done.is_set)
    splash.fade_out()

    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
