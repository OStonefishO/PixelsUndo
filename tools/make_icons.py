# -*- coding: utf-8 -*-
"""Generate the PNG app icons used by the web manifest and iOS."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "assets"


def make(size: int) -> Image.Image:
    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = int(side * 0.22)
    draw.rounded_rectangle((0, 0, side - 1, side - 1), radius=radius, fill="#0d1117")

    # Same five-block mark as web/assets/favicon.svg, enlarged for the launcher.
    unit = side / 32.0
    blocks = [(6, 6), (20, 6), (13, 13), (6, 20), (20, 20)]
    for x, y in blocks:
        draw.rectangle(
            (x * unit, y * unit, (x + 6) * unit - 1, (y + 6) * unit - 1),
            fill="#c8ff5e",
        )
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (512, 192, 180):
        make(size).save(OUT / ("icon-%d.png" % size), "PNG", optimize=True)
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
