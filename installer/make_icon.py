"""Generates installer/icon.ico (a simple subtitle/play glyph) from scratch.

Run once with the portable Python whenever the icon design needs to change:
    runtime\\python\\python.exe installer\\make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ACCENT = (124, 58, 237)  # matches --accent in frontend/src/index.css
WHITE = (255, 255, 255)
SIZE = 256
OUTPUT_PATH = Path(__file__).resolve().parent / "icon.ico"


def _draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = 12
    draw.rounded_rectangle(
        [margin, margin, SIZE - margin, SIZE - margin], radius=48, fill=ACCENT
    )

    # Two subtitle-line bars, evoking a captions/subtitle track.
    bar_height = 20
    draw.rounded_rectangle(
        [64, 108, 192, 108 + bar_height], radius=bar_height // 2, fill=WHITE
    )
    draw.rounded_rectangle(
        [64, 140, 160, 140 + bar_height], radius=bar_height // 2, fill=WHITE
    )

    # Small play triangle above the bars, evoking video playback.
    draw.polygon([(112, 56), (112, 96), (148, 76)], fill=WHITE)

    return image


def main() -> None:
    icon = _draw_icon()
    icon.save(
        OUTPUT_PATH,
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
