"""Anthropic client instrumentation monkey-patch.
"""

from __future__ import annotations

import time
import traceback
import uuid
from datetime import datetime, timezone

from agentlens.context import get_span_id, get_trace_id
from agentlens.pricing import calculate_cost


def instrument_anthropic():
    """Monkey-patch Anthropic messages client to automatically record spans."""
    try:
        from anthropic.resources.messages import Messages
    except ImportError:
        return

    if getattr(Messages, "_agentlens_instrumented", False):
        return
    Messages._agentlens_instrumented = True

    original_create = Messages.create

    def patched_create(self, *args, **kwargs):
        import agentlens
        if agentlens._global_client is None or not agentlens._global_client.enabled:
            return original_create(self, *args, **kwargs)

        trace_id = get_trace_id()
        if not trace_id:
            return original_create(self, *args, **kwargs)

        parent_span_id = get_span_id()
        span_id = str(uuid.uuid4())

        model = kwargs.get("model", "unknown")
        provider = "anthropic"
        started_at = datetime.now(timezone.utc)
        start_time = time.time()
        messages = kwargs.get("messages", [])
        is_stream = kwargs.get("stream", False)

        if is_stream:
            try:
                response = original_create(self, *args, **kwargs)
            except Exception as e:
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)
                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": f"anthropic.messages.create ({model})",
                    "span_type": "llm",
                    "status": "error",
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "model": model,
                    "provider": provider,
                    "input": {"messages": messages},
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_stack": traceback.format_exc(),
                }
                agentlens._global_client._safe_enqueue(span_payload)
                raise e

            def stream_wrapper(stream_resp):
                accumulated_content = []
                input_tokens = 0
                output_tokens = 0
                try:
                    for event in stream_resp:
                        yield event
                        event_type = getattr(event, "type", None)
                        if event_type == "content_block_delta":
                            delta = getattr(event, "delta", None)
                            if delta and getattr(delta, "type", None) == "text_delta":
                                text = getattr(delta, "text", "")
                                accumulated_content.append(text)
                        elif event_type == "message_start":
                            message = getattr(event, "message", None)
                            if message and hasattr(message, "usage") and message.usage:
                                input_tokens = getattr(message.usage, "input_tokens", 0) or 0
                        elif event_type == "message_delta":
                            usage = getattr(event, "usage", None)
                            if usage:
                                output_tokens = getattr(usage, "output_tokens", 0) or 0
                finally:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)
                    cost_usd = calculate_cost(model, input_tokens, output_tokens)
                    full_output = "".join(accumulated_content)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"anthropic.messages.create ({model})",
                        "span_type": "llm",
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                        "input": {"messages": messages},
                        "output": {"content": [{"type": "text", "text": full_output}]},
                    }
                    agentlens._global_client._safe_enqueue(span_payload)

            return stream_wrapper(response)
        else:
            try:
                response = original_create(self, *args, **kwargs)
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)

                input_tokens = 0
                output_tokens = 0
                output_content = []

                if hasattr(response, "usage") and response.usage:
                    input_tokens = getattr(response.usage, "input_tokens", 0) or 0
                    output_tokens = getattr(response.usage, "output_tokens", 0) or 0

                if hasattr(response, "content") and response.content:
                    for block in response.content:
                        block_type = getattr(block, "type", "text")
                        if block_type == "text":
                            output_content.append({
                                "type": "text",
                                "text": getattr(block, "text", "")
                            })

                cost_usd = calculate_cost(model, input_tokens, output_tokens)

                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": f"anthropic.messages.create ({model})",
                    "span_type": "llm",
                    "status": "success",
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "model": model,
                    "provider": provider,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd,
                    "input": {"messages": messages},
                    "output": {"content": output_content},
                }
                agentlens._global_client._safe_enqueue(span_payload)
                return response
            except Exception as e:
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)
                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": f"anthropic.messages.create ({model})",
                    "span_type": "llm",
                    "status": "error",
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "model": model,
                    "provider": provider,
                    "input": {"messages": messages},
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "error_stack": traceback.format_exc(),
                }
                agentlens._global_client._safe_enqueue(span_payload)
                raise e

    Messages.create = patched_create

    try:
        from anthropic.resources.messages import AsyncMessages

        original_async_create = AsyncMessages.create

        async def patched_async_create(self, *args, **kwargs):
            import agentlens
            if agentlens._global_client is None or not agentlens._global_client.enabled:
                return await original_async_create(self, *args, **kwargs)

            trace_id = get_trace_id()
            if not trace_id:
                return await original_async_create(self, *args, **kwargs)

            parent_span_id = get_span_id()
            span_id = str(uuid.uuid4())

            model = kwargs.get("model", "unknown")
            provider = "anthropic"
            started_at = datetime.now(timezone.utc)
            start_time = time.time()
            messages = kwargs.get("messages", [])
            is_stream = kwargs.get("stream", False)

            if is_stream:
                try:
                    response = await original_async_create(self, *args, **kwargs)
                except Exception as e:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)
                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"anthropic.messages.create ({model})",
                        "span_type": "llm",
                        "status": "error",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input": {"messages": messages},
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "error_stack": traceback.format_exc(),
                    }
                    agentlens._global_client._safe_enqueue(span_payload)
                    raise e

                async def async_stream_wrapper(stream_resp):
                    accumulated_content = []
                    input_tokens = 0
                    output_tokens = 0
                    try:
                        async for event in stream_resp:
                            yield event
                            event_type = getattr(event, "type", None)
                            if event_type == "content_block_delta":
                                delta = getattr(event, "delta", None)
                                if delta and getattr(delta, "type", None) == "text_delta":
                                    text = getattr(delta, "text", "")
                                    accumulated_content.append(text)
                            elif event_type == "message_start":
                                message = getattr(event, "message", None)
                                if message and hasattr(message, "usage") and message.usage:
                                    input_tokens = getattr(message.usage, "input_tokens", 0) or 0
                            elif event_type == "message_delta":
                                usage = getattr(event, "usage", None)
                                if usage:
                                    output_tokens = getattr(usage, "output_tokens", 0) or 0
                    finally:
                        ended_at = datetime.now(timezone.utc)
                        duration_ms = int((time.time() - start_time) * 1000)
                        cost_usd = calculate_cost(model, input_tokens, output_tokens)
                        full_output = "".join(accumulated_content)

                        span_payload = {
                            "id": span_id,
                            "trace_id": trace_id,
                            "parent_span_id": parent_span_id,
                            "name": f"anthropic.messages.create ({model})",
                            "span_type": "llm",
                            "status": "success",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "duration_ms": duration_ms,
                            "model": model,
                            "provider": provider,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "cost_usd": cost_usd,
                            "input": {"messages": messages},
                            "output": {"content": [{"type": "text", "text": full_output}]},
                        }
                        agentlens._global_client._safe_enqueue(span_payload)

                return async_stream_wrapper(response)
            else:
                try:
                    response = await original_async_create(self, *args, **kwargs)
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)

                    input_tokens = 0
                    output_tokens = 0
                    output_content = []

                    if hasattr(response, "usage") and response.usage:
                        input_tokens = getattr(response.usage, "input_tokens", 0) or 0
                        output_tokens = getattr(response.usage, "output_tokens", 0) or 0

                    if hasattr(response, "content") and response.content:
                        for block in response.content:
                            block_type = getattr(block, "type", "text")
                            if block_type == "text":
                                output_content.append({
                                    "type": "text",
                                    "text": getattr(block, "text", "")
                                })

                    cost_usd = calculate_cost(model, input_tokens, output_tokens)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"anthropic.messages.create ({model})",
                        "span_type": "llm",
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cost_usd": cost_usd,
                        "input": {"messages": messages},
                        "output": {"content": output_content},
                    }
                    agentlens._global_client._safe_enqueue(span_payload)
                    return response
                except Exception as e:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)
                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"anthropic.messages.create ({model})",
                        "span_type": "llm",
                        "status": "error",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input": {"messages": messages},
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "error_stack": traceback.format_exc(),
                    }
                    agentlens._global_client._safe_enqueue(span_payload)
                    raise e

        AsyncMessages.create = patched_async_create
    except Exception:
        pass
