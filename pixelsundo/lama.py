# -*- coding: utf-8 -*-
"""Optional LaMa deep-inpainting backend.

The model is intentionally *not* required: if onnxruntime or the model file is
missing, the app keeps using the classical repair paths.  Keeping the import
lazy also keeps the Render/Linux image small.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional

import numpy as np

MODEL_NAME = "lama_fp32.onnx"
_MODEL_SIZE = 512
_session = None
_session_path: Optional[str] = None
_lock = threading.Lock()


def model_path() -> Optional[Path]:
    """Find the LaMa model next to the app, in the source tree, or via env."""
    env = os.environ.get("PIXELSUNDO_LAMA", "").strip().strip('"')
    candidates = []
    if env:
        candidates.append(Path(env))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "models" / MODEL_NAME)
    here = Path(__file__).resolve().parent.parent
    candidates.extend([
        here / "models" / MODEL_NAME,
        Path.cwd() / "models" / MODEL_NAME,
        Path.cwd() / MODEL_NAME,
    ])
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 10 * 1024 * 1024:
                return path
        except OSError:
            continue
    return None


def available() -> bool:
    if model_path() is None:
        return False
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False
    return True


def _get_session():
    global _session, _session_path
    path = model_path()
    if path is None:
        raise RuntimeError("找不到 LaMa 模型文件 models/lama_fp32.onnx")
    key = str(path.resolve())
    with _lock:
        if _session is not None and _session_path == key:
            return _session
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 4)))
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _session = ort.InferenceSession(
            key, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        _session_path = key
        return _session


def _to_uint8(rgb: np.ndarray) -> np.ndarray:
    arr = rgb.astype(np.float32, copy=False)
    if float(arr.max(initial=0.0)) <= 2.0:
        arr = arr * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)


def inpaint_bgr(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Run LaMa on a square crop around the mask and composite it back.

    The model is fixed at 512x512.  Cropping around the mask keeps far-away
    detail untouched and gives the model a tighter view of the repair.
    """
    import cv2

    h, w = bgr.shape[:2]
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return bgr.copy()

    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    margin = max(48, int(0.10 * min(h, w)))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    side = max(x1 - x0, y1 - y0) + margin * 2
    side = min(max(side, 256), max(h, w))
    left = max(0, min(w - side, cx - side // 2))
    top = max(0, min(h - side, cy - side // 2))
    right, bottom = min(w, left + side), min(h, top + side)
    crop = bgr[top:bottom, left:right]
    cmask = mask[top:bottom, left:right]

    # Keep the crop square so the fixed 512x512 model does not distort it.
    ch, cw = crop.shape[:2]
    size = max(ch, cw)
    square = np.zeros((size, size, 3), np.uint8)
    square_mask = np.zeros((size, size), np.uint8)
    ox, oy = (size - cw) // 2, (size - ch) // 2
    square[oy:oy + ch, ox:ox + cw] = crop
    square_mask[oy:oy + ch, ox:ox + cw] = cmask

    small = cv2.resize(square, (_MODEL_SIZE, _MODEL_SIZE), interpolation=cv2.INTER_AREA)
    small_mask = cv2.resize(square_mask, (_MODEL_SIZE, _MODEL_SIZE), interpolation=cv2.INTER_NEAREST)
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = np.transpose(rgb, (2, 0, 1))[None]
    mblob = (small_mask > 0).astype(np.float32)[None, None]

    session = _get_session()
    out = session.run(None, {"image": blob, "mask": mblob})[0]
    pred = _to_uint8(np.transpose(out[0], (1, 2, 0)))
    pred = cv2.cvtColor(pred, cv2.COLOR_RGB2BGR)

    # Crop away the letterbox before resizing back.  The letterbox lived in
    # the 1280-ish square, so its offsets must be scaled to the 512 output.
    ratio = _MODEL_SIZE / float(size)
    ox_s, oy_s = int(round(ox * ratio)), int(round(oy * ratio))
    cw_s, ch_s = int(round(cw * ratio)), int(round(ch * ratio))
    pred = pred[oy_s:oy_s + ch_s, ox_s:ox_s + cw_s]
    pred = cv2.resize(pred, (cw, ch), interpolation=cv2.INTER_CUBIC)
    alpha = cv2.GaussianBlur(cmask, (0, 0), max(1.0, min(3.0, min(ch, cw) / 200.0)))
    alpha = (alpha.astype(np.float32) / 255.0)[..., None]
    blended = pred.astype(np.float32) * alpha + crop.astype(np.float32) * (1.0 - alpha)
    result = bgr.copy()
    result[top:bottom, left:right] = np.clip(blended, 0, 255).astype(np.uint8)
    return result
