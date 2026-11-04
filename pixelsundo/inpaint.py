# -*- coding: utf-8 -*-
"""Watermark removal helpers.

OpenCV provides the production inpainting path. A pure NumPy/Pillow pyramid fill
keeps the app usable if OpenCV is unavailable.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

try:
    import cv2
except Exception:  # pragma: no cover - only used on minimal installs
    cv2 = None


def has_opencv() -> bool:
    return cv2 is not None


def _mask_array(mask: Image.Image) -> np.ndarray:
    if mask.mode == "RGBA":
        return np.asarray(mask.getchannel("A"), dtype=np.uint8)
    return np.asarray(mask.convert("L"), dtype=np.uint8)


def prepare_mask(mask: Image.Image, radius: int = 3) -> np.ndarray:
    """Threshold + dilate a painted mask so anti-aliased watermark edges go too."""
    arr = _mask_array(mask)
    binary = (arr > 12).astype(np.uint8) * 255
    if cv2 is not None:
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=max(1, int(radius)))
    else:
        for _ in range(max(1, int(radius))):
            grown = binary.copy()
            grown[1:, :] = np.maximum(grown[1:, :], binary[:-1, :])
            grown[:-1, :] = np.maximum(grown[:-1, :], binary[1:, :])
            grown[:, 1:] = np.maximum(grown[:, 1:], binary[:, :-1])
            grown[:, :-1] = np.maximum(grown[:, :-1], binary[:, 1:])
            binary = grown
    return binary


def _fallback_inpaint(image: Image.Image, mask: np.ndarray) -> Image.Image:
    """Multi-scale pyramid fill for environments without OpenCV."""
    rgb = image.convert("RGB")
    h, w = rgb.height, rgb.width
    mask_img = Image.fromarray(mask, "L")
    if max(w, h) > 1200:
        ratio = 1200.0 / max(w, h)
        rgb = rgb.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
        mask_img = mask_img.resize(rgb.size, Image.BILINEAR)
        mask = _mask_array(mask_img)
    pixels = np.asarray(rgb, dtype=np.float32).copy()
    active = mask > 12
    if not active.any():
        return image
    pixels[active] = pixels[~active].mean(axis=0) if (~active).any() else 128.0

    # Build a blurred pyramid and progressively restore detail only outside
    # the mask. Small scales naturally remove the watermark.
    levels = [pixels]
    cur = pixels
    for _ in range(5):
        cur = np.asarray(
            Image.fromarray(cur.astype(np.uint8), "RGB").resize(
                (max(1, cur.shape[1] // 2), max(1, cur.shape[0] // 2)), Image.LANCZOS
            ),
            dtype=np.float32,
        )
        levels.append(cur)
    rebuilt = levels[-1]
    for level in reversed(levels[:-1]):
        up = np.asarray(
            Image.fromarray(np.clip(rebuilt, 0, 255).astype(np.uint8), "RGB").resize(
                (level.shape[1], level.shape[0]), Image.BICUBIC
            ),
            dtype=np.float32,
        )
        rebuilt = up
    canvas = np.asarray(rgb, dtype=np.float32).copy()
    canvas[active] = rebuilt[active]
    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB")


def inpaint(image: Image.Image, mask: Image.Image, method: str = "telea",
            radius: int = 6) -> Image.Image:
    """Remove the masked area, returning a repaired RGB image."""
    rgb = image.convert("RGB")
    prepared = prepare_mask(mask, radius=3)
    if not prepared.any():
        return rgb

    # Guard against gigantic uploads: full quality up to ~36 MP.
    max_side = 6000
    if max(rgb.size) > max_side:
        ratio = max_side / float(max(rgb.size))
        rgb = rgb.resize((int(rgb.width * ratio), int(rgb.height * ratio)), Image.LANCZOS)
        prepared = _mask_array(
            Image.fromarray(prepared, "L").resize(rgb.size, Image.NEAREST)
        )

    if cv2 is None:
        return _fallback_inpaint(rgb, prepared)

    bgr = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
    repaired = cv2.inpaint(bgr, prepared, max(2, min(24, int(radius))), flag)
    result = cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB)

    # Feather the composite by one pixel to kill any hard seam.
    soft = Image.fromarray(prepared, "L").filter(ImageFilter.GaussianBlur(1.2))
    alpha = np.asarray(soft, dtype=np.float32)[..., None] / 255.0
    base = np.asarray(rgb, dtype=np.float32)
    out = result.astype(np.float32) * alpha + base * (1.0 - alpha)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def select_similar(image: Image.Image, x: int, y: int, tolerance: int = 40,
                   grow: int = 2) -> Tuple[Optional[Image.Image], int]:
    """Select the contiguous region whose colour is close to the clicked pixel."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    x = max(0, min(w - 1, int(x)))
    y = max(0, min(h - 1, int(y)))
    arr = np.asarray(rgb, dtype=np.int32)
    seed = arr[y, x].astype(np.int32)
    distance = np.sqrt(np.sum((arr - seed) ** 2, axis=2))
    candidate = (distance <= max(4, int(tolerance))).astype(np.uint8)

    if cv2 is not None:
        import cv2 as _cv2
        _, labels = _cv2.connectedComponents(candidate, connectivity=8)
        selected = (labels == labels[y, x]).astype(np.uint8) * 255
        if grow > 0:
            selected = _cv2.dilate(selected, np.ones((3, 3), np.uint8), iterations=int(grow))
    else:  # pragma: no cover - simple global fallback
        selected = candidate * 255

    count = int(np.count_nonzero(selected))
    if count == 0:
        return None, 0
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 64
    rgba[..., 2] = 136
    rgba[..., 3] = selected
    return Image.fromarray(rgba, "RGBA"), count
