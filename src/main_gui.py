from __future__ import annotations

import os
from pathlib import Path
import queue
import runpy
import subprocess
import sys
import threading
from typing import Any

# CLI intercept for running target applications using the bundled runtime
if len(sys.argv) >= 3 and sys.argv[1] == "--run-target":
    target_path = Path(sys.argv[2]).resolve()
    if not target_path.exists():
        sys.stderr.write(f"[ERR] Target script not found: {target_path}\n")
        sys.exit(1)

    project_dir = target_path.parent
    if (project_dir.parent / "components").exists():
        project_dir = project_dir.parent

    sys.path.insert(0, str(project_dir))
    if str(target_path.parent) not in sys.path:
        sys.path.insert(0, str(target_path.parent))

    os.chdir(str(project_dir))
    sys.argv = [str(target_path)] + sys.argv[3:]
    runpy.run_path(str(target_path), run_name="__main__")
    sys.exit(0)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# Ensure root directory is on sys.path for direct execution
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.agent.client import DeepSeekClient
from src.agent.preprocessor import ArchitecturePreprocessor
from src.agent.query_engine import QueryEngine
from src.agent.token_ledger import TokenLedger
from src.agent.tools import ToolRegistry


def resolve_asset_path(rel_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        meipass_candidate = Path(getattr(sys, "_MEIPASS")) / rel_path
        if meipass_candidate.exists():
            return meipass_candidate

    workspace_candidate = Path(__file__).resolve().parent.parent / rel_path
    if workspace_candidate.exists():
        return workspace_candidate

    return Path(rel_path).resolve()


class AgentApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ClawArchAgent - Architecture to Desktop Code Agent")
        self.root.geometry("980x760")
        self.root.minsize(800, 600)

        self.ui_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.active_engine: QueryEngine | None = None

        self._init_variables()
        self._build_layout()
        self._start_queue_poller()

    def _init_variables(self) -> None:
        default_key = (
            os.environ.get("DEEPSEEK_API_KEY", "")
            or os.environ.get("TOKENHARBOR_API_KEY", "")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        self.api_key_var = tk.StringVar(value=default_key)
        self.show_key_var = tk.BooleanVar(value=False)

        default_base_url = "https://api.deepseek.com/v1"
        default_model = "deepseek-v4-pro"

        if os.environ.get("TOKENHARBOR_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
            default_base_url = "https://tokenharbor.ai/v1"
            default_model = "deepseek-v4.1-flash:free"
        elif os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
            default_base_url = "https://openrouter.ai/api/v1"

        self.base_url_var = tk.StringVar(value=default_base_url)
        self.model_var = tk.StringVar(value=default_model)

        default_doc = resolve_asset_path("inputs/Architecture_Documentation.md")
        default_view = resolve_asset_path("inputs/Architecture_View.md")
        self.doc_path_var = tk.StringVar(value=str(default_doc) if default_doc.exists() else "")
        self.view_path_var = tk.StringVar(value=str(default_view) if default_view.exists() else "")

        default_out = (Path.cwd() / "workspace_output").resolve()
        self.out_dir_var = tk.StringVar(value=str(default_out))

        self.status_var = tk.StringVar(value="Status: Ready")
        self.telemetry_var = tk.StringVar(value="Tokens: 0 | Cost: $0.0000 USD / $1.00 Limit")

    def _build_layout(self) -> None:
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        config_frame = ttk.LabelFrame(main_frame, text="LLM API Gateway Configuration", padding="10")
        config_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(config_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=3)
        self.key_entry = ttk.Entry(config_frame, textvariable=self.api_key_var, show="*", width=45)
        self.key_entry.grid(row=0, column=1, sticky=tk.W, padx=4, pady=3)

        show_cb = ttk.Checkbutton(config_frame, text="Show", variable=self.show_key_var, command=self._toggle_show_key)
        show_cb.grid(row=0, column=2, sticky=tk.W, padx=4, pady=3)

        ttk.Label(config_frame, text="Base URL:").grid(row=0, column=3, sticky=tk.W, padx=(16, 4), pady=3)
        base_url_cb = ttk.Combobox(
            config_frame,
            textvariable=self.base_url_var,
            values=["https://api.deepseek.com/v1", "https://tokenharbor.ai/v1", "https://openrouter.ai/api/v1"],
            width=28,
        )
        base_url_cb.grid(row=0, column=4, sticky=tk.W, padx=4, pady=3)

        ttk.Label(config_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=3)
        model_cb = ttk.Combobox(
            config_frame,
            textvariable=self.model_var,
            values=[
                "deepseek-v4-pro",
                "deepseek-v4.1-flash:free",
                "deepseek-chat",
                "deepseek-reasoner",
                "deepseek/deepseek-chat",
            ],
            width=28,
        )
        model_cb.grid(row=1, column=1, sticky=tk.W, padx=4, pady=3)

        paths_frame = ttk.LabelFrame(main_frame, text="Input Architecture Specifications & Workspace", padding="10")
        paths_frame.pack(fill=tk.X, pady=(0, 8))
        paths_frame.columnconfigure(1, weight=1)

        ttk.Label(paths_frame, text="Architecture Doc:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=3)
        ttk.Entry(paths_frame, textvariable=self.doc_path_var).grid(row=0, column=1, sticky=tk.EW, padx=4, pady=3)
        ttk.Button(paths_frame, text="Browse...", command=self._browse_doc).grid(row=0, column=2, padx=4, pady=3)

        ttk.Label(paths_frame, text="Architecture Views:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=3)
        ttk.Entry(paths_frame, textvariable=self.view_path_var).grid(row=1, column=1, sticky=tk.EW, padx=4, pady=3)
        ttk.Button(paths_frame, text="Browse...", command=self._browse_view).grid(row=1, column=2, padx=4, pady=3)

        ttk.Label(paths_frame, text="Target Output Dir:").grid(row=2, column=0, sticky=tk.W, padx=4, pady=3)
        ttk.Entry(paths_frame, textvariable=self.out_dir_var).grid(row=2, column=1, sticky=tk.EW, padx=4, pady=3)
        ttk.Button(paths_frame, text="Browse...", command=self._browse_out).grid(row=2, column=2, padx=4, pady=3)

        action_frame = ttk.Frame(main_frame, padding="4")
        action_frame.pack(fill=tk.X, pady=(0, 6))

        self.btn_run = ttk.Button(action_frame, text="Run Code Agent", command=self._start_agent)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        self.btn_stop = ttk.Button(action_frame, text="Stop", command=self._stop_agent, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        self.btn_verify = ttk.Button(action_frame, text="Verify Output", command=self._verify_output)
        self.btn_verify.pack(side=tk.LEFT, padx=4)

        self.btn_launch = ttk.Button(action_frame, text="Launch Generated Game", command=self._launch_game)
        self.btn_launch.pack(side=tk.LEFT, padx=4)

        self.btn_clear = ttk.Button(action_frame, text="Clear Console", command=self._clear_console)
        self.btn_clear.pack(side=tk.RIGHT, padx=4)

        telemetry_frame = ttk.Frame(main_frame, padding="2")
        telemetry_frame.pack(fill=tk.X, pady=(0, 6))

        lbl_status = ttk.Label(telemetry_frame, textvariable=self.status_var, font=("Segoe UI", 9, "bold"))
        lbl_status.pack(side=tk.LEFT, padx=4)

        lbl_telemetry = ttk.Label(telemetry_frame, textvariable=self.telemetry_var, font=("Consolas", 9))
        lbl_telemetry.pack(side=tk.RIGHT, padx=4)

        console_frame = ttk.LabelFrame(main_frame, text="Agent Execution Log & Diagnostics", padding="6")
        console_frame.pack(fill=tk.BOTH, expand=True)

        self.console = ScrolledText(
            console_frame,
            wrap=tk.WORD,
            bg="#181818",
            fg="#D4D4D4",
            insertbackground="#FFFFFF",
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        self.console.pack(fill=tk.BOTH, expand=True)

        self.console.tag_config("INFO", foreground="#9CDCFE")
        self.console.tag_config("WARN", foreground="#CE9178")
        self.console.tag_config("ERR", foreground="#F44747")
        self.console.tag_config("PASS", foreground="#4EC9B0")
        self.console.tag_config("FAIL", foreground="#F44747")
        self.console.tag_config("TOOL", foreground="#DCDCAA")
        self.console.tag_config("STEP", foreground="#C586C0")

        self._append_log("[INFO] ClawArchAgent initialized.")
        self._append_log(f"[INFO] Runtime interpreter: {sys.executable}")
        self._append_log("[INFO] Ready. Configure API key and trigger execution.")

    def _toggle_show_key(self) -> None:
        self.key_entry.config(show="" if self.show_key_var.get() else "*")

    def _browse_doc(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select Architecture Documentation",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if filename:
            self.doc_path_var.set(filename)

    def _browse_view(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select Architecture View",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if filename:
            self.view_path_var.set(filename)

    def _browse_out(self) -> None:
        directory = filedialog.askdirectory(title="Select Target Output Directory")
        if directory:
            self.out_dir_var.set(directory)

    def _clear_console(self) -> None:
        self.console.delete("1.0", tk.END)

    def _append_log(self, text: str) -> None:
        tag = None
        for candidate in ("INFO", "WARN", "ERR", "PASS", "FAIL", "TOOL", "STEP"):
            if f"[{candidate}]" in text:
                tag = candidate
                break

        self.console.insert(tk.END, text + "\n", tag)
        self.console.see(tk.END)

    def _start_queue_poller(self) -> None:
        self._drain_queue()
        self.root.after(50, self._start_queue_poller)

    def _drain_queue(self) -> None:
        while not self.ui_queue.empty():
            try:
                msg_type, payload = self.ui_queue.get_nowait()
                if msg_type == "log":
                    self._append_log(payload)
                elif msg_type == "token":
                    self.telemetry_var.set(payload)
                elif msg_type == "status":
                    self.status_var.set(f"Status: {payload}")
                elif msg_type == "done":
                    self._on_agent_finished(payload)
                elif msg_type == "error":
                    self._on_agent_error(payload)
            except queue.Empty:
                break

    def _start_agent(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Missing API Key", "Please enter a valid DeepSeek or OpenRouter API key.")
            return

        doc_path = Path(self.doc_path_var.get().strip())
        view_path = Path(self.view_path_var.get().strip())
        out_dir = Path(self.out_dir_var.get().strip())

        if not doc_path.exists():
            messagebox.showerror("File Not Found", f"Architecture documentation not found: {doc_path}")
            return
        if not view_path.exists():
            messagebox.showerror("File Not Found", f"Architecture view not found: {view_path}")
            return

        out_dir.mkdir(parents=True, exist_ok=True)

        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_var.set("Status: Running...")

        self.worker_thread = threading.Thread(
            target=self._run_agent_worker,
            args=(api_key, self.base_url_var.get().strip(), self.model_var.get().strip(), doc_path, view_path, out_dir),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_agent_worker(
        self,
        api_key: str,
        base_url: str,
        model: str,
        doc_path: Path,
        view_path: Path,
        out_dir: Path,
    ) -> None:
        try:
            self.ui_queue.put(("log", "[INFO] Preprocessing architectural specifications into JSON IR"))
            preprocessor = ArchitecturePreprocessor(doc_path, view_path)
            ir = preprocessor.process()
            self.ui_queue.put(("log", f"[PASS] Preprocessing complete. Extracted {len(ir.diagrams)} diagrams."))

            client = DeepSeekClient(
                api_key=api_key,
                base_url=base_url,
                model=model,
                log_callback=lambda msg: self.ui_queue.put(("log", msg)),
            )

            ledger = TokenLedger(budget_limit_usd=1.00)

            self.active_engine = QueryEngine(
                client=client,
                ir=ir,
                output_dir=out_dir,
                token_ledger=ledger,
                on_log=lambda msg: self.ui_queue.put(("log", msg)),
                on_token_update=lambda status: self.ui_queue.put(("token", status)),
                on_step=lambda curr, total: self.ui_queue.put(("status", f"Running turn {curr}/{total}")),
            )

            result = self.active_engine.run()
            self.ui_queue.put(("done", result))

        except Exception as exc:
            self.ui_queue.put(("error", str(exc)))

    def _stop_agent(self) -> None:
        if self.active_engine:
            self.active_engine.request_cancel()
            self.status_var.set("Status: Cancelling...")
            self.btn_stop.config(state=tk.DISABLED)

    def _on_agent_finished(self, summary: dict[str, Any]) -> None:
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("Status: Finished")
        cost = summary.get("total_cost_usd", 0.0)
        turns = summary.get("total_turns", 0)
        completed = summary.get("completed", False)
        self._append_log(
            f"[PASS] Agent completed execution in {turns} turns. Total cost: ${cost:.4f} USD. (Verified: {completed})"
        )

    def _on_agent_error(self, err_msg: str) -> None:
        self.btn_run.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_var.set("Status: Error")
        self._append_log(f"[ERR] Execution halted: {err_msg}")
        messagebox.showerror("Execution Error", err_msg)

    def _verify_output(self) -> None:
        out_dir = Path(self.out_dir_var.get().strip())
        if not out_dir.exists():
            messagebox.showwarning("Workspace Missing", "Target output directory does not exist.")
            return

        doc_path = Path(self.doc_path_var.get().strip())
        view_path = Path(self.view_path_var.get().strip())
        if not doc_path.exists() or not view_path.exists():
            messagebox.showwarning("Input Missing", "Input architecture files required for verification.")
            return

        try:
            preprocessor = ArchitecturePreprocessor(doc_path, view_path)
            ir = preprocessor.process()
            registry = ToolRegistry(out_dir, ir)
            report = registry.run_verification()
            self._append_log("\n--- Manual Output Verification ---")
            for line in report.splitlines():
                self._append_log(line)
        except Exception as exc:
            messagebox.showerror("Verification Error", str(exc))

    def _launch_game(self) -> None:
        out_dir = Path(self.out_dir_var.get().strip())
        target_script = out_dir / "main.py"

        if not target_script.exists():
            messagebox.showerror(
                "Game Script Missing",
                f"Generated application entry point not found at:\n{target_script}\n\n"
                "Please run the code agent first to generate the desktop game.",
            )
            return

        self._append_log(f"[INFO] Launching desktop game via bundled interpreter: {target_script}")
        try:
            # Invokes sys.executable with --run-target so it uses the bundled runtime in standalone exe
            subprocess.Popen([sys.executable, "--run-target", str(target_script)])
        except Exception as exc:
            messagebox.showerror("Launch Failed", f"Could not launch desktop game:\n{exc}")


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    app = AgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
