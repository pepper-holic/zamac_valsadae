"""Frameless splash window with fade in/out, shown while launcher.py works.

Tkinter (bundled with a normal desktop Python, and pulled into the PyInstaller
exe automatically) is used here rather than in the app itself, because the
portable embedded-Python runtime the app runs under has no Tcl/Tk shipped
with it.

The actual startup work (runtime install, backend boot) runs on a background
thread; it reports progress back via `update()`, which marshals the change
onto the Tk main thread with `root.after(0, ...)` - the standard safe way to
touch Tk widgets from another thread.
"""

import time
import tkinter as tk
from tkinter import ttk

_WIDTH, _HEIGHT = 420, 200
_BG = "#14161c"
_FG = "#e8e9ee"
_SUBTLE_FG = "#9aa0ad"
_ACCENT = "#5b8cff"
_TROUGH = "#23262f"
_FADE_STEPS = 15
_FADE_STEP_SEC = 0.015
_PUMP_INTERVAL_SEC = 0.03


class Splash:
    def __init__(self, app_name: str, icon_path: str | None = None) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(bg=_BG)
        self._center()
        if icon_path:
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

        tk.Label(
            self.root, text=app_name, font=("Segoe UI", 16, "bold"), fg=_FG, bg=_BG
        ).pack(pady=(36, 6))

        self._status_var = tk.StringVar(value="시작하는 중...")
        tk.Label(
            self.root,
            textvariable=self._status_var,
            font=("Segoe UI", 9),
            fg=_SUBTLE_FG,
            bg=_BG,
            wraplength=_WIDTH - 60,
        ).pack(pady=(0, 16))

        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure(
            "Splash.Horizontal.TProgressbar",
            troughcolor=_TROUGH,
            background=_ACCENT,
            bordercolor=_BG,
            lightcolor=_ACCENT,
            darkcolor=_ACCENT,
        )
        self._progress = ttk.Progressbar(
            self.root,
            style="Splash.Horizontal.TProgressbar",
            length=_WIDTH - 80,
            mode="determinate",
            maximum=100,
        )
        self._progress.pack(pady=4)

    def _center(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - _WIDTH) // 2
        y = (screen_h - _HEIGHT) // 2
        self.root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")

    def update(self, text: str, percent: float | None = None) -> None:
        """Thread-safe status/progress update, callable from any thread."""

        def _apply() -> None:
            self._status_var.set(text)
            if percent is None:
                self._progress.configure(mode="indeterminate")
                self._progress.start(15)
            else:
                self._progress.stop()
                self._progress.configure(mode="determinate")
                self._progress["value"] = max(0.0, min(100.0, percent))

        self.root.after(0, _apply)

    def fade_in(self) -> None:
        self.root.deiconify()
        for step in range(_FADE_STEPS + 1):
            self.root.attributes("-alpha", step / _FADE_STEPS)
            self.root.update()
            time.sleep(_FADE_STEP_SEC)

    def fade_out(self) -> None:
        for step in range(_FADE_STEPS, -1, -1):
            self.root.attributes("-alpha", step / _FADE_STEPS)
            self.root.update()
            time.sleep(_FADE_STEP_SEC)
        self.root.destroy()

    def run_until(self, is_done) -> None:
        """Pumps the Tk event loop (so queued `update()` calls apply) until is_done()."""
        while not is_done():
            self.root.update()
            time.sleep(_PUMP_INTERVAL_SEC)
