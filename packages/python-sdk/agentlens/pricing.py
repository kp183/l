"""Token cost lookup and calculation for LLM spans.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("agentlens")

PRICING = {
    "gpt-4o": {"input": 5.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4-turbo": {"input": 10.0 / 1_000_000, "output": 30.0 / 1_000_000},
    "gpt-4": {"input": 30.0 / 1_000_000, "output": 60.0 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "gpt-3.5-turbo-0125": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "claude-3-5-sonnet-20241022": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "claude-3-5-haiku-20241022": {"input": 0.80 / 1_000_000, "output": 4.0 / 1_000_000},
    "claude-3-opus-20240229": {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
    "claude-3-sonnet-20240229": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "claude-3-haiku-20240307": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost in USD for a given model and token count."""
    rates = PRICING.get(model)
    if not rates:
        logger.debug(f"Unknown model name for cost calculation: {model}")
        return 0.0

    in_cost = input_tokens * rates["input"]
    out_cost = output_tokens * rates["output"]
    return in_cost + out_cost
