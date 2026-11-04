# -*- coding: utf-8 -*-
"""PixelsUndo local application server.

A deliberately small, dependency-light HTTP server. It runs on loopback by
default and can expose itself to the local network (``--lan``) so a phone on
the same Wi-Fi can use the app. Uploaded images stay in the project's data
folder.
"""
from __future__ import annotations

import argparse
import base64
import hmac
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import socket
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote, unquote, urlparse

from PIL import Image, ImageOps

try:
    import segno
except ImportError:  # QR codes are an optional convenience only
    segno = None

from pixelsundo import __version__
from pixelsundo import engine
from pixelsundo import inpaint as repair

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
FROZEN = bool(getattr(sys, "frozen", False))
APP_HOME = Path(sys.executable).resolve().parent if FROZEN else ROOT
WEB_DIR = ROOT / "web"
DATA_DIR = APP_HOME / "data"
SESSION_DIR = DATA_DIR / "sessions"
SAMPLE_DIR = DATA_DIR / "samples"
LOG_DIR = DATA_DIR / "logs"
MAX_BODY = 120 * 1024 * 1024
MAX_SOURCE_SIDE = 6000
PREVIEW_SIDE = 1600
SESSION_RE = re.compile(r"^[a-f0-9]{32}$")
ACCESS_PASSWORD = os.environ.get("PIXELSUNDO_PASSWORD", "").strip()

for directory in (DATA_DIR, SESSION_DIR, SAMPLE_DIR, LOG_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# In a PyInstaller bundle the sample photos live in the read-only _MEIPASS
# folder; copy them next to the exe on first run so the UI can load them.
_bundled_samples = ROOT / "data" / "samples"
if _bundled_samples.is_dir() and _bundled_samples.resolve() != SAMPLE_DIR.resolve():
    for sample in _bundled_samples.glob("*.png"):
        target = SAMPLE_DIR / sample.name
        if not target.exists():
            try:
                shutil.copy2(str(sample), str(target))
            except OSError:
                pass


def lan_addresses():
    """Return usable IPv4 addresses for this machine, outbound first."""
    found = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            found.append(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    result = []
    for address in found:
        if not address or address.startswith(("127.", "169.254.", "0.")):
            continue
        if address not in result:
            result.append(address)
    return result


def network_info(bound_host, port):
    local_url = "http://127.0.0.1:%d" % port
    lan = bound_host not in ("127.0.0.1", "localhost", "::1")
    urls = []
    if lan:
        urls = ["http://%s:%d" % (address, port) for address in lan_addresses()]
    return {
        "lan": bool(lan and urls),
        "localUrl": local_url,
        "urls": urls,
        "primary": urls[0] if urls else local_url,
        "port": port,
    }


GITHUB_REPO = "OStonefishO/PixelsUndo"
RELEASES_URL = "https://github.com/%s/releases/latest" % GITHUB_REPO
UPDATE_API = "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
_update_cache = {"at": 0.0, "payload": None}


def _version_tuple(value: str):
    parts = []
    for chunk in str(value).lstrip("vV").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_update(force: bool = False) -> dict:
    """Ask GitHub for the newest release, caching for ten minutes."""
    now = time.time()
    if not force and _update_cache["payload"] and now - _update_cache["at"] < 600:
        return _update_cache["payload"]
    payload = {
        "ok": True,
        "current": __version__,
        "latest": __version__,
        "has_update": False,
        "url": RELEASES_URL,
        "notes": "",
        "published_at": "",
        "source": "github",
    }
    request = urlrequest.Request(
        UPDATE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PixelsUndo/" + __version__,
        },
    )
    try:
        with urlrequest.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
        latest = str(data.get("tag_name") or data.get("name") or "").strip()
        if latest:
            payload["latest"] = latest.lstrip("vV")
            payload["has_update"] = _version_tuple(payload["latest"]) > _version_tuple(__version__)
        payload["url"] = data.get("html_url") or RELEASES_URL
        payload["notes"] = str(data.get("body") or "")[:4000]
        payload["published_at"] = str(data.get("published_at") or "")
    except urlerror.HTTPError as exc:
        if exc.code == 404:
            payload["message"] = "还没有发布版本，当前已是最新开发版。"
        else:
            payload["ok"] = False
            payload["message"] = "检查更新失败（HTTP %d）" % exc.code
    except Exception as exc:
        payload["ok"] = False
        payload["message"] = "无法连接 GitHub：%s" % exc
    _update_cache["at"] = now
    _update_cache["payload"] = payload
    return payload

_log_handlers = [logging.FileHandler(str(LOG_DIR / "server.log"), encoding="utf-8")]
if sys.stderr is not None:
    _log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    handlers=_log_handlers,
)
LOG = logging.getLogger("pixelsundo")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def data_url(image: Image.Image, fmt: str = "PNG", quality: int = 92,
             max_side: Optional[int] = None) -> str:
    img = image
    if max_side and max(img.size) > max_side:
        copy = img.copy()
        copy.thumbnail((max_side, max_side), engine.RESAMPLE_LANCZOS)
        img = copy
    buffer = io.BytesIO()
    save_format = fmt.upper()
    if save_format in ("JPG", "JPEG"):
        img.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True)
        mime = "image/jpeg"
    elif save_format == "WEBP":
        img.save(buffer, "WEBP", quality=quality, method=4)
        mime = "image/webp"
    else:
        img.save(buffer, "PNG", optimize=True)
        mime = "image/png"
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:%s;base64,%s" % (mime, encoded)


def decode_data_url(value: str) -> Image.Image:
    if not isinstance(value, str) or "," not in value:
        raise ApiError("图片数据格式不正确")
    header, payload = value.split(",", 1)
    if "base64" not in header:
        raise ApiError("仅支持 Base64 图片数据")
    try:
        raw = base64.b64decode(payload, validate=False)
    except Exception:
        raise ApiError("图片数据无法解码")
    if len(raw) > 90 * 1024 * 1024:
        raise ApiError("图片超过 90MB 限制")
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        raise ApiError("无法识别该图片格式")
    return ImageOps.exif_transpose(image)


def _sessions_root() -> Path:
    return SESSION_DIR


def create_session(image: Image.Image, filename: str) -> Dict[str, Any]:
    image = ImageOps.exif_transpose(image).convert("RGB")
    if max(image.size) > MAX_SOURCE_SIDE:
        ratio = MAX_SOURCE_SIDE / float(max(image.size))
        image = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
            engine.RESAMPLE_LANCZOS,
        )
    if image.width * image.height > 40_000_000:
        ratio = (40_000_000 / float(image.width * image.height)) ** 0.5
        image = image.resize(
            (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
            engine.RESAMPLE_LANCZOS,
        )

    session_id = uuid.uuid4().hex
    folder = SESSION_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    version_file = "v0.png"
    image.save(folder / version_file, "PNG")
    meta = {
        "id": session_id,
        "name": Path(filename or "image").name[:160],
        "width": image.width,
        "height": image.height,
        "history": [version_file],
        "current": 0,
        "created": time.time(),
    }
    _write_meta(session_id, meta)
    return meta


def _write_meta(session_id: str, meta: Dict[str, Any]) -> None:
    path = SESSION_DIR / session_id / "session.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> Tuple[Dict[str, Any], Path, Path]:
    if not SESSION_RE.match(session_id or ""):
        raise ApiError("会话不存在，请重新打开图片", 404)
    folder = SESSION_DIR / session_id
    meta_path = folder / "session.json"
    if not meta_path.exists():
        raise ApiError("会话已过期，请重新打开图片", 404)
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except Exception:
        raise ApiError("会话数据损坏", 500)
    version = meta["history"][meta["current"]]
    image_path = folder / version
    if not image_path.exists():
        raise ApiError("图片版本丢失，请重新打开", 410)
    return meta, folder, image_path


def load_base(session_id: str) -> Tuple[Dict[str, Any], Path, Image.Image]:
    meta, folder, image_path = load_session(session_id)
    image = Image.open(image_path)
    image.load()
    return meta, folder, image.convert("RGB")


def session_state(meta: Dict[str, Any], folder: Path,
                  image: Optional[Image.Image] = None) -> Dict[str, Any]:
    if image is None:
        image = Image.open(folder / meta["history"][meta["current"]])
    return {
        "id": meta["id"],
        "name": meta.get("name", "image"),
        "width": meta["width"],
        "height": meta["height"],
        "image": data_url(image, "PNG", max_side=PREVIEW_SIDE),
        "version": meta["current"],
        "canUndo": meta["current"] > 0,
        "canRedo": meta["current"] < len(meta["history"]) - 1,
    }


def cleanup_sessions(days: int = 14) -> None:
    cutoff = time.time() - days * 86400
    for entry in SESSION_DIR.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


def _safe_name(name: str, fallback: str = "pixelsundo") -> str:
    name = Path(name or "").name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return (name or fallback)[:80]


class PixelsUndoHandler(BaseHTTPRequestHandler):
    server_version = "PixelsUndo/" + __version__
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- helpers
    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s  %s", self.address_string(), fmt % args)

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status)

    def _read_json(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ApiError("请求长度无效")
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ApiError("上传内容过大", 413)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError("请求数据不是有效 JSON")
        if not isinstance(payload, dict):
            raise ApiError("请求数据格式错误")
        return payload

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_error_json("页面不存在", 404)
            return
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime.endswith("javascript") or mime.endswith("json") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not ACCESS_PASSWORD:
            return True
        if urlparse(self.path).path == "/api/health":
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
        except Exception:
            return False
        _, _, password = decoded.partition(":")
        return hmac.compare_digest(password, ACCESS_PASSWORD)

    def _send_auth_required(self) -> None:
        body = "PixelsUndo 需要访问密码".encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="PixelsUndo"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -------------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send_auth_required()
            return
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        if route in ("/", "/index.html"):
            self._serve_file(WEB_DIR / "index.html")
            return
        if route == "/api/health":
            host, port = self.server.server_address[:2]
            net = network_info(host, port)
            self._send_json({
                "ok": True,
                "version": __version__,
                "opencv": repair.has_opencv(),
                "lan": net["lan"],
                "lanUrl": net["primary"] if net["lan"] else "",
            })
            return
        if route == "/api/update":
            query = parsed.query or ""
            force = "force=1" in query or "force=true" in query
            self._send_json({"ok": True, "update": check_update(force)})
            return
        if route == "/api/network":
            host, port = self.server.server_address[:2]
            self._send_json({"ok": True, **network_info(host, port)})
            return
        if route == "/api/qr.svg":
            if segno is None:
                self._send_error_json("二维码组件未安装，请重新运行启动脚本", 503)
                return
            host, port = self.server.server_address[:2]
            url = network_info(host, port)["primary"]
            buffer = io.BytesIO()
            qr = segno.make(url, error="m")
            qr.save(buffer, kind="svg", scale=8, border=2, dark="#101405", light="#f4ffd6")
            body = buffer.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if route.startswith("/api/"):
            self._send_error_json("接口不存在", 404)
            return
        candidate = (WEB_DIR / route.lstrip("/")).resolve()
        try:
            candidate.relative_to(WEB_DIR.resolve())
        except ValueError:
            self._send_error_json("禁止访问", 403)
            return
        self._serve_file(candidate)

    # ------------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send_auth_required()
            return
        route = urlparse(self.path).path
        try:
            if route == "/api/upload":
                self._handle_upload()
            elif route == "/api/sample":
                self._handle_sample()
            elif route == "/api/pixelate":
                self._handle_pixelate()
            elif route == "/api/inpaint":
                self._handle_inpaint()
            elif route == "/api/select":
                self._handle_select()
            elif route == "/api/undo":
                self._handle_history(-1)
            elif route == "/api/redo":
                self._handle_history(1)
            elif route == "/api/export":
                self._handle_export()
            elif route == "/api/shutdown":
                self._send_json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._send_error_json("接口不存在", 404)
        except ApiError as exc:
            self._send_error_json(exc.message, exc.status)
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            LOG.exception("Unhandled error on %s", route)
            self._send_error_json("处理失败：%s" % str(exc), 500)

    def _handle_upload(self) -> None:
        payload = self._read_json()
        image = decode_data_url(payload.get("image", ""))
        meta = create_session(image, str(payload.get("name") or "image.png"))
        LOG.info("uploaded %s  %dx%d", meta["name"], meta["width"], meta["height"])
        self._send_json({"ok": True, "session": session_state(meta, SESSION_DIR / meta["id"])})

    def _handle_sample(self) -> None:
        payload = self._read_json()
        kind = str(payload.get("kind") or "landscape")
        allowed = {"landscape": "sample-landscape.png", "watermark": "sample-watermark.png"}
        filename = allowed.get(kind, allowed["landscape"])
        path = SAMPLE_DIR / filename
        if not path.exists():
            raise ApiError("示例图片未安装", 404)
        image = Image.open(path)
        image.load()
        meta = create_session(image, filename)
        self._send_json({"ok": True, "session": session_state(meta, SESSION_DIR / meta["id"])})

    def _handle_pixelate(self) -> None:
        payload = self._read_json()
        started = time.time()
        meta, folder, image = load_base(str(payload.get("session") or ""))
        art, info = engine.pixelate(image, payload.get("params") or {})
        elapsed = int((time.time() - started) * 1000)
        self._send_json({
            "ok": True,
            "image": data_url(art, "PNG"),
            "outWidth": info["width"],
            "outHeight": info["height"],
            "colors": info["colors"],
            "palette": info["palette_colors"],
            "sourceWidth": meta["width"],
            "sourceHeight": meta["height"],
            "ms": elapsed,
        })

    def _handle_inpaint(self) -> None:
        payload = self._read_json()
        started = time.time()
        meta, folder, image = load_base(str(payload.get("session") or ""))
        if not payload.get("mask"):
            raise ApiError("请先涂抹或选取要修复的区域")
        mask_image = decode_data_url(payload.get("mask", ""))
        if mask_image.size != image.size:
            mask_image = mask_image.resize(image.size, Image.NEAREST)
        if not repair.prepare_mask(mask_image).any():
            raise ApiError("请先涂抹或选取要修复的区域")
        method = str(payload.get("method") or "telea")
        radius = int(payload.get("radius") or 6)
        repaired = repair.inpaint(image, mask_image, method=method, radius=radius)

        history = list(meta["history"])
        current = int(meta["current"])
        history = history[:current + 1]
        version_file = "v%d.png" % len(history)
        repaired.save(folder / version_file, "PNG")
        history.append(version_file)
        meta["history"] = history
        meta["current"] = len(history) - 1
        _write_meta(meta["id"], meta)
        elapsed = int((time.time() - started) * 1000)
        LOG.info("inpaint session=%s radius=%s %dms", meta["id"][:8], radius, elapsed)
        state = session_state(meta, folder, repaired)
        state["ms"] = elapsed
        self._send_json({"ok": True, **state})

    def _handle_select(self) -> None:
        payload = self._read_json()
        meta, folder, image = load_base(str(payload.get("session") or ""))
        x = int(payload.get("x") or 0)
        y = int(payload.get("y") or 0)
        tolerance = int(payload.get("tolerance") or 40)
        mask, count = repair.select_similar(image, x, y, tolerance=tolerance)
        if mask is None:
            raise ApiError("该位置没有可选取的区域")
        total = float(image.width * image.height)
        self._send_json({
            "ok": True,
            "mask": data_url(mask, "PNG"),
            "count": count,
            "coverage": count / total,
        })

    def _handle_history(self, direction: int) -> None:
        payload = self._read_json()
        meta, folder, _ = load_base(str(payload.get("session") or ""))
        new_index = int(meta["current"]) + direction
        new_index = max(0, min(len(meta["history"]) - 1, new_index))
        meta["current"] = new_index
        _write_meta(meta["id"], meta)
        image = Image.open(folder / meta["history"][new_index])
        image.load()
        state = session_state(meta, folder, image.convert("RGB"))
        state["ms"] = 0
        self._send_json({"ok": True, **state})

    def _handle_export(self) -> None:
        payload = self._read_json()
        meta, folder, image = load_base(str(payload.get("session") or ""))
        mode = str(payload.get("mode") or "pixel")
        scale = int(payload.get("scale") or 4)
        fmt = str(payload.get("format") or "png").lower()
        if fmt not in ("png", "jpg", "jpeg", "webp"):
            fmt = "png"
        quality = max(60, min(100, int(payload.get("quality") or 95)))
        if mode == "base":
            output = image
        else:
            art, _info = engine.pixelate(image, payload.get("params") or {})
            output = engine.upscale(art, scale)

        fmt_ext = "jpg" if fmt in ("jpg", "jpeg") else fmt
        base_name = _safe_name(str(payload.get("filename") or "pixelsundo"))
        filename = "%s.%s" % (base_name, fmt_ext)
        buffer = io.BytesIO()
        if fmt_ext == "jpg":
            output.convert("RGB").save(buffer, "JPEG", quality=quality, optimize=True, subsampling=0)
            mime = "image/jpeg"
        elif fmt_ext == "webp":
            output.convert("RGB").save(buffer, "WEBP", quality=quality, method=6)
            mime = "image/webp"
        else:
            output.save(buffer, "PNG", optimize=True)
            mime = "image/png"
        body = buffer.getvalue()
        escaped = quote(filename, safe="")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Disposition",
            "attachment; filename=\"pixelsundo.%s\"; filename*=UTF-8''%s" % (fmt_ext, escaped),
        )
        self.send_header("X-Output-Width", str(output.width))
        self.send_header("X-Output-Height", str(output.height))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def find_port(preferred: int = 8765, host: str = "127.0.0.1") -> int:
    for offset in range(0, 30):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用端口")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="PixelsUndo local server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="", help="bind address (default 127.0.0.1)")
    parser.add_argument("--lan", action="store_true", help="allow phones on the same Wi-Fi")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    host = args.host or ("0.0.0.0" if args.lan else "127.0.0.1")
    cleanup_sessions()
    port = find_port(args.port, host)
    server = ThreadingHTTPServer((host, port), PixelsUndoHandler)
    server.daemon_threads = True
    info = network_info(host, port)
    url = info["localUrl"]
    runtime_file = DATA_DIR / "runtime.json"
    try:
        runtime_file.write_text(
            json.dumps({
                "port": port,
                "pid": os.getpid(),
                "url": url,
                "lan": info["lan"],
                "lanUrl": info["primary"] if info["lan"] else "",
            }),
            encoding="utf-8",
        )
    except OSError:
        pass
    LOG.info("PixelsUndo %s running at %s", __version__, url)
    if info["lan"]:
        LOG.info("phone access on the same Wi-Fi: %s", info["primary"])
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            current = json.loads(runtime_file.read_text(encoding="utf-8"))
            if int(current.get("pid") or 0) == os.getpid():
                runtime_file.unlink()
        except (OSError, ValueError, TypeError):
            pass
        LOG.info("server stopped")


if __name__ == "__main__":
    main()
