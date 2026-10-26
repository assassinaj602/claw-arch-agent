from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict[str, Any]]
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    raw_response: dict[str, Any]


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-v4-pro",
        timeout: float = 120.0,
        max_retries: int = 3,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.log_callback = log_callback or (lambda msg: None)

        self._resolved_model: str = self.model
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    def _log(self, message: str) -> None:
        logger.info(message)
        self.log_callback(message)

    def _resolve_fallback_model(self) -> str:
        if "openrouter.ai" in self.base_url:
            return "deepseek/deepseek-chat"
        if "tokenharbor.ai" in self.base_url:
            return "deepseek-v4.1-flash:free"
        return "deepseek-chat"

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for attempt in range(self.max_retries):
            try:
                resp = self._client.post("/chat/completions", json=payload)

                if resp.status_code in (400, 401, 403, 404, 422):
                    err_body = resp.text
                    err_msg = ""
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", "")
                    except Exception:
                        pass

                    if "model_not_found" in err_body or "does not exist" in err_body or "not found" in err_body.lower():
                        if self._resolved_model != self._resolve_fallback_model():
                            fallback = self._resolve_fallback_model()
                            self._log(
                                f"[INFO] Model {self._resolved_model} not exposed on endpoint; routing via {fallback}"
                            )
                            self._resolved_model = fallback
                            payload["model"] = fallback
                            continue

                    detailed = err_msg or err_body
                    raise RuntimeError(f"API Error {resp.status_code}: {detailed}")

                if resp.status_code in (429, 500, 502, 503, 504):
                    wait_sec = 2.0 * (attempt + 1)
                    self._log(f"[WARN] HTTP {resp.status_code}. Retrying in {wait_sec}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait_sec)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data)

            except httpx.RequestError as exc:
                if attempt == self.max_retries - 1:
                    raise
                wait_sec = 2.0 * (attempt + 1)
                self._log(f"[WARN] Network error {exc}. Retrying in {wait_sec}s")
                time.sleep(wait_sec)

        raise RuntimeError("Exceeded maximum retries for DeepSeek API completion")

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices", [])
        if not choices:
            return LLMResponse(
                content="",
                tool_calls=[],
                prompt_tokens=0,
                completion_tokens=0,
                cached_tokens=0,
                raw_response=data,
            )

        message = choices[0].get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls: list[dict[str, Any]] = []
        for tc in raw_tool_calls:
            tc_id = tc.get("id", "")
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {"raw_arguments": raw_args}
            else:
                args = raw_args

            tool_calls.append({
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args,
                },
            })

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = prompt_details.get("cached_tokens", 0)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            raw_response=data,
        )

    def close(self) -> None:
        self._client.close()

