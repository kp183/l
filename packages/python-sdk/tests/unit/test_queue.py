import time
import pytest
from unittest.mock import patch, MagicMock
from agentlens.client import AgentLensClient


@patch.object(AgentLensClient, "start")
def test_queue_overflow_silent(mock_start):
    # Initialize enabled client but mocked start so background thread doesn't start
    client = AgentLensClient(api_key="test_key", enabled=True)
    
    # Fill queue to maximum size of 10000
    for i in range(10000):
        client.enqueue({"id": f"span-{i}", "name": "test"})
    
    assert client._queue.qsize() == 10000
    
    # Enqueue 10,001st item. It should not raise an exception, and the queue size should still be 10,000
    try:
        client.enqueue({"id": "span-10001", "name": "overflow"})
    except Exception as e:
        pytest.fail(f"Enqueueing on full queue raised an exception: {e}")
        
    assert client._queue.qsize() == 10000


@patch("agentlens.client.httpx.Client")
@patch.object(AgentLensClient, "start")
def test_flush_drains_queue(mock_start, mock_httpx_client):
    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_httpx_client.return_value.__enter__.return_value.post = mock_post

    client = AgentLensClient(api_key="test_key", enabled=True)
    
    # Enqueue 250 items
    for i in range(250):
        client.enqueue({"id": f"span-{i}", "name": "test"})
        
    assert client._queue.qsize() == 250
    
    client.flush()
    
    assert client._queue.qsize() == 0
    # 250 items should be sent in 3 batches: 100, 100, 50
    assert mock_post.call_count == 3

