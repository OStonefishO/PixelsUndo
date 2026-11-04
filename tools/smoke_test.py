# -*- coding: utf-8 -*-
"""End-to-end smoke test for a running PixelsUndo server."""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"


def post(path, payload, raw=False):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
        if raw:
            return resp, body
        return json.loads(body.decode("utf-8"))


def data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    checks = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))
        print(("PASS " if condition else "FAIL ") + name + ("  " + detail if detail else ""))

    health = json.loads(urllib.request.urlopen(BASE + "/api/health", timeout=20).read())
    check("health", health.get("ok") and health.get("opencv"), str(health))

    sample = post("/api/sample", {"kind": "landscape"})
    sample = sample.get("session") or {}
    check("sample load", sample.get("id") and sample.get("width") == 1280, f"{sample.get('width')}x{sample.get('height')}")

    pixel = post("/api/pixelate", {
        "session": sample["id"],
        "params": {"pixels": 64, "palette": "pico8", "colors": 12, "dither": "bayer",
                   "saturation": 1.1, "contrast": 1.05, "brightness": 1.0, "outline": 0.2},
    })
    check("pixelate", pixel.get("ok") and pixel.get("outWidth") == 64, f"{pixel.get('outWidth')}x{pixel.get('outHeight')} {pixel.get('colors')} colors")

    resp, body = post("/api/export", {
        "session": sample["id"], "mode": "pixel", "scale": 4, "format": "png",
        "filename": "像素画 测试", "quality": 95,
    }, raw=True)
    disp = resp.headers.get("Content-Disposition", "")
    check("export bytes", len(body) > 1000 and body[:8] == b"\x89PNG\r\n\x1a\n", f"{len(body)} bytes")
    check("export unicode header", "filename*=UTF-8''" in disp and "%E5%83%8F" in disp, disp)

    wm = post("/api/sample", {"kind": "watermark"})
    wm = wm.get("session") or {}
    check("watermark sample", wm.get("id"), f"{wm.get('width')}x{wm.get('height')}")
    select = post("/api/select", {"session": wm["id"], "x": 420, "y": 250, "tolerance": 60})
    check("select mask", select.get("ok") and select.get("coverage", 0) > 0, f"coverage={select.get('coverage', 0):.4f}")
    check("mask png rgba", select.get("mask", "").startswith("data:image/png;base64,"))

    repaired = post("/api/inpaint", {
        "session": wm["id"], "mask": select["mask"], "method": "telea", "radius": 6,
    })
    check("inpaint", repaired.get("ok") and repaired.get("canUndo"), f"{repaired.get('ms')} ms")
    undid = post("/api/undo", {"session": wm["id"]})
    check("undo", undid.get("ok") and undid.get("canRedo"), f"v{undid.get('version')}")
    redid = post("/api/redo", {"session": wm["id"]})
    check("redo", redid.get("ok"), f"v{redid.get('version')}")

    try:
        post("/api/inpaint", {"session": wm["id"], "mask": "data:image/png;base64,", "method": "telea", "radius": 6})
        check("empty mask rejected", False, "no error raised")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        check("empty mask rejected", exc.code == 400, detail[:120])

    failed = [name for name, ok, _ in checks if not ok]
    print("\n%d/%d passed" % (len(checks) - len(failed), len(checks)))
    if failed:
        print("failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
