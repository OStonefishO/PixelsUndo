# -*- coding: utf-8 -*-
"""Frozen desktop entry point for PixelsUndo.

The browser UI is still the product; this wrapper starts the LAN-enabled local
server, opens the browser and shows a native error box if startup fails.
"""
from __future__ import annotations

import ctypes
import multiprocessing
import sys
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
        ctypes.windll.user32.MessageBoxW(
            0, message, "PixelsUndo 启动失败", 0x10
        )
    except Exception:
        pass


def main() -> None:
    try:
        from server import main as run_server
        run_server(["--lan"])
    except BaseException:
        detail = traceback.format_exc(limit=8)
        _show_error(
            "PixelsUndo 无法启动。\n\n"
            "请确认程序文件夹没有被杀毒软件隔离，并且 8765-8795 端口未被占用。\n\n"
            + detail[-1800:]
        )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
