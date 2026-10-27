#!/usr/bin/env python3
"""
ClawArchAgent Root Entry Point
Supports both Desktop GUI and Headless CLI modes.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _has_graphical_display() -> bool:
    if sys.platform.startswith("win") or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def run_cli(args: argparse.Namespace) -> None:
    from src.agent.client import DeepSeekClient
    from src.agent.preprocessor import ArchitecturePreprocessor
    from src.agent.query_engine import QueryEngine
    from src.agent.token_ledger import TokenLedger

    doc_path = Path(args.doc).resolve()
    view_path = Path(args.view).resolve()
    out_dir = Path(args.out).resolve()

    if not doc_path.exists():
        print(f"[ERR] Architecture documentation not found: {doc_path}", file=sys.stderr)
        sys.exit(1)
    if not view_path.exists():
        print(f"[ERR] Architecture view not found: {view_path}", file=sys.stderr)
        sys.exit(1)

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("[ERR] API key required. Provide --api-key or set DEEPSEEK_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Compiling architecture specifications from {doc_path} and {view_path}")
    preprocessor = ArchitecturePreprocessor(doc_path, view_path)
    ir = preprocessor.process()
    print(f"[PASS] Preprocessing finished. Identified {len(ir.diagrams)} diagrams and {len(ir.traceability_matrix)} requirements.")

    client = DeepSeekClient(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        log_callback=lambda msg: print(msg),
    )

    ledger = TokenLedger(budget_limit_usd=1.00)

    engine = QueryEngine(
        client=client,
        ir=ir,
        output_dir=out_dir,
        token_ledger=ledger,
        on_log=lambda msg: print(msg),
        on_token_update=lambda status: print(f"[TELEMETRY] {status}"),
        on_step=lambda curr, total: print(f"[PROGRESS] Turn {curr}/{total}"),
    )

    result = engine.run()
    cost = result.get("total_cost_usd", 0.0)
    print(f"\n[PASS] Agent pipeline completed successfully!")
    print(f"[INFO] Synthesized deliverables written to: {out_dir}")
    print(f"[INFO] Total Token Cost: ${cost:.4f} USD (Budget ceiling: $1.00 USD)")
    print(f"[INFO] Launch generated desktop game: python run_game.py\n")


def main() -> None:
    # Forward --run-target directly to main_gui if passed
    if len(sys.argv) >= 3 and sys.argv[1] == "--run-target":
        from src.main_gui import main as gui_main
        gui_main()
        return

    parser = argparse.ArgumentParser(
        description="ClawArchAgent: Architecture-Driven Autonomous Code Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--cli", action="store_true", help="Force headless CLI mode instead of Desktop GUI")
    parser.add_argument("--gui", action="store_true", help="Force Desktop GUI mode")
    parser.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY", ""), help="DeepSeek API Key")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1", help="DeepSeek API base URL")
    parser.add_argument("--model", default="deepseek-chat", help="Model name (e.g., deepseek-chat, deepseek-v4.1-flash:free)")
    parser.add_argument("--doc", default="inputs/Architecture_Documentation.md", help="Path to Architecture Documentation")
    parser.add_argument("--view", default="inputs/Architecture_View.md", help="Path to Architecture View (PlantUML)")
    parser.add_argument("--out", default="workspace_output", help="Directory where generated desktop game will be written")

    args, unknown = parser.parse_known_args()

    # Determine execution mode:
    # If explicitly --cli or if no graphical display is available, run CLI
    if args.cli:
        run_cli(args)
    elif args.gui or _has_graphical_display():
        from src.main_gui import main as gui_main
        gui_main()
    else:
        print("[INFO] No graphical display detected. Falling back to CLI mode...")
        run_cli(args)


if __name__ == "__main__":
    main()
