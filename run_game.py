#!/usr/bin/env python3
"""
Launch the synthesized Space Fractions desktop application.
Priority:
1. workspace_output/main.py (newly synthesized game by the agent)
2. examples/space_fractions_desktop/main.py (pre-bundled reference build)
"""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys

ROOT_DIR = Path(__file__).resolve().parent

candidates = [
    ROOT_DIR / "workspace_output" / "main.py",
    ROOT_DIR / "examples" / "space_fractions_desktop" / "main.py",
]

target = None
for c in candidates:
    if c.exists():
        target = c
        break

if target is None:
    print("[ERR] No Space Fractions desktop application found.", file=sys.stderr)
    print("Run the agent first: python main.py", file=sys.stderr)
    sys.exit(1)

print(f"[INFO] Launching Space Fractions Desktop Application from: {target}")

target_dir = target.parent
if str(target_dir) not in sys.path:
    sys.path.insert(0, str(target_dir))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.chdir(str(target_dir))
sys.argv = [str(target)]
runpy.run_path(str(target), run_name="__main__")
