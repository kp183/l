"""AgentLens Python SDK — zero-overhead observability for AI agents.
"""

from __future__ import annotations

import atexit
import logging
from typing import Optional

from agentlens.client import AgentLensClient
from agentlens.decorators import span, trace
from agentlens.instruments.anthropic import instrument_anthropic
from agentlens.instruments.openai import instrument_openai

__all__ = [
    "init",
    "instrument_openai",
    "instrument_anthropic",
    "trace",
    "span",
    "flush",
]

_global_client: Optional[AgentLensClient] = None
logger = logging.getLogger("agentlens")


def init(
    api_key: str,
    base_url: str = "http://localhost:8000",
    debug: bool = False,
    enabled: bool = True,
) -> AgentLensClient:
    """Initialize the global AgentLens client."""
    global _global_client

    if _global_client is not None:
        _global_client.stop()

    _global_client = AgentLensClient(
        api_key=api_key,
        base_url=base_url,
        debug=debug,
        enabled=enabled,
    )

    # Register exit handler to flush queue on shutdown
    if enabled:
        atexit.register(flush)

    return _global_client


def flush(timeout: float = 5.0) -> None:
    """Flush all currently buffered spans in the global client."""
    global _global_client
    if _global_client is not None and _global_client.enabled:
        try:
            _global_client.flush(timeout=timeout)
        except Exception as e:
            if _global_client.debug:
                logger.debug(f"Failed to flush spans: {e}", exc_info=True)
