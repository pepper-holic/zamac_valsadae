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
    """A rocket launching on a trail of subtitle bars - "자막발사대" (subtitle
    launchpad) is a literal cannon/launchpad for subtitles, so the exhaust
    plume is drawn as tapering subtitle-line bars instead of generic smoke."""
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = 12
    draw.rounded_rectangle(
        [margin, margin, SIZE - margin, SIZE - margin], radius=48, fill=ACCENT
    )

    # Rocket: nose cone, body, porthole (cut out to accent), and fins.
    draw.polygon([(128, 42), (104, 96), (152, 96)], fill=WHITE)
    draw.rounded_rectangle([104, 90, 152, 150], radius=12, fill=WHITE)
    draw.ellipse([118, 104, 138, 124], fill=ACCENT)
    draw.polygon([(104, 128), (104, 156), (82, 156)], fill=WHITE)
    draw.polygon([(152, 128), (152, 156), (174, 156)], fill=WHITE)

    # Exhaust trail made of subtitle bars, tapering down.
    draw.rounded_rectangle([98, 168, 158, 180], radius=6, fill=WHITE)
    draw.rounded_rectangle([104, 190, 152, 202], radius=6, fill=WHITE)
    draw.rounded_rectangle([112, 212, 144, 224], radius=6, fill=WHITE)

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
