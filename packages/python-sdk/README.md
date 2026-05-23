# AgentLens Python SDK

The official Python client for AgentLens. Easily trace agent execution steps, nested tool calls, and LLM completions with non-blocking, asynchronous ingestion.

## Key Features

- **Micro-Batched Background Ingestion**: Uses a thread-safe daemon worker (`SpanQueue` wrapping a safe `queue.Queue`) to buffer and flush spans concurrently without delaying agent execution.
- **Zero-Dependency Exception Guard**: The SDK never propagates internal networking or API exceptions, ensuring your production agent runs remain robust.
- **Automatic Cost & Token Estimation**: Immediate calculations of token consumption and pricing for popular OpenAI and Anthropic models.
- **Auto-Instrumentation**: Monkey-patches OpenAI and Anthropic clients to capture inputs, outputs, tokens, and streaming responses out-of-the-box.

---

## Installation

Install the package via `pip` (or `uv` / `poetry`):

```bash
pip install agentlens
```

---

## Quick Start (2-Line Integration)

Instrument your application to capture all OpenAI completions automatically:

```python
import agentlens as al

# Initialize the global client and instrument the OpenAI SDK
al.init(api_key="al_live_YOUR_API_KEY_HERE", base_url="http://localhost:8000")
al.instrument_openai()
```

---

## Detailed Usage

### Decorators & Context Managers

Trace custom Python functions or specific logical blocks inside your agents:

```python
import agentlens as al

# 1. Trace a high-level agent loop
@al.trace(name="Customer Assistant Agent")
def run_assistant(user_query: str):
    print("Agent started...")
    
    # 2. Trace tool calls or sub-steps using context managers
    with al.span(name="Database Lookup", span_type="tool") as s:
        s.set_metadata("query", user_query)
        result = db_search(user_query)
        s.set_output({"results_count": len(result)})
        
    return result
```

### Auto-Instrumentation Examples

#### OpenAI (Both Streaming & Non-Streaming)

```python
import openai
import agentlens as al

al.init(api_key="al_live_...")
al.instrument_openai()

client = openai.OpenAI()

# Spans are automatically created for completions, including token counts and costs
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain quantizing neural networks."}]
)
```

#### Anthropic (Both Streaming & Non-Streaming)

```python
import anthropic
import agentlens as al

al.init(api_key="al_live_...")
al.instrument_anthropic()

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    messages=[{"role": "user", "content": "What is reinforcement learning?"}]
)
```

---

## Public API Reference

### `al.init(api_key: str, base_url: str = "http://localhost:8000", debug: bool = False, enabled: bool = True) -> None`
Configures the global AgentLens client, spins up the thread-safe background ingestion worker, and registers an `atexit` hook to flush remaining spans on application termination.
- `api_key`: Your active AgentLens project API key (prefixed with `al_live_`).
- `base_url`: Endpoint of your FastAPI backend.
- `debug`: Enable internal logging for SDK debugging.
- `enabled`: If set to `False`, all tracing operations, monkey-patches, and decorators gracefully fallback to no-ops.

### `al.trace(name: str | None = None, tags: list[str] | None = None)`
Decorator to declare a new root trace context. Propagates the trace context down the execution tree.

### `al.span(name: str, span_type: str = "custom")`
Context manager to record a logical sub-step inside an active trace context. Supports updating metadata and final outputs.

### `al.flush(timeout: float = 5.0) -> None`
Manually blocks and flushes any enqueued spans to the API backend up to the specified timeout. Excellent for short-running serverless function environments.
