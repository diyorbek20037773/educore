"""Render the PWA icons and the default Open Graph image (`static/img/`) with Pillow.

The mark is drawn geometrically (no font files needed for the icon); the OG image uses the self-hosted
a Source Serif TTF when available and falls back to Pillow's default font. Commit the output.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img"
NAVY = (11, 31, 58)
GOLD = (201, 162, 39)
WHITE = (255, 255, 255)


def mark(draw: ImageDraw.ImageDraw, x: int, y: int, unit: float) -> None:
    """The "E" mark from favicon.svg, scaled: unit = 1/64 of the icon size."""

    def box(x0: float, y0: float, x1: float, y1: float, fill: tuple[int, int, int]) -> None:
        draw.rectangle([x + x0 * unit, y + y0 * unit, x + x1 * unit - 1, y + y1 * unit - 1], fill=fill)

    box(19, 16, 26, 48, WHITE)
    box(26, 16, 45, 22, WHITE)
    box(26, 29, 42, 35, WHITE)
    box(26, 42, 45, 48, WHITE)
    box(19, 52, 45, 55, GOLD)


def icon(size: int) -> None:
    image = Image.new("RGB", (size, size), NAVY)
    mark(ImageDraw.Draw(image), 0, 0, size / 64)
    image.save(OUT / f"icon-{size}.png", optimize=True)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "static/fonts/og/SourceSerif4-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ):
        path = ROOT / candidate if not candidate.startswith("/") else Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def og_image() -> None:
    image = Image.new("RGB", (1200, 630), NAVY)
    draw = ImageDraw.Draw(image)
    mark(draw, 80, 150, 5)
    draw.text((440, 150), "EDUCORE", font=font(110), fill=WHITE)
    draw.rectangle([444, 295, 700, 301], fill=GOLD)
    subtitle = "Huquqni muhofaza qilish\ntaʼlim muassasalari\naxborot-tahliliy platformasi"
    draw.multiline_text((444, 330), subtitle, font=font(34), fill=(200, 212, 232), spacing=12)
    image.save(OUT / "og-default.png", optimize=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        icon(size)
    og_image()
    print("wrote icon-192.png, icon-512.png, og-default.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
