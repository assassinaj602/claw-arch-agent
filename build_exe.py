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
        str(root / "main.py"),
    ]

    print(f"[INFO] Executing PyInstaller build on {sys.platform}...")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=str(root))
    if res.returncode != 0:
        print(f"[ERR] PyInstaller build failed with exit code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)

    print("[PASS] Standalone executable build succeeded in dist/")


def build_game() -> None:
    sep = ";" if sys.platform.startswith("win") else ":"
    root = Path(__file__).resolve().parent

    examples_dir = root / "examples"
    workspace_dir = root / "workspace_output"

    add_data_args = ["--add-data", f"{examples_dir}{sep}examples"]
    if workspace_dir.exists():
        add_data_args.extend(["--add-data", f"{workspace_dir}{sep}workspace_output"])

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "SpaceFractions",
        *add_data_args,
        "--hidden-import",
        "tkinter",
        "--hidden-import",
        "tkinter.ttk",
        "--hidden-import",
        "tkinter.messagebox",
        "--hidden-import",
        "sqlite3",
        "--hidden-import",
        "random",
        "--hidden-import",
        "math",
        "--hidden-import",
        "json",
        "--hidden-import",
        "runpy",
        str(root / "run_game.py"),
    ]

    print(f"\n[INFO] Executing PyInstaller build for SpaceFractions desktop game on {sys.platform}...")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=str(root))
    if res.returncode != 0:
        print(f"[ERR] PyInstaller game build failed with exit code {res.returncode}", file=sys.stderr)
        sys.exit(res.returncode)

    print("[PASS] Standalone SpaceFractions.exe build succeeded in dist/")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build desktop executables")
    parser.add_argument("--agent-only", action="store_true", help="Build only ClawArchAgent.exe")
    parser.add_argument("--game-only", action="store_true", help="Build only SpaceFractions.exe")
    args = parser.parse_args()

    if args.game_only:
        build_game()
    elif args.agent_only:
        build()
    else:
        build()
        build_game()

