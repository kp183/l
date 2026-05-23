"""Property-based tests for serialization invariants.

Feature: agentlens-mvp
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.ingest import SpanPayload


def _valid_span(**overrides) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "trace_id": str(uuid.uuid4()),
        "name": "test-span",
        "span_type": "custom",
        "status": "success",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Property 25: SpanPayload serialization round-trip
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    name=st.text(min_size=1, max_size=100),
    span_type=st.sampled_from(["llm", "tool", "agent", "custom"]),
    status=st.sampled_from(["running", "success", "error"]),
)
def test_span_payload_round_trip(name: str, span_type: str, status: str) -> None:
    """Feature: agentlens-mvp, Property 25: SpanPayload serialization round-trip

    Serialize SpanPayload to JSON and deserialize back — all fields must be equal.
    """
    original = SpanPayload(**_valid_span(name=name, span_type=span_type, status=status))
    json_str = original.model_dump_json()
    restored = SpanPayload.model_validate_json(json_str)

    assert original.id == restored.id
    assert original.trace_id == restored.trace_id
    assert original.name == restored.name
    assert original.span_type == restored.span_type
    assert original.status == restored.status
    assert original.started_at == restored.started_at
