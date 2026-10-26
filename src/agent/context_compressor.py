from __future__ import annotations

import copy
from typing import Any


class ContextCompressor:
    def __init__(
        self,
        max_tool_output_chars: int = 2500,
        fold_threshold_messages: int = 16,
        keep_recent_atomic_turns: int = 3,
    ) -> None:
        self.max_tool_output_chars = max_tool_output_chars
        self.fold_threshold_messages = fold_threshold_messages
        self.keep_recent_atomic_turns = keep_recent_atomic_turns

    def compress(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(messages) <= 2:
            return copy.deepcopy(messages)

        msgs = copy.deepcopy(messages)
        msgs = self._apply_level1_trim(msgs)
        msgs = self._apply_level2_deduplicate(msgs)
        if len(msgs) > self.fold_threshold_messages:
            msgs = self._apply_level3_fold(msgs)

        self._validate_message_invariants(msgs)
        return msgs

    def _apply_level1_trim(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for msg in messages:
            if msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str):
                continue
            if len(content) > self.max_tool_output_chars:
                head_len = self.max_tool_output_chars // 2 - 50
                tail_len = self.max_tool_output_chars // 2 - 50
                omitted = len(content) - (head_len + tail_len)
                trimmed = (
                    f"{content[:head_len]}\n\n"
                    f"[... {omitted} characters truncated by context compressor ...]\n\n"
                    f"{content[-tail_len:]}"
                )
                msg["content"] = trimmed
        return messages

    def _apply_level2_deduplicate(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_ir_reads = 0
        tool_call_map: dict[str, str] = {}
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id")
                    fn_name = tc.get("function", {}).get("name")
                    if tc_id and fn_name:
                        tool_call_map[tc_id] = fn_name

        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg.get("role") != "tool":
                continue
            tc_id = msg.get("tool_call_id")
            fn_name = tool_call_map.get(tc_id, "")

            if fn_name == "read_architecture_ir":
                seen_ir_reads += 1
                if seen_ir_reads > 1:
                    msg["content"] = "[TRUNCATED: superseded by subsequent architecture IR inspection]"

        return messages

    def _apply_level3_fold(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(messages) <= 2:
            return messages

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        user_msg = messages[1] if len(messages) > 1 and messages[1].get("role") == "user" else None

        start_idx = 0
        if system_msg:
            start_idx += 1
        if user_msg:
            start_idx += 1

        atomic_groups: list[list[dict[str, Any]]] = []
        i = start_idx
        while i < len(messages):
            msg = messages[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                group = [msg]
                i += 1
                while i < len(messages) and messages[i].get("role") == "tool":
                    group.append(messages[i])
                    i += 1
                atomic_groups.append(group)
            else:
                atomic_groups.append([msg])
                i += 1

        if len(atomic_groups) <= self.keep_recent_atomic_turns:
            return messages

        groups_to_fold = atomic_groups[:-self.keep_recent_atomic_turns]
        groups_to_keep = atomic_groups[-self.keep_recent_atomic_turns:]

        completed_actions: list[str] = []
        for grp in groups_to_fold:
            for m in grp:
                if m.get("role") == "assistant" and m.get("tool_calls"):
                    for tc in m["tool_calls"]:
                        fn = tc.get("function", {})
                        completed_actions.append(f"invoked {fn.get('name')}")
                elif m.get("role") == "assistant" and m.get("content"):
                    snippet = str(m.get("content"))[:80].replace("\n", " ")
                    completed_actions.append(f"reasoned: '{snippet}...'")

        fold_summary = (
            "[SYSTEM CONTEXT COMPRESSION]: Earlier agent turns folded to conserve token budget.\n"
            f"Actions executed: {'; '.join(completed_actions[-8:]) if completed_actions else 'scaffolding initialized'}.\n"
            "State invariant: All materialized files and verification results are maintained in the workspace."
        )

        folded_history: list[dict[str, Any]] = []
        if system_msg:
            folded_history.append(system_msg)
        if user_msg:
            folded_history.append(user_msg)

        folded_history.append({"role": "user", "content": fold_summary})
        folded_history.append({"role": "assistant", "content": "Acknowledged. Proceeding with active components."})

        for grp in groups_to_keep:
            folded_history.extend(grp)

        return folded_history

    @staticmethod
    def _validate_message_invariants(messages: list[dict[str, Any]]) -> None:
        for idx, msg in enumerate(messages):
            if msg.get("role") == "tool":
                if idx == 0:
                    raise ValueError("Invariant violation: tool message at index 0")
                prev = messages[idx - 1]
                if prev.get("role") not in ("assistant", "tool"):
                    raise ValueError(
                        f"Invariant violation: tool message at index {idx} preceded by {prev.get('role')}"
                    )

