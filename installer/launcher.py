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
import os
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
# The backend's first cold start imports torch/transformers/pyannote-audio -
# genuinely slow (well over a minute in testing) the very first time, before
# any disk/OS caching has warmed up. Must stay >= desktop.py's own
# STARTUP_TIMEOUT_SEC, which independently guards the same startup.
STARTUP_TIMEOUT_SEC = 240

_STEP_LINE_RE = re.compile(r"\[(\d+)/(\d+)\]")
# pip prints one of these per package it fetches/builds - used to give step 4
# (the multi-GB backend package install) visible movement instead of sitting
# at a static percentage for several minutes straight.
_PIP_PACKAGE_RE = re.compile(r"^(?:Downloading|Using cached) ")
_PIP_PACKAGE_STEP = 4

# install.ps1's own step messages are English (they go to install.log for
# troubleshooting) - the splash shows a Korean label per step instead of
# passing that text through, keyed by step number.
_STEP_LABELS_KO = {
    1: "Python 런타임 준비 중",
    2: "Node.js 런타임 준비 중",
    3: "ffmpeg 준비 중",
    4: "필수 패키지 설치 중 (용량이 커서 시간이 걸릴 수 있어요)",
    5: "프론트엔드 빌드 중",
}


def _show_error(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "Zamak_Valsadae", 0x10)


def _log(message: str) -> None:
    """No-op under the real --noconsole build (sys.stdout is None there);
    only prints when run via the console debug build for troubleshooting."""
    if sys.stdout is not None:
        print(message, flush=True)


def _ensure_runtime(root_dir: Path, splash: Splash) -> None:
    # Gated on install.ps1's completion marker, not python.exe: an
    # interrupted first run can leave python.exe present but pip/site-packages
    # never set up, and install.ps1 itself now repairs that on retry - but
    # only if it actually gets invoked again instead of being skipped here.
    install_complete = root_dir / "runtime" / ".install_complete"
    _log(f"[launcher] root_dir={root_dir}")
    _log(f"[launcher] install marker present: {install_complete.exists()}")
    if install_complete.exists():
        return

    log_path = root_dir / "install.log"
    install_ps1 = root_dir / "install.ps1"
    _log(f"[launcher] install.ps1 exists: {install_ps1.exists()}")
    splash.update("최초 실행: 필수 구성 요소를 설치하는 중...", percent=0)

    try:
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
            # npm/vite print UTF-8 (e.g. the "✓" build checkmark); text=True
            # alone decodes with the system locale encoding (cp949 on Korean
            # Windows), which raises UnicodeDecodeError on that output.
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        _log(f"[launcher] failed to start powershell: {exc!r}")
        raise
    _log(f"[launcher] install.ps1 subprocess started, pid={process.pid}")

    current_step = 0
    package_count = 0
    with log_path.open("w", encoding="utf-8") as log_file:
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            match = _STEP_LINE_RE.search(line)
            if match:
                current_step, total = int(match.group(1)), int(match.group(2))
                package_count = 0
                label = _STEP_LABELS_KO.get(
                    current_step, f"설치 진행 중 ({current_step}/{total})"
                )
                _log(f"[launcher] step {current_step}/{total}: {label} | raw: {line.strip()}")
                splash.update(label, percent=(current_step - 1) / total * 100)
            elif current_step == _PIP_PACKAGE_STEP and _PIP_PACKAGE_RE.match(line):
                package_count += 1
                label = _STEP_LABELS_KO[_PIP_PACKAGE_STEP]
                splash.update(f"{label} · 패키지 {package_count}개 처리됨", percent=None)
    returncode = process.wait()
    _log(f"[launcher] install.ps1 exited with code {returncode}")

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
    backend_dir = root_dir / "backend"
    runtime_dir = root_dir / "runtime"

    # Spawns pythonw directly instead of going through `cmd /c "call env.bat
    # && ... && start ... /B ..."`: that batch chain proved unreliable when
    # launched via subprocess with CREATE_NO_WINDOW (silently produced no
    # running process at all in testing). env.bat only ever did two things -
    # prepend the portable runtime to PATH, and set HF_HUB_DISABLE_XET - both
    # reproduced directly here via `env`, which Popen passes straight to the
    # child process with no shell in between to swallow errors.
    child_env = dict(os.environ)
    child_env["PATH"] = (
        f"{runtime_dir / 'python'};{runtime_dir / 'python' / 'Scripts'};"
        f"{runtime_dir / 'node'};{runtime_dir / 'ffmpeg' / 'bin'};{child_env.get('PATH', '')}"
    )
    child_env["HF_HUB_DISABLE_XET"] = "1"

    subprocess.Popen(
        [str(pythonw_exe), "-m", "app.desktop"],
        cwd=str(backend_dir),
        env=child_env,
        creationflags=CREATE_NO_WINDOW,
    )


def _wait_until_backend_ready(splash: Splash) -> bool:
    splash.update("앱을 불러오는 중...")
    deadline = time.monotonic() + STARTUP_TIMEOUT_SEC
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(READY_URL, timeout=1)
            return True
        except OSError:
            time.sleep(0.4)
    return False


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
            _log("[launcher] backend process launched, waiting for it to respond...")
            ready = _wait_until_backend_ready(splash)
            _log(f"[launcher] backend ready: {ready}")
        except Exception as exc:  # surfaced to caller via `failure`, not raised on this thread
            import traceback

            _log(f"[launcher] worker failed: {exc!r}")
            _log(traceback.format_exc())
            failure["message"] = str(exc)
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()
    splash.fade_in()
    splash.run_until(done.is_set)
    splash.fade_out()

    return 1 if failure else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Runs under pythonw-style --noconsole (no stdout/stderr), so an
        # uncaught exception here would otherwise vanish silently - a crash
        # before the splash's own worker-thread try/except even starts
        # (e.g. constructing the Tk window itself) needs its own net.
        import traceback

        crash_log = Path(sys.executable).resolve().parent / "launcher_crash.log"
        crash_log.write_text(traceback.format_exc(), encoding="utf-8")
        _show_error(
            "실행 준비 중 오류가 발생했습니다.\n\n"
            f"자세한 내용: {crash_log}"
        )
        sys.exit(1)
