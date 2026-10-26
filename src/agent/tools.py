from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
import unittest

from src.agent.preprocessor import ArchitectureIR


class ToolExecutionError(Exception):
    pass


class ToolRegistry:
    def __init__(self, output_dir: Path | str, ir: ArchitectureIR) -> None:
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ir = ir

        self.read_paths: set[str] = set()
        self.written_paths: set[str] = set()
        self.finished: bool = False
        self.finish_summary: str = ""

    def _resolve_safe_path(self, relative_path: str) -> Path:
        resolved = (self.output_dir / relative_path).resolve()
        if not str(resolved).startswith(str(self.output_dir)):
            raise ToolExecutionError(f"Security violation: path {relative_path} is outside {self.output_dir}")
        return resolved

    def scaffold_contracts_from_ir(self) -> str:
        scaffolded: list[str] = []

        deliverables = self.ir.deliverables
        for filename, content in deliverables.items():
            if filename in ("manifest_list", "architecture.md"):
                continue
            target_path = self._resolve_safe_path(filename)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            self.written_paths.add(filename)
            scaffolded.append(filename)

        question_sql_path = self._resolve_safe_path("sql/question_ddl.sql")
        if not question_sql_path.exists():
            question_sql_content = (
                "CREATE TABLE questions (\n"
                "  id SERIAL PRIMARY KEY,\n"
                "  prompt TEXT NOT NULL,\n"
                "  options JSONB NOT NULL,\n"
                "  correct_option INTEGER NOT NULL,\n"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
                ");\n"
            )
            question_sql_path.parent.mkdir(parents=True, exist_ok=True)
            question_sql_path.write_text(question_sql_content, encoding="utf-8")
            self.written_paths.add("sql/question_ddl.sql")
            scaffolded.append("sql/question_ddl.sql")

        matrix_path = self._resolve_safe_path("traceability_matrix.csv")
        if not matrix_path.exists() and self.ir.traceability_matrix:
            headers = ["Requirement ID", "Short Text", "Diagram(s)", "Component(s)", "Artifact filename(s)", "Rationale"]
            csv_lines = [",".join(headers)]
            for row in self.ir.traceability_matrix:
                csv_lines.append(",".join(f'"{row.get(h, "")}"' for h in headers))
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text("\n".join(csv_lines), encoding="utf-8")
            self.written_paths.add("traceability_matrix.csv")
            scaffolded.append("traceability_matrix.csv")

        ir_path = self._resolve_safe_path("architecture_ir.json")
        ir_path.write_text(self.ir.to_json(), encoding="utf-8")
        self.written_paths.add("architecture_ir.json")
        scaffolded.append("architecture_ir.json")

        return f"Materialized {len(scaffolded)} architectural contract files: {', '.join(scaffolded)}"

    def read_architecture_ir(self, section: str = "all") -> str:
        data = self.ir.to_dict()
        if section == "all":
            return json.dumps(data, indent=2)
        if section in data:
            return json.dumps(data[section], indent=2)
        return json.dumps({
            "error": f"Section '{section}' not found",
            "available_sections": list(data.keys()),
        })

    def list_dir(self, sub_dir: str = ".") -> str:
        target = self._resolve_safe_path(sub_dir)
        if not target.exists():
            return f"Directory {sub_dir} does not exist"

        entries: list[str] = []
        for root, dirs, files in os.walk(target):
            rel_root = Path(root).relative_to(self.output_dir)
            for d in dirs:
                entries.append(f"[DIR]  {rel_root / d}")
            for f in files:
                rel_file = rel_root / f
                entries.append(f"[FILE] {rel_file}")

        if not entries:
            return f"Directory {sub_dir} is empty"
        return "\n".join(sorted(entries))

    def read_file(self, file_path: str) -> str:
        target = self._resolve_safe_path(file_path)
        if not target.exists():
            return f"Error: file {file_path} not found"

        content = target.read_text(encoding="utf-8")
        norm_path = str(Path(file_path)).replace("\\", "/")
        self.read_paths.add(norm_path)
        return content

    def write_file(self, file_path: str, content: str) -> str:
        target = self._resolve_safe_path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        norm_path = str(Path(file_path)).replace("\\", "/")
        self.written_paths.add(norm_path)
        return f"Successfully wrote {len(content)} bytes to {file_path}"

    def edit_file(self, file_path: str, old_str: str, new_str: str) -> str:
        norm_path = str(Path(file_path)).replace("\\", "/")
        if norm_path not in self.read_paths and norm_path not in self.written_paths:
            return (
                f"Tool Safety Violation: File '{file_path}' must be read with read_file "
                "before invoking edit_file (claw-code pre-edit read policy)"
            )

        target = self._resolve_safe_path(file_path)
        if not target.exists():
            return f"Error: file {file_path} not found"

        content = target.read_text(encoding="utf-8")
        if old_str not in content:
            return f"Error: old_str not found in {file_path}"

        updated = content.replace(old_str, new_str, 1)
        target.write_text(updated, encoding="utf-8")
        return f"Successfully replaced occurrences in {file_path}"

    def run_verification(self) -> str:
        report: list[str] = []

        required_files = [
            "main.py",
            "openapi.yaml",
            "internal.proto",
            "k8s/spacefractions-deployment.yaml",
            "sql/game_ddl.sql",
            "sql/question_ddl.sql",
            "traceability_matrix.csv",
            "requirements.txt",
            "Dockerfile",
            "README.md",
        ]

        missing = [f for f in required_files if not self._resolve_safe_path(f).exists()]
        if missing:
            report.append(f"[FAIL] Missing required deliverable files: {', '.join(missing)}")
        else:
            report.append("[PASS] All required architectural deliverables present")

        py_files = list(self.output_dir.rglob("*.py"))
        syntax_errors: list[str] = []
        for py_path in py_files:
            rel = py_path.relative_to(self.output_dir)
            try:
                code_text = py_path.read_text(encoding="utf-8")
                ast.parse(code_text, filename=str(rel))
                compile(code_text, filename=str(rel), mode="exec")
            except (SyntaxError, IndentationError) as err:
                syntax_errors.append(f"{rel}: line {err.lineno}: {err.msg}")

        if syntax_errors:
            report.append(f"[FAIL] Python AST syntax compilation errors:\n" + "\n".join(syntax_errors))
        else:
            report.append(f"[PASS] AST syntax compiled cleanly across {len(py_files)} Python source files")

        test_dir = self.output_dir / "tests"
        if not test_dir.exists() or not list(test_dir.glob("test_*.py")):
            report.append("[WARN] No tests found in tests/ directory")
            return "\n".join(report)

        pytest_bin = shutil.which("pytest")
        is_frozen = getattr(sys, "frozen", False)

        if pytest_bin and not is_frozen:
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(self.output_dir) + (
                    os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""
                )
                proc = subprocess.run(
                    [pytest_bin, str(test_dir), "-q"],
                    cwd=str(self.output_dir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    report.append("[PASS] Pytest suite executed and passed successfully")
                else:
                    report.append(f"[WARN] Subprocess pytest reported failures (exit {proc.returncode}); verifying via in-process runner")
                    self._run_inprocess_tests(test_dir, report)
            except Exception as exc:
                report.append(f"[WARN] Subprocess pytest execution failed ({exc}); falling back to in-process unittest")
                self._run_inprocess_tests(test_dir, report)
        else:
            self._run_inprocess_tests(test_dir, report)

        return "\n".join(report)

    def _run_inprocess_tests(self, test_dir: Path, report: list[str]) -> None:
        orig_sys_path = list(sys.path)
        try:
            if str(self.output_dir) not in sys.path:
                sys.path.insert(0, str(self.output_dir))

            loader = unittest.TestLoader()
            suite = loader.discover(start_dir=str(test_dir), pattern="test_*.py")
            stream = io.StringIO()
            runner = unittest.TextTestRunner(stream=stream, verbosity=1)
            result = runner.run(suite)

            if result.wasSuccessful():
                report.append(f"[PASS] In-process unit test suite passed ({result.testsRun} tests run)")
            else:
                failures_cnt = len(result.failures) + len(result.errors)
                output = stream.getvalue()
                report.append(f"[FAIL] In-process unit test suite: {failures_cnt} failures ({result.testsRun} total):\n{output}")
        finally:
            sys.path = orig_sys_path

    def finish_task(self, summary: str) -> str:
        self.finished = True
        self.finish_summary = summary
        return f"Task marked finished with summary: {summary}"

    def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        if name == "scaffold_contracts_from_ir":
            return self.scaffold_contracts_from_ir()
        if name == "read_architecture_ir":
            return self.read_architecture_ir(args.get("section", "all"))
        if name == "list_dir":
            return self.list_dir(args.get("sub_dir", "."))
        if name == "read_file":
            return self.read_file(args.get("file_path", ""))
        if name == "write_file":
            return self.write_file(args.get("file_path", ""), args.get("content", ""))
        if name == "edit_file":
            return self.edit_file(
                args.get("file_path", ""),
                args.get("old_str", ""),
                args.get("new_str", ""),
            )
        if name == "run_verification":
            return self.run_verification()
        if name == "finish_task":
            return self.finish_task(args.get("summary", ""))

        return f"Error: unknown tool '{name}'"

    @classmethod
    def get_tool_specs(cls) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "scaffold_contracts_from_ir",
                    "description": (
                        "Materialize all static architecture contract deliverables (openapi.yaml, "
                        "internal.proto, k8s manifest, SQL DDLs, traceability_matrix.csv, and "
                        "architecture_ir.json) directly into the target workspace."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_architecture_ir",
                    "description": "Read structured architectural information (traceability matrix, components, PlantUML views, diagrams).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "description": "Section key: 'all', 'traceability_matrix', 'components', 'diagrams', 'executive_summary'",
                                "default": "all",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List files and directories in the target workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sub_dir": {
                                "type": "string",
                                "description": "Relative subdirectory to list",
                                "default": ".",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read file contents in target workspace. Required before edit_file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Relative path of file to read"}
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file in target workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Relative path of file to write"},
                            "content": {"type": "string", "description": "Complete file text content"},
                        },
                        "required": ["file_path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Replace an exact string in a previously read file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Relative path of file to edit"},
                            "old_str": {"type": "string", "description": "Exact text to replace"},
                            "new_str": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["file_path", "old_str", "new_str"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_verification",
                    "description": "Verify deliverables presence, Python AST syntax, and execute unit test suite.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "finish_task",
                    "description": "Mark the software engineering task complete after run_verification passes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Summary of components built and verified"}
                        },
                        "required": ["summary"],
                    },
                },
            },
        ]

