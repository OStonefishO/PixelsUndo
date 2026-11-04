# -*- coding: utf-8 -*-
"""Generate the two demo images shipped with PixelsUndo.

sample-landscape.png : a clean illustration used to try the pixel workshop.
sample-watermark.png : the same scene with a repeated translucent stock
                       watermark, used to try the repair brush.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "samples"
SIZE = (1280, 800)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def make_scene() -> Image.Image:
    w, h = SIZE
    img = Image.new("RGB", SIZE)
    px = img.load()

    # Sky gradient: deep dusk blue into warm peach near the horizon.
    top = (34, 55, 96)
    mid = (122, 129, 156)
    low = (246, 189, 143)
    horizon = int(h * 0.56)
    for y in range(horizon):
        t = y / max(1, horizon)
        c = lerp(top, mid, t / 0.65) if t < 0.65 else lerp(mid, low, (t - 0.65) / 0.35)
        for x in range(w):
            px[x, y] = c

    draw = ImageDraw.Draw(img, "RGBA")

    # Sun with a soft halo.
    sun = (int(w * 0.72), int(h * 0.33))
    halo = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    for r, alpha in ((210, 26), (150, 36), (95, 52), (52, 90)):
        hd.ellipse([sun[0] - r, sun[1] - r, sun[0] + r, sun[1] + r], fill=(255, 214, 150, alpha))
    halo = halo.filter(ImageFilter.GaussianBlur(38))
    img = Image.alpha_composite(img.convert("RGBA"), halo).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse([sun[0] - 44, sun[1] - 44, sun[0] + 44, sun[1] + 44], fill=(255, 236, 197, 255))

    # Distant mountain range.
    rng = random.Random(7)
    far = []
    for i in range(9):
        far.append((int(w * i / 8), int(h * (0.40 + rng.random() * 0.10))))
    far = [(0, int(h * 0.55))] + far + [(w, int(h * 0.55))]
    draw.polygon(far, fill=(96, 104, 132, 255))
    for i in range(len(far) - 1):
        if far[i][1] < far[i + 1][1]:
            x0, y0 = far[i]
            x1, y1 = far[i + 1]
            draw.polygon([(x0, y0), (x1, y1), (x1, y0 + 26)], fill=(120, 128, 156, 255))

    # Near hills.
    near = [(0, int(h * 0.55))]
    for i in range(13):
        near.append((int(w * i / 12), int(h * (0.48 + rng.random() * 0.075))))
    near += [(w, int(h * 0.55)), (w, int(h * 0.62)), (0, int(h * 0.62))]
    draw.polygon(near, fill=(52, 76, 92, 255))

    # Lake.
    water_top = int(h * 0.56)
    for y in range(water_top, h):
        t = (y - water_top) / max(1, h - water_top)
        c = lerp((88, 112, 132), (27, 42, 63), t)
        draw.line([(0, y), (w, y)], fill=c)
    # Sun reflection.
    for i in range(46):
        y = water_top + int(i * (h - water_top) / 46) + rng.randint(-2, 2)
        half = int(46 - i * 0.55 + rng.randint(-8, 8))
        if half <= 0:
            continue
        alpha = max(18, 130 - i * 2)
        draw.line(
            [(sun[0] - half, y), (sun[0] + half, y)],
            fill=(255, 214, 158, alpha),
            width=max(1, 3 - i // 18),
        )
    # Water ripples.
    for _ in range(230):
        y = rng.randint(water_top + 6, h - 4)
        x = rng.randint(0, w - 1)
        length = rng.randint(10, 90)
        draw.line([(x, y), (min(w, x + length), y)], fill=(210, 228, 240, rng.randint(8, 30)))

    # Foreground bank with grass and pines.
    bank = [(0, int(h * 0.80))]
    for i in range(10):
        bank.append((int(w * i / 9), int(h * (0.78 + rng.random() * 0.05))))
    bank += [(w, h), (0, h)]
    draw.polygon(bank, fill=(20, 32, 34, 255))
    for _ in range(680):
        x = rng.randint(0, w - 1)
        y = rng.randint(int(h * 0.78), h - 1)
        g = rng.randint(34, 78)
        draw.line([(x, y), (x + rng.randint(-2, 2), y - rng.randint(3, 16))], fill=(26, g, 44, 220))

    # Pine silhouettes.
    def pine(x, base, height, color):
        for layer in range(4):
            t = layer / 4
            half = height * (0.34 - t * 0.055)
            y0 = base - height * (0.92 - t * 0.22)
            draw.polygon(
                [(x, y0 - height * 0.26), (x - half, y0), (x + half, y0)],
                fill=color,
            )
        draw.rectangle([x - 3, base - height * 0.12, x + 3, base], fill=(24, 28, 30, 255))

    for x, base, height in (
        (int(w * 0.10), int(h * 0.84), 210),
        (int(w * 0.16), int(h * 0.82), 150),
        (int(w * 0.88), int(h * 0.85), 245),
        (int(w * 0.94), int(h * 0.83), 170),
    ):
        pine(x, base, height, (17, 40, 38, 255))

    # Small cabin with a warm window.
    cx, cy = int(w * 0.31), int(h * 0.735)
    draw.rectangle([cx - 54, cy - 30, cx + 54, cy + 34], fill=(52, 38, 34, 255))
    draw.polygon([(cx - 68, cy - 30), (cx, cy - 78), (cx + 68, cy - 30)], fill=(38, 34, 36, 255))
    draw.rectangle([cx - 26, cy - 8, cx - 6, cy + 12], fill=(255, 196, 104, 255))
    draw.rectangle([cx + 10, cy - 8, cx + 30, cy + 12], fill=(255, 196, 104, 255))
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - 92, cy - 62, cx + 96, cy + 70], fill=(255, 178, 92, 34))
    glow = glow.filter(ImageFilter.GaussianBlur(24))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    # Birds.
    draw = ImageDraw.Draw(img, "RGBA")
    for bx, by, s in ((w * 0.48, h * 0.17, 12), (w * 0.53, h * 0.13, 9), (w * 0.57, h * 0.20, 7)):
        draw.arc([bx - s, by - s * 0.6, bx, by + s * 0.6], 200, 340, fill=(40, 46, 58, 220), width=2)
        draw.arc([bx, by - s * 0.6, bx + s, by + s * 0.6], 200, 340, fill=(40, 46, 58, 220), width=2)

    # Very light grain so compression / pixelation has something to chew on.
    grain = Image.effect_noise(SIZE, 12).convert("L")
    img = Image.blend(img, Image.merge("RGB", (grain, grain, grain)), 0.035)
    return img


def load_font(size: int):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def add_watermark(scene: Image.Image) -> Image.Image:
    w, h = scene.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tile = Image.new("RGBA", (620, 260), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    font = load_font(58)
    text = "PIXELSTOCK"
    box = td.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    td.text(((620 - tw) / 2 - box[0], (260 - th) / 2 - box[1]), text, font=font, fill=(255, 255, 255, 78))
    sub = load_font(21)
    subtext = "PREMIUM  STOCK  PHOTO"
    sb = td.textbbox((0, 0), subtext, font=sub)
    td.text(
        ((620 - (sb[2] - sb[0])) / 2 - sb[0], (260 - th) / 2 + 60 - sb[1]),
        subtext,
        font=sub,
        fill=(255, 255, 255, 62),
    )
    tile = tile.rotate(24, resample=Image.BICUBIC, expand=True)
    for y in range(-320, h + 320, 250):
        for x in range(-420, w + 420, 600):
            layer.alpha_composite(tile, (x, y))

    # Bottom-right attribution badge.
    badge = Image.new("RGBA", (360, 56), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rounded_rectangle([0, 0, 359, 55], radius=10, fill=(12, 16, 22, 122))
    bf = load_font(24)
    bd.text((18, 15), "©  PIXELSTOCK", font=bf, fill=(255, 255, 255, 150))
    layer.alpha_composite(badge, (w - 390, h - 86))

    return Image.alpha_composite(scene.convert("RGBA"), layer).convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    scene = make_scene()
    scene.save(OUT / "sample-landscape.png", "PNG", optimize=True)
    add_watermark(scene).save(OUT / "sample-watermark.png", "PNG", optimize=True)
    print("wrote", OUT / "sample-landscape.png")
    print("wrote", OUT / "sample-watermark.png")


if __name__ == "__main__":
    main()
