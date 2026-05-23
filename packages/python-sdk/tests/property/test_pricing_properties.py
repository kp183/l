"""Property-based tests for token cost calculations.

Feature: agentlens-mvp
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from agentlens.pricing import PRICING, calculate_cost


# ---------------------------------------------------------------------------
# Property 18: Cost calculation correctness
# ---------------------------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(
    model=st.sampled_from(list(PRICING.keys())),
    input_tokens=st.integers(0, 1_000_000),
    output_tokens=st.integers(0, 1_000_000),
)
def test_cost_calculation_correctness(model: str, input_tokens: int, output_tokens: int) -> None:
    """Feature: agentlens-mvp, Property 18: Cost calculation correctness"""
    rates = PRICING[model]
    expected = input_tokens * rates["input"] + output_tokens * rates["output"]
    actual = calculate_cost(model, input_tokens, output_tokens)
    assert abs(actual - expected) < 1e-9


# ---------------------------------------------------------------------------
# Property 19: Unknown model cost is zero
# ---------------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(
    model=st.text(min_size=1, max_size=50),
    input_tokens=st.integers(0, 1_000_000),
    output_tokens=st.integers(0, 1_000_000),
)
def test_unknown_model_cost_is_zero(model: str, input_tokens: int, output_tokens: int) -> None:
    """Feature: agentlens-mvp, Property 19: Unknown model cost is zero"""
    assume(model not in PRICING)
    actual = calculate_cost(model, input_tokens, output_tokens)
    assert actual == 0.0
