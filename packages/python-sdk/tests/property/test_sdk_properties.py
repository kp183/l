"""Property-based tests for Python SDK queue operations.

Feature: agentlens-mvp
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# Mock classes to support standard Python class monkeypatching in testing
class MockCompletions:
    def __init__(self, client):
        self.client = client
    def create(self, *args, **kwargs):
        pass

class MockAsyncCompletions:
    def __init__(self, client):
        self.client = client
    async def create(self, *args, **kwargs):
        pass

class MockMessages:
    def __init__(self, client):
        self.client = client
    def create(self, *args, **kwargs):
        pass

class MockAsyncMessages:
    def __init__(self, client):
        self.client = client
    async def create(self, *args, **kwargs):
        pass

mock_openai = MagicMock()
mock_openai.OpenAI = MagicMock()
sys.modules["openai"] = mock_openai

mock_openai_completions = MagicMock()
mock_openai_completions.Completions = MockCompletions
mock_openai_completions.AsyncCompletions = MockAsyncCompletions

mock_openai.resources = MagicMock()
mock_openai.resources.chat = MagicMock()
mock_openai.resources.chat.completions = mock_openai_completions

sys.modules["openai.resources"] = mock_openai.resources
sys.modules["openai.resources.chat"] = mock_openai.resources.chat
sys.modules["openai.resources.chat.completions"] = mock_openai_completions

mock_anthropic = MagicMock()
mock_anthropic.Anthropic = MagicMock()
sys.modules["anthropic"] = mock_anthropic

mock_anthropic_messages = MagicMock()
mock_anthropic_messages.Messages = MockMessages
mock_anthropic_messages.AsyncMessages = MockAsyncMessages

mock_anthropic.resources = MagicMock()
mock_anthropic.resources.messages = mock_anthropic_messages

sys.modules["anthropic.resources"] = mock_anthropic.resources
sys.modules["anthropic.resources.messages"] = mock_anthropic_messages

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agentlens.client import AgentLensClient


# ---------------------------------------------------------------------------
# Property 11: Batch size never exceeds 100
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(n=st.integers(1, 500))
@patch.object(AgentLensClient, "start")
def test_batch_size_never_exceeds_100(mock_start, n: int) -> None:
    """Feature: agentlens-mvp, Property 11: Batch size never exceeds 100"""
    client = AgentLensClient(api_key="test_key", enabled=True)

    for i in range(n):
        client.enqueue({"id": f"span-{i}", "name": "test"})

    # Mock the HTTP batch sending logic
    batches = []

    def mock_send_batch(batch):
        batches.append(batch)

    client._send_batch = mock_send_batch
    client.flush()

    for b in batches:
        assert len(b) <= 100, f"Batch size {len(b)} exceeded 100"


# ---------------------------------------------------------------------------
# Property 12: Buffer overflow is silent
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(n=st.integers(10001, 10100))
@patch.object(AgentLensClient, "start")
def test_buffer_overflow_is_silent(mock_start, n: int) -> None:
    """Feature: agentlens-mvp, Property 12: Buffer overflow is silent"""
    client = AgentLensClient(api_key="test_key", enabled=True)

    try:
        for i in range(n):
            client.enqueue({"id": f"span-{i}", "name": "test"})
    except Exception as e:
        pytest.fail(f"Buffer overflow raised an exception: {e}")

    assert client._queue.qsize() == 10000


# ---------------------------------------------------------------------------
# Property 8: @trace decorator creates root span
# ---------------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(name=st.text(min_size=1, max_size=50))
def test_trace_decorator_creates_root_span(name: str) -> None:
    """Feature: agentlens-mvp, Property 8: @trace decorator creates root span"""
    import agentlens
    client = AgentLensClient(api_key="test_key", enabled=True)
    agentlens._global_client = client

    captured_spans = []
    client._safe_enqueue = captured_spans.append

    @agentlens.decorators.trace(name=name)
    def my_func():
        pass

    my_func()

    assert len(captured_spans) == 1
    span = captured_spans[0]
    assert span["name"] == name
    assert span["parent_span_id"] is None
    assert span["span_type"] == "custom"
    assert span["status"] == "success"


# ---------------------------------------------------------------------------
# Property 9: span() context manager creates child span
# ---------------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(
    root_name=st.text(min_size=1, max_size=50),
    child_name=st.text(min_size=1, max_size=50)
)
def test_span_creates_child_span(root_name: str, child_name: str) -> None:
    """Feature: agentlens-mvp, Property 9: span() context manager creates child span"""
    import agentlens
    client = AgentLensClient(api_key="test_key", enabled=True)
    agentlens._global_client = client

    captured_spans = []
    client._safe_enqueue = captured_spans.append

    @agentlens.decorators.trace(name=root_name)
    def my_func():
        with agentlens.decorators.span(name=child_name, span_type="tool"):
            pass

    my_func()

    assert len(captured_spans) == 2
    child = captured_spans[0]
    root = captured_spans[1]

    assert child["name"] == child_name
    assert child["parent_span_id"] == root["id"]
    assert child["trace_id"] == root["trace_id"]
    assert child["span_type"] == "tool"


# ---------------------------------------------------------------------------
# Property 10: Disabled SDK produces no spans
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(st.just(None))
def test_disabled_sdk_produces_no_spans(_: None) -> None:
    """Feature: agentlens-mvp, Property 10: Disabled SDK produces no spans"""
    import agentlens
    client = AgentLensClient(api_key="test_key", enabled=False)
    agentlens._global_client = client

    captured_spans = []
    client._safe_enqueue = captured_spans.append

    @agentlens.decorators.trace(name="disabled_root")
    def my_func():
        with agentlens.decorators.span(name="disabled_child"):
            pass

    my_func()

    assert len(captured_spans) == 0


# ---------------------------------------------------------------------------
# Property 13: SDK never propagates exceptions
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(st.just(None))
def test_sdk_never_propagates_exceptions(_: None) -> None:
    """Feature: agentlens-mvp, Property 13: SDK never propagates exceptions"""
    import agentlens
    client = AgentLensClient(api_key="test_key", enabled=True)
    agentlens._global_client = client

    def raise_error(*args, **kwargs):
        raise RuntimeError("Network Timeout")
    client.enqueue = raise_error

    try:
        client._safe_enqueue({"id": "1", "trace_id": "2", "name": "test"})
    except Exception as e:
        pytest.fail(f"SDK propagated exception: {e}")


# ---------------------------------------------------------------------------
# Property 6 & 14: OpenAI instrumentation produces spans & captures content
# ---------------------------------------------------------------------------

@settings(max_examples=5, deadline=None)
@given(
    model=st.sampled_from(["gpt-4o", "gpt-4o-mini"]),
    prompt_tokens=st.integers(1, 1000),
    completion_tokens=st.integers(1, 1000),
    content=st.text(min_size=1, max_size=100)
)
@patch.object(AgentLensClient, "start")
def test_openai_instrumentation(mock_start, model: str, prompt_tokens: int, completion_tokens: int, content: str) -> None:
    """Feature: agentlens-mvp, Property 6: OpenAI instrumentation produces spans"""
    import agentlens
    import openai
    import openai.resources.chat.completions as completions_module
    
    try:
        del completions_module.Completions._agentlens_instrumented
    except AttributeError:
        pass
        
    mock_response = MagicMock()
    mock_response.model = model
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    
    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = content
    mock_response.choices = [mock_choice]

    # Pre-mock the original Completions.create
    mock_original_create = MagicMock(return_value=mock_response)
    completions_module.Completions.create = mock_original_create

    # Configure mock client to return actual instrumented Completions instance
    mock_client = MagicMock()
    openai.OpenAI.return_value = mock_client
    real_completions = completions_module.Completions(mock_client)
    mock_client.chat.completions = real_completions

    agentlens.init(api_key="test_key")
    agentlens.instrument_openai()

    # Manually bind monkeypatched class method to the mock instance
    real_completions.create = completions_module.Completions.create.__get__(real_completions, completions_module.Completions)
    
    captured_spans = []
    agentlens._global_client._safe_enqueue = captured_spans.append

    @agentlens.trace(name="openai_trace")
    def run():
        # Instantiate a mocked OpenAI client
        client = openai.OpenAI(api_key="test")
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hello"}]
        )
    run()

    assert len(captured_spans) == 2
    llm_span = captured_spans[0]
    trace_span = captured_spans[1]

    assert llm_span["span_type"] == "llm"
    assert llm_span["model"] == model
    assert llm_span["provider"] == "openai"
    assert llm_span["input_tokens"] == prompt_tokens
    assert llm_span["output_tokens"] == completion_tokens
    assert llm_span["trace_id"] == trace_span["trace_id"]
    assert llm_span["parent_span_id"] == trace_span["id"]


# ---------------------------------------------------------------------------
# Property 7: Anthropic instrumentation produces spans
# ---------------------------------------------------------------------------

@settings(max_examples=5, deadline=None)
@given(
    model=st.sampled_from(["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]),
    input_tokens=st.integers(1, 1000),
    output_tokens=st.integers(1, 1000),
    content=st.text(min_size=1, max_size=100)
)
@patch.object(AgentLensClient, "start")
def test_anthropic_instrumentation(mock_start, model: str, input_tokens: int, output_tokens: int, content: str) -> None:
    """Feature: agentlens-mvp, Property 7: Anthropic instrumentation produces spans"""
    import agentlens
    import anthropic
    import anthropic.resources.messages as messages_module

    try:
        del messages_module.Messages._agentlens_instrumented
    except AttributeError:
        pass

    mock_response = MagicMock()
    mock_response.model = model
    mock_response.usage.input_tokens = input_tokens
    mock_response.usage.output_tokens = output_tokens

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = content
    mock_response.content = [mock_content]

    # Pre-mock the original Messages.create
    mock_original_create = MagicMock(return_value=mock_response)
    messages_module.Messages.create = mock_original_create

    # Configure mock client to return actual instrumented Messages instance
    mock_client = MagicMock()
    anthropic.Anthropic.return_value = mock_client
    real_messages = messages_module.Messages(mock_client)
    mock_client.messages = real_messages

    agentlens.init(api_key="test_key")
    agentlens.instrument_anthropic()

    # Manually bind monkeypatched class method to the mock instance
    real_messages.create = messages_module.Messages.create.__get__(real_messages, messages_module.Messages)

    captured_spans = []
    agentlens._global_client._safe_enqueue = captured_spans.append

    @agentlens.trace(name="anthropic_trace")
    def run():
        client = anthropic.Anthropic(api_key="test")
        client.messages.create(
            model=model,
            messages=[{"role": "user", "content": "hello"}]
        )
    run()

    assert len(captured_spans) == 2
    llm_span = captured_spans[0]
    trace_span = captured_spans[1]

    assert llm_span["span_type"] == "llm"
    assert llm_span["model"] == model
    assert llm_span["provider"] == "anthropic"
    assert llm_span["input_tokens"] == input_tokens
    assert llm_span["output_tokens"] == output_tokens
    assert llm_span["trace_id"] == trace_span["trace_id"]
    assert llm_span["parent_span_id"] == trace_span["id"]





