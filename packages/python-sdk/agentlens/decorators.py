"""Decorators and context managers for AgentLens instrumentation.
"""

from __future__ import annotations

import traceback
import uuid
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, List, Optional

from agentlens.context import (
    _current_span_id,
    _current_trace_id,
    get_span_id,
    get_trace_id,
    set_span_id,
    set_trace_id,
)


def trace(name: Optional[str] = None, tags: Optional[List[str]] = None) -> Callable[..., Any]:
    """Decorator to mark a function as a trace root."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import agentlens
            if agentlens._global_client is None or not agentlens._global_client.enabled:
                return func(*args, **kwargs)

            trace_id = str(uuid.uuid4())
            span_id = str(uuid.uuid4())

            trace_token = set_trace_id(trace_id)
            span_token = set_span_id(span_id)

            span_name = name or func.__name__
            started_at = datetime.now(timezone.utc)
            start_time = time.time()

            status = "success"
            error_type = None
            error_message = None
            error_stack = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_type = type(e).__name__
                error_message = str(e)
                error_stack = traceback.format_exc()
                raise e
            finally:
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)

                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": None,
                    "name": span_name,
                    "span_type": "custom",
                    "status": status,
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "tags": tags or [],
                }
                if error_type:
                    span_payload.update({
                        "error_type": error_type,
                        "error_message": error_message,
                        "error_stack": error_stack,
                    })

                agentlens._global_client._safe_enqueue(span_payload)

                _current_trace_id.reset(trace_token)
                _current_span_id.reset(span_token)

        return wrapper
    return decorator


@contextmanager
def span(name: str, span_type: str = "custom", tags: Optional[List[str]] = None):
    """Context manager to mark a block of code as a span."""
    import agentlens
    if agentlens._global_client is None or not agentlens._global_client.enabled:
        yield
        return

    trace_id = get_trace_id()
    if not trace_id:
        yield
        return

    parent_span_id = get_span_id()
    span_id = str(uuid.uuid4())

    span_token = set_span_id(span_id)

    started_at = datetime.now(timezone.utc)
    start_time = time.time()

    status = "success"
    error_type = None
    error_message = None
    error_stack = None

    try:
        yield
    except Exception as e:
        status = "error"
        error_type = type(e).__name__
        error_message = str(e)
        error_stack = traceback.format_exc()
        raise e
    finally:
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((time.time() - start_time) * 1000)

        span_payload = {
            "id": span_id,
            "trace_id": trace_id,
            "parent_span_id": parent_span_id,
            "name": name,
            "span_type": span_type,
            "status": status,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "tags": tags or [],
        }
        if error_type:
            span_payload.update({
                "error_type": error_type,
                "error_message": error_message,
                "error_stack": error_stack,
            })

        agentlens._global_client._safe_enqueue(span_payload)

        _current_span_id.reset(span_token)
