from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class BudgetExceededError(Exception):
    pass


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class TokenLedger:
    input_rate_per_m: float = 0.27
    cached_input_rate_per_m: float = 0.07
    output_rate_per_m: float = 1.10
    budget_limit_usd: float = 1.00

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_tokens: int = 0
    total_cost_usd: float = 0.0
    turn_history: list[TokenUsage] = field(default_factory=list)

    def calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        uncached_prompt = max(0, prompt_tokens - cached_tokens)
        cost_uncached = (uncached_prompt / 1_000_000.0) * self.input_rate_per_m
        cost_cached = (cached_tokens / 1_000_000.0) * self.cached_input_rate_per_m
        cost_output = (completion_tokens / 1_000_000.0) * self.output_rate_per_m
        return cost_uncached + cost_cached + cost_output

    def record_turn(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
    ) -> TokenUsage:
        turn_cost = self.calculate_cost(prompt_tokens, completion_tokens, cached_tokens)
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            cost_usd=turn_cost,
        )

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cached_tokens += cached_tokens
        self.total_cost_usd += turn_cost
        self.turn_history.append(usage)

        if self.total_cost_usd > self.budget_limit_usd:
            raise BudgetExceededError(
                f"Budget limit of ${self.budget_limit_usd:.2f} exceeded: total spend is ${self.total_cost_usd:.4f}"
            )

        return usage

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "budget_limit_usd": self.budget_limit_usd,
            "turns_recorded": len(self.turn_history),
        }

    def format_status(self) -> str:
        total_tokens = self.total_prompt_tokens + self.total_completion_tokens
        return (
            f"Tokens: {total_tokens:,} "
            f"(in: {self.total_prompt_tokens:,}, out: {self.total_completion_tokens:,}, cache: {self.total_cached_tokens:,}) "
            f"| Cost: ${self.total_cost_usd:.4f} USD / ${self.budget_limit_usd:.2f}"
        )

