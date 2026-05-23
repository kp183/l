"""Property-based tests for ingest pipeline invariants.

Feature: agentlens-mvp
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.ingest import IngestRequest, SpanPayload

_VALID_SPAN_TYPES = {"llm", "tool", "agent", "custom"}
_VALID_STATUSES = {"running", "success", "error"}

# ---------------------------------------------------------------------------
# Minimal valid span factory
# ---------------------------------------------------------------------------

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
# Property 17: Span type validation rejects unknown types
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(span_type=st.text(min_size=1))
def test_span_type_validation_rejects_unknown(span_type: str) -> None:
    """Feature: agentlens-mvp, Property 17: Span type validation rejects unknown types"""
    assume(span_type not in _VALID_SPAN_TYPES)

    with pytest.raises(ValidationError) as exc_info:
        SpanPayload(**_valid_span(span_type=span_type))

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("span_type",) for e in errors), (
        f"Expected span_type validation error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 26: Required field validation rejects incomplete spans
# ---------------------------------------------------------------------------

@settings(max_examples=50)
@given(
    missing_field=st.sampled_from(
        ["id", "trace_id", "name", "span_type", "status", "started_at"]
    )
)
def test_required_field_validation(missing_field: str) -> None:
    """Feature: agentlens-mvp, Property 26: Required field validation rejects incomplete spans"""
    payload = _valid_span()
    del payload[missing_field]

    with pytest.raises(ValidationError) as exc_info:
        SpanPayload(**payload)

    errors = exc_info.value.errors()
    field_names = {e["loc"][0] for e in errors}
    assert missing_field in field_names, (
        f"Expected '{missing_field}' in validation errors, got: {field_names}"
    )


# ---------------------------------------------------------------------------
# Property 15: Ingest batch accepted/rejected counts are correct
# ---------------------------------------------------------------------------

@settings(max_examples=30)
@given(
    n_valid=st.integers(0, 50),
    n_invalid=st.integers(0, 50),
)
def test_ingest_batch_counts(n_valid: int, n_invalid: int) -> None:
    """Feature: agentlens-mvp, Property 15: Ingest batch accepted/rejected counts are correct

    Tests the schema-level validation: a batch with n_valid good spans and
    n_invalid bad spans (wrong span_type) should have exactly n_valid parseable
    spans and n_invalid that fail validation.
    """
    assume(n_valid + n_invalid <= 500)
    assume(n_valid + n_invalid > 0)

    valid_spans = [_valid_span() for _ in range(n_valid)]
    invalid_spans = [_valid_span(span_type="INVALID_TYPE") for _ in range(n_invalid)]

    accepted = 0
    rejected = 0

    for raw in valid_spans + invalid_spans:
        try:
            SpanPayload(**raw)
            accepted += 1
        except ValidationError:
            rejected += 1

    assert accepted == n_valid, f"Expected {n_valid} accepted, got {accepted}"
    assert rejected == n_invalid, f"Expected {n_invalid} rejected, got {rejected}"


# ---------------------------------------------------------------------------
# Property 16: Ingest idempotency on span_id (schema level)
# ---------------------------------------------------------------------------

def test_ingest_idempotency_schema() -> None:
    """Feature: agentlens-mvp, Property 16: Ingest idempotency on span_id

    The same span submitted twice in a batch should parse identically.
    DB-level idempotency (ON CONFLICT DO NOTHING) is tested in integration tests.
    """
    span_data = _valid_span()
    span1 = SpanPayload(**span_data)
    span2 = SpanPayload(**span_data)
    assert span1.id == span2.id
    assert span1.trace_id == span2.trace_id
