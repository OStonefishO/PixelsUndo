# -*- coding: utf-8 -*-
"""PixelsUndo desktop entry point: a native app window, not a browser tab."""
from __future__ import annotations

import ctypes
import http.client
import json
import multiprocessing
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path


def _show_error(message: str) -> None:
    try:
        base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        with open(str(base / "PixelsUndo-crash.log"), "a", encoding="utf-8") as fh:
            fh.write(message + "\n\n")
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "PixelsUndo 启动失败", 0x10)
    except Exception:
        pass


def _free_port(preferred: int = 8765) -> int:
    for port in range(preferred, preferred + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("8765-8794 端口都被占用")


def _wait_for_server(port: int, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
        try:
            conn.request("GET", "/api/health")
            if conn.getresponse().status == 200:
                return
        except OSError:
            time.sleep(0.15)
        finally:
            conn.close()
    raise RuntimeError("本地服务启动超时")


def _launch_app_window(url: str) -> bool:
    """Fallback for paths where pythonnet cannot load: a chromeless Edge app window."""
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    edge = next((p for p in candidates if p.exists()), None)
    if edge is None:
        return False
    profile = Path(tempfile.gettempdir()) / "PixelsUndo-window"
    profile.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            str(edge),
            "--app=" + url,
            "--window-size=1440,920",
            "--user-data-dir=" + str(profile),
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=msEdgeSidebarV2",
        ],
        creationflags=0x08000000,  # CREATE_NO_WINDOW; the Edge window itself is still shown
    )
    proc.wait()
    return True


def main() -> None:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        try:
            stream = open(str(base / "PixelsUndo-stderr.log"), "a", encoding="utf-8", buffering=1)
            sys.stdout = stream
            sys.stderr = stream
        except Exception:
            pass
    try:
        import webview
        from server import main as run_server

        port = _free_port()
        url = "http://127.0.0.1:%d" % port
        thread = threading.Thread(
            target=run_server,
            args=(["--no-browser", "--port", str(port)],),
            daemon=True,
        )
        thread.start()
        _wait_for_server(port)

        webview.create_window(
            "PixelsUndo · 像素画工作室",
            url,
            width=1440,
            height=920,
            min_size=(1024, 680),
            background_color="#080a0e",
        )
        # A real desktop window backed by Edge WebView2; no browser tab, no address bar.
        try:
            webview.start(debug=False, private_mode=False)
        except Exception:
            # pythonnet cannot load from non-ASCII install paths. Keep the native server
            # alive and open the same UI in Edge's chromeless app window instead.
            if not _launch_app_window(url):
                raise
    except BaseException:
        detail = traceback.format_exc(limit=10)
        _show_error(
            "PixelsUndo 无法启动。\n\n"
            "请确认程序文件夹没有被杀毒软件隔离，并且 8765-8794 端口未被占用。\n\n"
            + detail[-2200:]
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--server-only" in sys.argv:
        from server import main as _server_main

        _server_main([a for a in sys.argv[1:] if a != "--server-only"])
    else:
        main()
