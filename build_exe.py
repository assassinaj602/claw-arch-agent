from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def build() -> None:
    sep = ";" if sys.platform.startswith("win") else ":"
    root = Path(__file__).resolve().parent

    inputs_dir = root / "inputs"
    add_data_arg = f"{inputs_dir}{sep}inputs"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "ClawArchAgent",
        "--add-data",
        add_data_arg,
        "--hidden-import",
        "tkinter",
        "--hidden-import",
        "tkinter.ttk",
        "--hidden-import",
        "tkinter.filedialog",
        "--hidden-import",
        "tkinter.messagebox",
        "--hidden-import",
        "tkinter.scrolledtext",
        "--hidden-import",
        "sqlite3",
        "--hidden-import",
        "unittest",
        "--hidden-import",
        "doctest",
        "--hidden-import",
        "http.server",
        "--hidden-import",
        "httpx",
        "--hidden-import",
        "openai",
        "--hidden-import",
        "runpy",
        str(root / "src" / "main_gui.py"),
    ]

    print(f"[INFO] Executing PyInstaller build on {sys.platform}...")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=str(root))
    if res.returncode != 0:
        print(f"[ERR] PyInstaller build failed with exit code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)

    print("[PASS] Standalone executable build succeeded in dist/")


if __name__ == "__main__":
    build()

