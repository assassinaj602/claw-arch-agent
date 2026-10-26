from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import sys
import threading
from typing import Any

from src.agent.client import DeepSeekClient
from src.agent.preprocessor import ArchitecturePreprocessor
from src.agent.query_engine import QueryEngine
from src.agent.token_ledger import TokenLedger
from src.agent.tools import ToolRegistry

logger = logging.getLogger(__name__)


def run_headless_agent(
    doc_path: Path,
    view_path: Path,
    output_dir: Path,
    api_key: str,
    base_url: str = "https://api.deepseek.com/v1",
    model: str = "deepseek-v4-pro",
) -> dict[str, Any]:
    print(f"[INFO] Compiling architecture specifications from {doc_path} and {view_path}")
    preprocessor = ArchitecturePreprocessor(doc_path, view_path)
    ir = preprocessor.process()
    print(f"[PASS] Preprocessing finished. Identified {len(ir.diagrams)} diagrams and {len(ir.traceability_matrix)} requirements.")

    client = DeepSeekClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        log_callback=lambda msg: print(msg),
    )

    ledger = TokenLedger(budget_limit_usd=1.00)

    engine = QueryEngine(
        client=client,
        ir=ir,
        output_dir=output_dir,
        token_ledger=ledger,
        on_log=lambda msg: print(msg),
        on_token_update=lambda status: print(f"[TELEMETRY] {status}"),
        on_step=lambda curr, total: print(f"[PROGRESS] Turn {curr}/{total}"),
    )

    result = engine.run()
    print(f"[PASS] Agent completed execution. Total cost: ${result.get('total_cost_usd', 0.0):.4f} USD")
    return result


def start_web_server(port: int = 8080) -> None:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

    active_jobs: dict[str, Any] = {
        "status": "idle",
        "logs": [],
        "telemetry": "Tokens: 0 | Cost: $0.00 USD",
    }

    class WebHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/status":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(active_jobs).encode("utf-8"))
                return

            if parsed.path == "/" or parsed.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ClawArchAgent - Web Console</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #121212; color: #E0E0E0; margin: 20px; }
        .card { background: #1E1E1E; border: 1px solid #333; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
        input, select, button { background: #2A2A2A; color: #FFF; border: 1px solid #444; padding: 8px 12px; border-radius: 4px; margin: 4px 0; }
        button { background: #007ACC; cursor: pointer; font-weight: bold; border: none; }
        button:hover { background: #0098FF; }
        #console { background: #0A0A0A; border: 1px solid #222; border-radius: 4px; padding: 12px; height: 350px; overflow-y: auto; font-family: monospace; font-size: 13px; line-height: 1.4; }
        .log-INFO { color: #9CDCFE; }
        .log-PASS { color: #4EC9B0; }
        .log-FAIL { color: #F44747; }
        .log-WARN { color: #CE9178; }
        .telemetry { float: right; font-weight: bold; color: #4EC9B0; }
    </style>
</head>
<body>
    <h2>ClawArchAgent Web Interface (Fallback Service)</h2>
    <div class="card">
        <div>
            <label>API Key:</label><br>
            <input type="password" id="apiKey" style="width: 400px;" placeholder="DeepSeek or OpenRouter API key">
        </div>
        <div style="margin-top: 8px;">
            <label>Model:</label>
            <select id="model">
                <option value="deepseek-v4-pro">deepseek-v4-pro</option>
                <option value="deepseek-v4.1-flash:free">deepseek-v4.1-flash:free (TokenHarbor)</option>
                <option value="deepseek-chat">deepseek-chat</option>
                <option value="deepseek/deepseek-chat">deepseek/deepseek-chat (OpenRouter)</option>
            </select>
            <label style="margin-left: 16px;">Base URL:</label>
            <select id="baseUrl">
                <option value="https://api.deepseek.com/v1">https://api.deepseek.com/v1</option>
                <option value="https://tokenharbor.ai/v1">https://tokenharbor.ai/v1 (TokenHarbor)</option>
                <option value="https://openrouter.ai/api/v1">https://openrouter.ai/api/v1</option>
            </select>
        </div>
        <div style="margin-top: 12px;">
            <button onclick="triggerRun()">Trigger Code Agent</button>
            <span class="telemetry" id="telemetry">Tokens: 0 | Cost: $0.0000 USD</span>
        </div>
    </div>
    <div class="card">
        <h3>Live Execution Stream</h3>
        <div id="console"></div>
    </div>
    <script>
        async function triggerRun() {
            const key = document.getElementById("apiKey").value;
            const model = document.getElementById("model").value;
            const baseUrl = document.getElementById("baseUrl").value;
            await fetch("/api/run", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({api_key: key, model: model, base_url: baseUrl})
            });
        }
        setInterval(async () => {
            const res = await fetch("/api/status");
            const data = await res.json();
            document.getElementById("telemetry").innerText = data.telemetry;
            const con = document.getElementById("console");
            con.innerHTML = data.logs.map(l => {
                let cls = "INFO";
                for (let k of ["PASS", "FAIL", "WARN", "ERR"]) { if (l.includes("[" + k + "]")) cls = k; }
                return `<div class="log-${cls}">${l}</div>`;
            }).join("");
            con.scrollTop = con.scrollHeight;
        }, 800);
    </script>
</body>
</html>"""
                self.wfile.write(html.encode("utf-8"))
                return

            self.send_error(404, "Not Found")

        def do_POST(self) -> None:
            if self.path == "/api/run":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                req_data = json.loads(body.decode("utf-8"))

                api_key = req_data.get("api_key", "").strip()
                base_url = req_data.get("base_url", "https://api.deepseek.com/v1")
                model = req_data.get("model", "deepseek-v4-pro")

                def worker():
                    active_jobs["status"] = "running"
                    active_jobs["logs"] = ["[INFO] Initiated run from web console"]

                    def log_cb(msg):
                        active_jobs["logs"].append(msg)

                    def token_cb(stat):
                        active_jobs["telemetry"] = stat

                    try:
                        doc_path = Path("inputs/Architecture_Documentation.md").resolve()
                        view_path = Path("inputs/Architecture_View.md").resolve()
                        out_dir = Path("workspace_output").resolve()
                        out_dir.mkdir(parents=True, exist_ok=True)

                        preprocessor = ArchitecturePreprocessor(doc_path, view_path)
                        ir = preprocessor.process()
                        client = DeepSeekClient(api_key=api_key, base_url=base_url, model=model, log_callback=log_cb)
                        ledger = TokenLedger(budget_limit_usd=1.00)
                        engine = QueryEngine(
                            client=client,
                            ir=ir,
                            output_dir=out_dir,
                            token_ledger=ledger,
                            on_log=log_cb,
                            on_token_update=token_cb,
                        )
                        res = engine.run()
                        active_jobs["status"] = "finished"
                        log_cb(f"[PASS] Finished. Cost: ${res.get('total_cost_usd', 0.0):.4f} USD")
                    except Exception as err:
                        active_jobs["status"] = "error"
                        log_cb(f"[ERR] {err}")

                threading.Thread(target=worker, daemon=True).start()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "started"}).encode("utf-8"))
                return

            self.send_error(404, "Not Found")

    server = HTTPServer(("127.0.0.1", port), WebHandler)
    print(f"[INFO] Started fallback web dashboard on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Stopped web dashboard")


def main() -> None:
    parser = argparse.ArgumentParser(description="ClawArchAgent Headless & Web Fallback Runner")
    parser.add_argument("--web", action="store_true", help="Launch local web-based fallback service")
    parser.add_argument("--port", type=int, default=8080, help="Web service port (default: 8080)")
    parser.add_argument("--doc", default="inputs/Architecture_Documentation.md", help="Path to Architecture_Documentation.md")
    parser.add_argument("--view", default="inputs/Architecture_View.md", help="Path to Architecture_View.md")
    parser.add_argument("--out", default="workspace_output", help="Output directory")
    default_key = (
        os.environ.get("DEEPSEEK_API_KEY", "")
        or os.environ.get("TOKENHARBOR_API_KEY", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )
    parser.add_argument("--api-key", default=default_key, help="API key")
    parser.add_argument("--base-url", default="https://api.deepseek.com/v1", help="API Base URL")
    parser.add_argument("--model", default="deepseek-v4-pro", help="Model name")
    args = parser.parse_args()

    if args.web:
        start_web_server(args.port)
        return

    if not args.api_key:
        print("[ERR] API key required. Provide --api-key or export DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)

    run_headless_agent(
        doc_path=Path(args.doc),
        view_path=Path(args.view),
        output_dir=Path(args.out),
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
    )


if __name__ == "__main__":
    main()

