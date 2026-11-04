# -*- coding: utf-8 -*-
"""Image processing engine for PixelsUndo.

Pixel-art conversion is implemented with Pillow + NumPy only, so it stays fast
and deterministic on modest hardware.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:  # Pillow >= 9.1
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
    RESAMPLE_NEAREST = Image.Resampling.NEAREST
    DITHER_FS = Image.Dither.FLOYDSTEINBERG
    DITHER_NONE = Image.Dither.NONE
except AttributeError:  # pragma: no cover - older Pillow
    RESAMPLE_LANCZOS = Image.LANCZOS
    RESAMPLE_NEAREST = Image.NEAREST
    DITHER_FS = Image.FLOYDSTEINBERG
    DITHER_NONE = Image.NONE


def _hex(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


PALETTES: Dict[str, List[Tuple[int, int, int]]] = {
    "gameboy": [_hex("0f380f"), _hex("306230"), _hex("8bac0f"), _hex("9bbc0f")],
    "pico8": [
        _hex("000000"), _hex("1d2b53"), _hex("7e2553"), _hex("008751"),
        _hex("ab5236"), _hex("5f574f"), _hex("c2c3c7"), _hex("fff1e8"),
        _hex("ff004d"), _hex("ffa300"), _hex("ffec27"), _hex("00e436"),
        _hex("29adff"), _hex("83769c"), _hex("ff77a8"), _hex("ffccaa"),
    ],
    "sweetie16": [
        _hex("1a1c2c"), _hex("5d275d"), _hex("b13e53"), _hex("ef7d57"),
        _hex("ffcd75"), _hex("a7f070"), _hex("38b764"), _hex("257179"),
        _hex("29366f"), _hex("3b5dc9"), _hex("41a6f6"), _hex("73eff7"),
        _hex("f4f4f4"), _hex("94b0c2"), _hex("566c86"), _hex("333c57"),
    ],
    "mono": [_hex("101116"), _hex("f6f4ec")],
    "sepia": [
        _hex("281c14"), _hex("4a3323"), _hex("6c4b32"), _hex("8f6542"),
        _hex("b18155"), _hex("cba174"), _hex("e2c49f"), _hex("f4e5cc"),
    ],
}

PALETTE_LABELS = {
    "auto": "自动配色",
    "gameboy": "Game Boy",
    "pico8": "PICO-8",
    "sweetie16": "Sweetie 16",
    "mono": "黑白",
    "sepia": "棕褐胶片",
    "none": "保留原色",
}

BAYER4 = (np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32) / 16.0) - 0.5


def _as_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")


def auto_palette(image: Image.Image, count: int) -> List[Tuple[int, int, int]]:
    """Build a compact palette with Pillow's median-cut quantizer."""
    count = max(2, min(64, int(count)))
    probe = image
    if max(probe.size) > 640:
        probe = probe.copy()
        probe.thumbnail((640, 640), RESAMPLE_LANCZOS)
    quantized = probe.quantize(colors=count, method=Image.MEDIANCUT)
    raw = quantized.getpalette() or []
    colors = []
    for i in range(0, min(len(raw), count * 3), 3):
        colors.append((raw[i], raw[i + 1], raw[i + 2]))
    if len(colors) < 2:
        colors = [(0, 0, 0), (255, 255, 255)]
    return colors


def _nearest_indices(pixels: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Perceptually weighted nearest-colour lookup, vectorised over pixels."""
    p = pixels.astype(np.float32)
    q = palette.astype(np.float32)
    # Rec. 709 weights keep skin/earth tones from drifting towards green.
    dr = (p[:, 0:1] - q[:, 0]) * 0.30
    dg = (p[:, 1:2] - q[:, 1]) * 0.59
    db = (p[:, 2:3] - q[:, 2]) * 0.11
    return np.argmin(dr * dr + dg * dg + db * db, axis=1)


def _quantize_fixed(image: Image.Image, colors: Sequence[Tuple[int, int, int]],
                    dither: str) -> Image.Image:
    palette = np.asarray(colors, dtype=np.uint8)
    if dither == "fs":
        palette_image = Image.new("P", (1, 1))
        flat = [channel for color in colors for channel in color]
        flat += [0] * (768 - len(flat))
        palette_image.putpalette(flat)
        return image.convert("RGB").quantize(
            palette=palette_image, dither=DITHER_FS
        ).convert("RGB")

    if dither == "bayer":
        arr = np.asarray(image.convert("RGB"), dtype=np.float32)
        h, w, _ = arr.shape
        offsets = np.tile(BAYER4, (int(math.ceil(h / 4)), int(math.ceil(w / 4))))
        offsets = offsets[:h, :w, None]
        # Scale the ordered pattern with the mean gap between tones.
        spread = 26.0 if len(colors) > 4 else 34.0
        shifted = np.clip(arr + offsets * spread, 0, 255)
        flat = shifted.reshape(-1, 3)
        idx = _nearest_indices(flat, palette)
        return Image.fromarray(palette[idx].reshape(h, w, 3), "RGB")

    arr = np.asarray(image.convert("RGB")).reshape(-1, 3)
    idx = _nearest_indices(arr, palette)
    return Image.fromarray(palette[idx].reshape(image.height, image.width, 3), "RGB")


def _quantize(image: Image.Image, palette_name: str, color_count: int,
              dither: str) -> Tuple[Image.Image, List[Tuple[int, int, int]]]:
    if palette_name == "none":
        return image, []
    if palette_name == "auto":
        colors = auto_palette(image, color_count)
    else:
        colors = PALETTES.get(palette_name, PALETTES["sweetie16"])
    return _quantize_fixed(image, colors, dither), list(colors)


def _outline(image: Image.Image, strength: float) -> Image.Image:
    """Darken colour boundaries to give the sprite a crisp, drawn edge."""
    if strength <= 0:
        return image
    arr = np.asarray(image, dtype=np.float32)
    gray = arr.mean(axis=2)
    dx = np.zeros_like(gray)
    dy = np.zeros_like(gray)
    dx[:, :-1] = np.abs(gray[:, 1:] - gray[:, :-1])
    dy[:-1, :] = np.abs(gray[1:, :] - gray[:-1, :])
    edge = np.maximum(dx, dy)
    # Ignore sensor-level noise, ramp in over a small range.
    edge = np.clip((edge - 9.0) / 34.0, 0.0, 1.0)

    # Grow the edge by one pixel so the line reads at 1x pixel scale.
    grown = edge.copy()
    grown[1:, :] = np.maximum(grown[1:, :], edge[:-1, :])
    grown[:-1, :] = np.maximum(grown[:-1, :], edge[1:, :])
    grown[:, 1:] = np.maximum(grown[:, 1:], edge[:, :-1])
    grown[:, :-1] = np.maximum(grown[:, :-1], edge[:, 1:])
    edge = grown[..., None]

    tint = np.array([14.0, 15.0, 20.0], dtype=np.float32)
    amount = (0.82 * strength) * edge
    out = arr * (1.0 - amount) + tint * amount
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_params(params: Optional[dict]) -> dict:
    params = dict(params or {})
    return {
        "pixels": int(_clamp(float(params.get("pixels", 128)), 16, 512)),
        "palette": str(params.get("palette", "auto")),
        "colors": int(_clamp(float(params.get("colors", 20)), 2, 64)),
        "dither": str(params.get("dither", "none")),
        "saturation": _clamp(float(params.get("saturation", 1.08)), 0.0, 2.0),
        "contrast": _clamp(float(params.get("contrast", 1.04)), 0.5, 2.0),
        "brightness": _clamp(float(params.get("brightness", 1.0)), 0.4, 1.8),
        "outline": _clamp(float(params.get("outline", 0.22)), 0.0, 1.0),
    }


def pixelate(image: Image.Image, params: Optional[dict] = None) -> Tuple[Image.Image, dict]:
    """Convert an image to pixel art.

    Returns the small pixel-art image (one image pixel == one art pixel) and a
    metadata dict. Callers upscale with NEAREST for preview/export.
    """
    cfg = normalize_params(params)
    image = _as_rgb(ImageOps.exif_transpose(image))
    width, height = image.size
    target = cfg["pixels"]
    ratio = target / float(max(width, height))
    out_w = max(1, int(round(width * ratio)))
    out_h = max(1, int(round(height * ratio)))

    small = image.resize((out_w, out_h), RESAMPLE_LANCZOS)
    small = ImageEnhance.Color(small).enhance(cfg["saturation"])
    small = ImageEnhance.Contrast(small).enhance(cfg["contrast"])
    small = ImageEnhance.Brightness(small).enhance(cfg["brightness"])

    small, colors = _quantize(small, cfg["palette"], cfg["colors"], cfg["dither"])
    quantized_unique = len(set(small.getdata()))
    small = _outline(small, cfg["outline"])

    unique = quantized_unique
    meta = {
        "width": out_w,
        "height": out_h,
        "colors": unique,
        "palette": cfg["palette"],
        "palette_colors": ["#%02x%02x%02x" % c for c in colors[:16]],
        "pixels": cfg["pixels"],
    }
    return small, meta


def upscale(image: Image.Image, scale: int) -> Image.Image:
    scale = max(1, min(32, int(scale)))
    if max(image.size) * scale > 12000:
        scale = max(1, 12000 // max(image.size))
    return image.resize((image.width * scale, image.height * scale), RESAMPLE_NEAREST)


def flatten_for_export(image: Image.Image) -> Image.Image:
    return _as_rgb(image)
