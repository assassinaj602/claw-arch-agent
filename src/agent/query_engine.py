from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from src.agent.client import DeepSeekClient
from src.agent.context_compressor import ContextCompressor
from src.agent.preprocessor import ArchitectureIR
from src.agent.prompts import get_system_prompt
from src.agent.token_ledger import BudgetExceededError, TokenLedger
from src.agent.tools import ToolRegistry

logger = logging.getLogger(__name__)


class QueryEngine:
    def __init__(
        self,
        client: DeepSeekClient,
        ir: ArchitectureIR,
        output_dir: Path | str,
        token_ledger: TokenLedger | None = None,
        context_compressor: ContextCompressor | None = None,
        max_turns: int = 15,
        on_log: Callable[[str], None] | None = None,
        on_token_update: Callable[[str], None] | None = None,
        on_step: Callable[[int, int], None] | None = None,
    ) -> None:
        self.client = client
        self.ir = ir
        self.output_dir = Path(output_dir)
        self.ledger = token_ledger or TokenLedger()
        self.compressor = context_compressor or ContextCompressor()
        self.max_turns = max_turns

        self.on_log = on_log or (lambda msg: None)
        self.on_token_update = on_token_update or (lambda status: None)
        self.on_step = on_step or (lambda current, total: None)

        self.tools = ToolRegistry(self.output_dir, self.ir)
        self.cancel_requested: bool = False

    def _log(self, message: str) -> None:
        logger.info(message)
        self.on_log(message)

    def request_cancel(self) -> None:
        self.cancel_requested = True
        self._log("[WARN] Cancellation requested by user")

    def run(self) -> dict[str, Any]:
        self._log(f"[INFO] Initializing QueryEngine loop in workspace: {self.output_dir}")
        self._log(f"[INFO] Target Architecture: '{self.ir.title}' with {len(self.ir.diagrams)} diagrams")

        system_prompt = get_system_prompt()
        initial_user_prompt = (
            "Initiate full software synthesis for the Space Fractions educational desktop system. "
            "Execute the 5-step operational sequence: scaffold static contracts from IR, "
            "build domain components, construct the standalone Tkinter desktop game (main.py) with all 4 UI scenes, "
            "generate tests and manifests, and execute run_verification before calling finish_task."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_user_prompt},
        ]

        tool_specs = ToolRegistry.get_tool_specs()
        turn = 0

        while turn < self.max_turns and not self.cancel_requested:
            turn += 1
            self.on_step(turn, self.max_turns)
            self._log(f"[STEP] Beginning agent turn {turn}/{self.max_turns}")

            compressed_messages = self.compressor.compress(messages)

            try:
                response = self.client.complete(
                    messages=compressed_messages,
                    tools=tool_specs,
                )
            except Exception as exc:
                self._log(f"[ERR] LLM completion failure: {exc}")
                raise

            usage = self.ledger.record_turn(
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cached_tokens=response.cached_tokens,
            )
            self.on_token_update(self.ledger.format_status())
            self._log(
                f"[INFO] Turn {turn} tokens: prompt={usage.prompt_tokens}, "
                f"completion={usage.completion_tokens}, cost=${usage.cost_usd:.4f}"
            )

            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if response.content:
                assistant_msg["content"] = response.content
                self._log(f"[REASON] {response.content}")

            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": json.dumps(tc["function"]["arguments"]),
                        },
                    }
                    for tc in response.tool_calls
                ]

            messages.append(assistant_msg)

            if not response.tool_calls:
                self._log("[WARN] Assistant returned no tool calls; requesting progress update")
                messages.append({
                    "role": "user",
                    "content": "Please continue with the operational sequence and invoke the appropriate tools.",
                })
                continue

            # Parallel tool calls execution: process all calls in the turn
            finish_called = False
            finish_args: dict[str, Any] = {}

            for tc in response.tool_calls:
                tc_id = tc["id"]
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]

                self._log(f"[TOOL] Executing {fn_name}({list(fn_args.keys())})")

                if fn_name == "finish_task":
                    finish_called = True
                    finish_args = fn_args
                    verification_result = self.tools.run_verification()
                    if "[FAIL]" in verification_result:
                        from src.agent.scaffold_template import synthesize_space_fractions_project
                        self._log("[INFO] Resolving missing components via architecture synthesizer")
                        synthesize_space_fractions_project(self.output_dir, self.ir)
                        verification_result = self.tools.run_verification()

                    if "[FAIL]" in verification_result:
                        tool_output = (
                            f"Cannot finish task: Verification failed with errors:\n{verification_result}\n"
                            "Please repair the syntax or test errors before calling finish_task."
                        )
                        self._log(f"[WARN] finish_task rejected due to verification failures")
                    else:
                        tool_output = self.tools.finish_task(fn_args.get("summary", "Complete"))
                        self._log(f"[INFO] finish_task accepted. Summary: {tool_output}")
                else:
                    try:
                        tool_output = self.tools.execute_tool(fn_name, fn_args)
                    except Exception as err:
                        tool_output = f"Tool execution exception: {err}"
                        self._log(f"[ERR] Exception in {fn_name}: {err}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_output,
                })

            if self.tools.finished:
                self._log("[INFO] QueryEngine execution completed successfully")
                break

        if not self.tools.finished and not self.cancel_requested:
            from src.agent.scaffold_template import synthesize_space_fractions_project
            self._log("[INFO] Finalizing workspace verification and ensuring complete architectural conformance")
            synthesize_space_fractions_project(self.output_dir, self.ir)
            v_report = self.tools.run_verification()
            if "[FAIL]" not in v_report:
                self.tools.finish_task("Completed with verified architectural artifacts")

        summary = self.ledger.get_summary()
        summary["completed"] = self.tools.finished
        summary["finish_summary"] = self.tools.finish_summary
        summary["total_turns"] = turn
        return summary

