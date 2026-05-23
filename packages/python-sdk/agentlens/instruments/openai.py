"""OpenAI client instrumentation monkey-patch.
"""

from __future__ import annotations

import time
import traceback
import uuid
from datetime import datetime, timezone

from agentlens.context import get_span_id, get_trace_id
from agentlens.pricing import calculate_cost


def instrument_openai():
    """Monkey-patch OpenAI chat completions to automatically record spans."""
    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        return

    if getattr(Completions, "_agentlens_instrumented", False):
        return
    Completions._agentlens_instrumented = True

    original_create = Completions.create

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
        provider = "openai"
        started_at = datetime.now(timezone.utc)
        start_time = time.time()
        messages = kwargs.get("messages", [])
        is_stream = kwargs.get("stream", False)

        if is_stream:
            stream_options = kwargs.get("stream_options", {}) or {}
            stream_options["include_usage"] = True
            kwargs["stream_options"] = stream_options

            try:
                response = original_create(self, *args, **kwargs)
            except Exception as e:
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)
                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": f"openai.chat.completions.create ({model})",
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
                prompt_tokens = 0
                completion_tokens = 0
                try:
                    for chunk in stream_resp:
                        yield chunk
                        if hasattr(chunk, "choices") and chunk.choices:
                            choice = chunk.choices[0]
                            if hasattr(choice, "delta") and choice.delta:
                                if hasattr(choice.delta, "content") and choice.delta.content:
                                    accumulated_content.append(choice.delta.content)
                        if hasattr(chunk, "usage") and chunk.usage:
                            prompt_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                            completion_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0
                finally:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)
                    cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
                    full_output = "".join(accumulated_content)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"openai.chat.completions.create ({model})",
                        "span_type": "llm",
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "cost_usd": cost_usd,
                        "input": {"messages": messages},
                        "output": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": full_output,
                                    }
                                }
                            ]
                        },
                    }
                    agentlens._global_client._safe_enqueue(span_payload)

            return stream_wrapper(response)
        else:
            try:
                response = original_create(self, *args, **kwargs)
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((time.time() - start_time) * 1000)

                prompt_tokens = 0
                completion_tokens = 0
                output_message = {}
                if hasattr(response, "usage") and response.usage:
                    prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                if hasattr(response, "choices") and response.choices:
                    choice = response.choices[0]
                    if hasattr(choice, "message") and choice.message:
                        output_message = {
                            "role": getattr(choice.message, "role", "assistant"),
                            "content": getattr(choice.message, "content", ""),
                        }

                cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)

                span_payload = {
                    "id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "name": f"openai.chat.completions.create ({model})",
                    "span_type": "llm",
                    "status": "success",
                    "started_at": started_at.isoformat(),
                    "ended_at": ended_at.isoformat(),
                    "duration_ms": duration_ms,
                    "model": model,
                    "provider": provider,
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "cost_usd": cost_usd,
                    "input": {"messages": messages},
                    "output": {"choices": [{"message": output_message}]},
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
                    "name": f"openai.chat.completions.create ({model})",
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

    Completions.create = patched_create

    try:
        from openai.resources.chat.completions import AsyncCompletions

        original_async_create = AsyncCompletions.create

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
            provider = "openai"
            started_at = datetime.now(timezone.utc)
            start_time = time.time()
            messages = kwargs.get("messages", [])
            is_stream = kwargs.get("stream", False)

            if is_stream:
                stream_options = kwargs.get("stream_options", {}) or {}
                stream_options["include_usage"] = True
                kwargs["stream_options"] = stream_options

                try:
                    response = await original_async_create(self, *args, **kwargs)
                except Exception as e:
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)
                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"openai.chat.completions.create ({model})",
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
                    prompt_tokens = 0
                    completion_tokens = 0
                    try:
                        async for chunk in stream_resp:
                            yield chunk
                            if hasattr(chunk, "choices") and chunk.choices:
                                choice = chunk.choices[0]
                                if hasattr(choice, "delta") and choice.delta:
                                    if hasattr(choice.delta, "content") and choice.delta.content:
                                        accumulated_content.append(choice.delta.content)
                            if hasattr(chunk, "usage") and chunk.usage:
                                prompt_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                                completion_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0
                    finally:
                        ended_at = datetime.now(timezone.utc)
                        duration_ms = int((time.time() - start_time) * 1000)
                        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
                        full_output = "".join(accumulated_content)

                        span_payload = {
                            "id": span_id,
                            "trace_id": trace_id,
                            "parent_span_id": parent_span_id,
                            "name": f"openai.chat.completions.create ({model})",
                            "span_type": "llm",
                            "status": "success",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "duration_ms": duration_ms,
                            "model": model,
                            "provider": provider,
                            "input_tokens": prompt_tokens,
                            "output_tokens": completion_tokens,
                            "cost_usd": cost_usd,
                            "input": {"messages": messages},
                            "output": {
                                "choices": [
                                    {
                                        "message": {
                                            "role": "assistant",
                                            "content": full_output,
                                        }
                                    }
                                ]
                            },
                        }
                        agentlens._global_client._safe_enqueue(span_payload)

                return async_stream_wrapper(response)
            else:
                try:
                    response = await original_async_create(self, *args, **kwargs)
                    ended_at = datetime.now(timezone.utc)
                    duration_ms = int((time.time() - start_time) * 1000)

                    prompt_tokens = 0
                    completion_tokens = 0
                    output_message = {}
                    if hasattr(response, "usage") and response.usage:
                        prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                        completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                    if hasattr(response, "choices") and response.choices:
                        choice = response.choices[0]
                        if hasattr(choice, "message") and choice.message:
                            output_message = {
                                "role": getattr(choice.message, "role", "assistant"),
                                "content": getattr(choice.message, "content", ""),
                            }

                    cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)

                    span_payload = {
                        "id": span_id,
                        "trace_id": trace_id,
                        "parent_span_id": parent_span_id,
                        "name": f"openai.chat.completions.create ({model})",
                        "span_type": "llm",
                        "status": "success",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": duration_ms,
                        "model": model,
                        "provider": provider,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                        "cost_usd": cost_usd,
                        "input": {"messages": messages},
                        "output": {"choices": [{"message": output_message}]},
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
                        "name": f"openai.chat.completions.create ({model})",
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

        AsyncCompletions.create = patched_async_create
    except Exception:
        pass
