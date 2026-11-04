# -*- coding: utf-8 -*-
"""Double-click friendly launcher for PixelsUndo.

Starts the local server in the background (or reuses a running instance),
waits until it answers, then opens the browser. Intended to be started with
pythonw.exe so no console window is left behind.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RUNTIME = DATA_DIR / "runtime.json"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "launcher.log"


def log(message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except OSError:
        pass


def alert(message: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "PixelsUndo", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def healthy(url: str, timeout: float = 1.2) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ok"))
    except Exception:
        return False


def known_url() -> str:
    try:
        payload = json.loads(RUNTIME.read_text(encoding="utf-8"))
        url = str(payload.get("url") or "")
        if url.startswith("http://127.0.0.1:") and healthy(url):
            return url
    except (OSError, ValueError, TypeError):
        pass
    return ""


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = known_url()
    if existing:
        webbrowser.open(existing)
        return 0

    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")

    flags = 0
    if os.name == "nt":
        # python.exe (not pythonw.exe) is used because some Windows firewall
        # rules explicitly block pythonw.exe inbound traffic. CREATE_NO_WINDOW
        # keeps the background server invisible, just like pythonw.
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    log("starting server with %s" % python)
    try:
        subprocess.Popen(
            [str(python), str(ROOT / "server.py"), "--no-browser", "--lan"],
            cwd=str(ROOT),
            creationflags=flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        log("failed to start server: %s" % exc)
        alert("PixelsUndo 启动失败：%s\n请查看 data\\logs\\launcher.log" % exc)
        return 1

    url = ""
    deadline = time.time() + 20
    while time.time() < deadline:
        url = known_url()
        if url:
            break
        time.sleep(0.25)

    if not url:
        log("server did not become ready")
        alert("PixelsUndo 未能启动。\n请查看 data\\logs\\server.log 排查原因。")
        return 1

    log("ready at %s" % url)
    webbrowser.open(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
