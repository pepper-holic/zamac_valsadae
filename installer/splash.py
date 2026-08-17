"""Frameless splash window with fade in/out, shown while launcher.py works.

Tkinter (bundled with a normal desktop Python, and pulled into the PyInstaller
exe automatically) is used here rather than in the app itself, because the
portable embedded-Python runtime the app runs under has no Tcl/Tk shipped
with it.

Everything is hand-drawn on a single Canvas (rounded card, progress pill)
instead of stock ttk widgets, which render as plain OS-themed controls that
don't match the app's rounded, flat-color look. Text uses "맑은 고딕"
throughout rather than "Segoe UI" (which has no Hangul glyphs and would make
Windows silently substitute a different font per run for the Korean text,
producing an inconsistent mix within the same label).

The actual startup work (runtime install, backend boot) runs on a background
thread; it reports progress back via `update()`. Tkinter widgets may only be
touched from the thread that created them - even scheduling via `root.after()`
from another thread can raise "RuntimeError: main thread is not in main loop"
depending on the Tcl build, so `update()` only pushes onto a plain
`queue.Queue` (thread-safe on its own), and the main thread drains it on each
event-loop pump below.
"""

import queue
import time
import tkinter as tk

# Mirrors the app's light theme (frontend/src/index.css :root) so the splash
# doesn't look like a different product from the window that follows it.
_WIDTH, _HEIGHT = 440, 220
_BG = "#f7f6f9"  # --bg
_SURFACE = "#ffffff"  # --surface
_BORDER = "#e5e4e7"  # --border
_TEXT_H = "#08060d"  # --text-h
_TEXT = "#4b4555"  # --text
_ACCENT = "#7c3aed"  # --accent
_ACCENT_BG = "#ede7fb"  # flat approximation of --accent-bg over white
_FONT_FAMILY = "맑은 고딕"
_CARD_RADIUS = 16
_BAR_RADIUS = 5
_BAR_WIDTH = _WIDTH - 96
_BAR_HEIGHT = 10
_FADE_STEPS = 15
_FADE_STEP_SEC = 0.015
_PUMP_INTERVAL_SEC = 0.03
_INDETERMINATE_STEP = 0.06


def _rounded_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class Splash:
    def __init__(self, app_name: str, icon_path: str | None = None, logo_path: str | None = None) -> None:
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

        self._canvas = tk.Canvas(
            self.root, width=_WIDTH, height=_HEIGHT, bg=_BG, highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)

        _rounded_rect(
            self._canvas, 10, 10, _WIDTH - 10, _HEIGHT - 10, _CARD_RADIUS,
            fill=_SURFACE, outline=_BORDER, width=1,
        )

        # App logo next to the name - falls back to a plain accent dot if the
        # PNG is missing or Tk's PhotoImage can't load it (no Pillow in this
        # PyInstaller build, so only GIF/PNG/PPM are supported).
        mark_cx, mark_cy, mark_r = 46, 58, 14
        self._logo_image = None
        if logo_path:
            try:
                image = tk.PhotoImage(file=logo_path)
                # PhotoImage.subsample only takes integer factors - the source
                # glyph is 256x256, so /8 lands close to the 2*mark_r target.
                factor = max(1, image.width() // (mark_r * 2))
                self._logo_image = image.subsample(factor, factor)
            except tk.TclError:
                self._logo_image = None
        if self._logo_image is not None:
            self._canvas.create_image(mark_cx, mark_cy, image=self._logo_image)
        else:
            self._canvas.create_oval(
                mark_cx - mark_r, mark_cy - mark_r, mark_cx + mark_r, mark_cy + mark_r,
                fill=_ACCENT, outline="",
            )
        self._canvas.create_text(
            mark_cx + mark_r + 12, mark_cy,
            text=app_name, anchor="w",
            font=(_FONT_FAMILY, 14, "bold"), fill=_TEXT_H,
        )

        self._status_id = self._canvas.create_text(
            _WIDTH / 2, 108, text="시작하는 중...", anchor="center",
            font=(_FONT_FAMILY, 10), fill=_TEXT, width=_WIDTH - 80,
        )

        self._bar_x1 = (_WIDTH - _BAR_WIDTH) / 2
        self._bar_y1 = 148
        self._bar_x2 = self._bar_x1 + _BAR_WIDTH
        self._bar_y2 = self._bar_y1 + _BAR_HEIGHT
        _rounded_rect(
            self._canvas, self._bar_x1, self._bar_y1, self._bar_x2, self._bar_y2,
            _BAR_RADIUS, fill=_ACCENT_BG, outline="",
        )
        self._fill_id = _rounded_rect(
            self._canvas, self._bar_x1, self._bar_y1, self._bar_x1, self._bar_y2,
            _BAR_RADIUS, fill=_ACCENT, outline="",
        )

        self._queue: queue.Queue[tuple[str, float | None]] = queue.Queue()
        self._indeterminate = False
        self._indeterminate_pos = 0.0

    def _center(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - _WIDTH) // 2
        y = (screen_h - _HEIGHT) // 2
        self.root.geometry(f"{_WIDTH}x{_HEIGHT}+{x}+{y}")

    def update(self, text: str, percent: float | None = None) -> None:
        """Thread-safe: just enqueues. Only the main thread touches the canvas."""
        self._queue.put((text, percent))

    def _set_bar(self, fraction: float) -> None:
        width = max(_BAR_HEIGHT, _BAR_WIDTH * max(0.0, min(1.0, fraction)))
        self._canvas.delete(self._fill_id)
        self._fill_id = _rounded_rect(
            self._canvas, self._bar_x1, self._bar_y1, self._bar_x1 + width, self._bar_y2,
            _BAR_RADIUS, fill=_ACCENT, outline="",
        )

    def _drain_queue(self) -> None:
        try:
            while True:
                text, percent = self._queue.get_nowait()
                if percent is None:
                    self._canvas.itemconfigure(self._status_id, text=text)
                    self._indeterminate = True
                else:
                    clamped = max(0.0, min(100.0, percent))
                    self._canvas.itemconfigure(
                        self._status_id, text=f"{text} ({round(clamped)}%)"
                    )
                    self._indeterminate = False
                    self._set_bar(clamped / 100)
        except queue.Empty:
            pass

    def _tick_indeterminate(self) -> None:
        if not self._indeterminate:
            return
        self._indeterminate_pos = (self._indeterminate_pos + _INDETERMINATE_STEP) % 2.0
        # Bounces a short segment back and forth (0..1..0) across the track.
        center = self._indeterminate_pos if self._indeterminate_pos <= 1.0 else 2.0 - self._indeterminate_pos
        segment = 0.28
        seg_start = max(0.0, center - segment / 2)
        seg_end = min(1.0, center + segment / 2)
        self._canvas.delete(self._fill_id)
        self._fill_id = _rounded_rect(
            self._canvas,
            self._bar_x1 + _BAR_WIDTH * seg_start,
            self._bar_y1,
            self._bar_x1 + _BAR_WIDTH * seg_end,
            self._bar_y2,
            _BAR_RADIUS, fill=_ACCENT, outline="",
        )

    def fade_in(self) -> None:
        self.root.deiconify()
        for step in range(_FADE_STEPS + 1):
            self._drain_queue()
            self.root.attributes("-alpha", step / _FADE_STEPS)
            self.root.update()
            time.sleep(_FADE_STEP_SEC)

    def fade_out(self) -> None:
        for step in range(_FADE_STEPS, -1, -1):
            self._drain_queue()
            self.root.attributes("-alpha", step / _FADE_STEPS)
            self.root.update()
            time.sleep(_FADE_STEP_SEC)
        self.root.destroy()

    def run_until(self, is_done) -> None:
        """Pumps the Tk event loop (draining queued `update()` calls) until is_done()."""
        while not is_done():
            self._drain_queue()
            self._tick_indeterminate()
            self.root.update()
            time.sleep(_PUMP_INTERVAL_SEC)
