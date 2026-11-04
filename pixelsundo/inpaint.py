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


def _patch_fill(bgr: np.ndarray, mask: np.ndarray, patch: int = 5,
                candidates: int = 14, search: int = 40, step: int = 2) -> np.ndarray:
    """Boundary-first exemplar fill.

    Each masked pixel looks for a fully valid nearby patch whose *known* pixels
    match its own known neighbourhood, then copies the missing pixels.  It is
    slower than Telea but keeps clouds, water and straight edges instead of
    smearing them into a blur.
    """
    h, w = bgr.shape[:2]
    r = patch // 2
    out = bgr.copy()
    active = mask > 0
    padded = cv2.copyMakeBorder(out, r, r, r, r, cv2.BORDER_REFLECT)
    pmask = cv2.copyMakeBorder(mask, r, r, r, r, cv2.BORDER_CONSTANT, value=255)
    ys, xs = np.where(active)
    if not len(ys):
        return out
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    order = np.argsort(dist[ys, xs])
    ys, xs = ys[order], xs[order]
    if step > 1:
        ys, xs = ys[::step], xs[::step]
    rng = np.random.default_rng(7)
    for index in range(len(ys)):
        y, x = int(ys[index]), int(xs[index])
        ty, tx = y + r, x + r
        tp = padded[ty - r:ty + r + 1, tx - r:tx + r + 1]
        tm = pmask[ty - r:ty + r + 1, tx - r:tx + r + 1] > 0
        known = ~tm
        if int(known.sum()) < max(6, tm.size // 5):
            continue
        # Flat regions (sky, water) are better served by the smooth Telea
        # seed; synthesising patches there produces ghost clouds.  Only use
        # exemplars where the neighbourhood actually carries texture.
        if float(tp[known].std()) < 8.0:
            continue
        best = None
        best_score = 1e18
        for _ in range(candidates):
            sy = int(np.clip(y + rng.integers(-search, search + 1), 0, h - 1))
            sx = int(np.clip(x + rng.integers(-search, search + 1), 0, w - 1))
            if active[sy, sx]:
                continue
            spy, spx = sy + r, sx + r
            sp = padded[spy - r:spy + r + 1, spx - r:spx + r + 1]
            if (pmask[spy - r:spy + r + 1, spx - r:spx + r + 1] > 0).any():
                continue
            d = (tp[known].astype(np.float32) - sp[known].astype(np.float32)) ** 2
            score = float(d.mean())
            if score < best_score:
                best_score = score
                best = sp
        if best is not None and best_score < 1400.0:
            tp[tm] = best[tm]
            padded[ty - r:ty + r + 1, tx - r:tx + r + 1] = tp
    return padded[r:r + h, r:r + w]


def _content_inpaint(bgr: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    """Multi-scale patch synthesis, capped at 1600px for a predictable wait."""
    h, w = bgr.shape[:2]
    max_side = 1600
    scale0 = 1.0
    src = bgr
    m0 = mask
    if max(h, w) > max_side:
        scale0 = max_side / float(max(h, w))
        src = cv2.resize(bgr, (int(w * scale0), int(h * scale0)), interpolation=cv2.INTER_AREA)
        m0 = cv2.resize(mask, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_NEAREST)
    h0, w0 = src.shape[:2]
    search = max(24, min(90, int(radius) * 6))
    levels = [4, 2, 1]
    prev = None
    for level in levels:
        lh, lw = max(1, h0 // level), max(1, w0 // level)
        base = cv2.resize(src, (lw, lh), interpolation=cv2.INTER_AREA)
        lm = cv2.resize(m0, (lw, lh), interpolation=cv2.INTER_NEAREST)
        if prev is None:
            cur = cv2.inpaint(base, lm, 3, cv2.INPAINT_TELEA)
        else:
            cur = cv2.resize(prev, (lw, lh), interpolation=cv2.INTER_CUBIC)
            # Keep every known pixel sharp; only the hole comes from the coarser level.
            known = lm == 0
            cur[known] = base[known]
            cur = cv2.inpaint(cur, lm, 2, cv2.INPAINT_TELEA)
        if int((lm > 0).sum()) > 180:
            # The coarsest levels can afford to skip every other pixel; the
            # final level must fill every masked pixel, otherwise the skipped
            # pixels keep their Telea seed and show up as speckles.
            cur = _patch_fill(cur, lm, search=search, step=1 if level == 1 else 2)
        prev = cur
    result = cv2.resize(prev, (w, h), interpolation=cv2.INTER_CUBIC)
    known = mask == 0
    result[known] = bgr[known]
    return result


def inpaint(image: Image.Image, mask: Image.Image, method: str = "telea",
            radius: int = 6) -> Image.Image:
    """Remove the masked area, returning a repaired RGB image."""
    rgb = image.convert("RGB")
    # The radius slider controls how far the repaired edge is feathered/expanded;
    # the old code ignored it for the mask and only passed it to Telea.
    prepared = prepare_mask(mask, radius=max(1, int(radius) // 2))
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
    if method == "content":
        repaired = _content_inpaint(bgr, prepared, radius)
    elif method == "lama":
        try:
            from .lama import available, inpaint_bgr
            if not available():
                raise RuntimeError("LaMa model is not installed")
            repaired = inpaint_bgr(bgr, prepared)
        except Exception:
            # The model is optional; keep the editor usable without it.
            repaired = _content_inpaint(bgr, prepared, radius)
    else:
        flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
        repaired = cv2.inpaint(bgr, prepared, max(2, min(24, int(radius))), flag)
    result = cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB)

    # Feather the composite by one pixel to kill any hard seam.
    soft = Image.fromarray(prepared, "L").filter(
        ImageFilter.GaussianBlur(max(1.0, min(4.0, float(radius) * 0.35)))
    )
    alpha = np.asarray(soft, dtype=np.float32)[..., None] / 255.0
    base = np.asarray(rgb, dtype=np.float32)
    out = result.astype(np.float32) * alpha + base * (1.0 - alpha)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def select_similar(image: Image.Image, x: int, y: int, tolerance: int = 40,
                   grow: int = 2, global_mode: bool = False) -> Tuple[Optional[Image.Image], int]:
    """Select pixels whose colour is close to the clicked pixel.

    By default only the connected region is kept (a classic magic wand).  With
    ``global_mode`` every matching pixel in the image is selected, which is what
    catches a repeated translucent PIXELSTOCK-style watermark in one click.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    x = max(0, min(w - 1, int(x)))
    y = max(0, min(h - 1, int(y)))
    arr = np.asarray(rgb, dtype=np.int32)
    seed = arr[y, x].astype(np.int32)
    distance = np.sqrt(np.sum((arr - seed) ** 2, axis=2))
    candidate = (distance <= max(4, int(tolerance))).astype(np.uint8)

    if global_mode:
        selected = candidate * 255
    elif cv2 is not None:
        import cv2 as _cv2
        _, labels = _cv2.connectedComponents(candidate, connectivity=8)
        selected = (labels == labels[y, x]).astype(np.uint8) * 255
    else:  # pragma: no cover - simple global fallback
        selected = candidate * 255
    if cv2 is not None and grow > 0:
        selected = cv2.dilate(selected, np.ones((3, 3), np.uint8), iterations=int(grow))

    count = int(np.count_nonzero(selected))
    if count == 0:
        return None, 0
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 64
    rgba[..., 2] = 136
    rgba[..., 3] = selected
    return Image.fromarray(rgba, "RGBA"), count
