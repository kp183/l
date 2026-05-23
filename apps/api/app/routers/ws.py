"""WebSocket endpoint for real-time trace streaming.

WS /v1/ws/traces/{trace_id}?token=<jwt_or_api_key>

Subscribes to Redis channel ``trace:{trace_id}`` and forwards span events
to the connected client.  Sends ``{"type": "trace_ended", ...}`` when the
trace reaches a terminal status.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import engine
from app.exceptions import AuthenticationError, AuthorizationError
from app.redis_client import redis_client
from app.schemas.traces import TraceDetail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["websocket"])

_SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _authenticate(token: str, trace_id: uuid.UUID) -> bool:
    """Authenticate the WebSocket connection via JWT or API key.

    Returns True if the token grants access to the trace's project.
    Raises AuthenticationError / AuthorizationError on failure.
    """
    from app.config import get_settings
    from app.middleware.auth import _get_jwks, hash_api_key
    from app.models.api_key import APIKey
    from app.models.trace import Trace
    from sqlalchemy import select

    settings = get_settings()

    async with _SessionLocal() as session:
        # Try API key first (starts with al_live_)
        if token.startswith("al_live_"):
            key_hash = hash_api_key(token)
            result = await session.execute(
                select(APIKey).where(
                    APIKey.key_hash == key_hash,
                    APIKey.revoked_at.is_(None),
                )
            )
            api_key = result.scalar_one_or_none()
            if not api_key:
                raise AuthenticationError("Invalid API key")

            trace_result = await session.execute(
                select(Trace).where(Trace.id == trace_id)
            )
            trace = trace_result.scalar_one_or_none()
            if not trace or trace.project_id != api_key.project_id:
                raise AuthorizationError("Access denied")
            return True

        # Try Clerk JWT
        from jose import JWTError, jwt as jose_jwt
        try:
            jwks = await _get_jwks()
            payload = jose_jwt.decode(
                token, jwks, algorithms=["RS256"], options={"verify_aud": False}
            )
            clerk_id = payload.get("sub")
            if not clerk_id:
                raise AuthenticationError("Invalid JWT")

            from app.models.org import OrgMember
            from app.models.project import Project
            from app.models.user import User

            user_result = await session.execute(
                select(User).where(User.clerk_id == clerk_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise AuthenticationError("User not found")

            trace_result = await session.execute(
                select(Trace).where(Trace.id == trace_id)
            )
            trace = trace_result.scalar_one_or_none()
            if not trace:
                raise AuthorizationError("Trace not found")

            member_result = await session.execute(
                select(OrgMember).where(
                    OrgMember.user_id == user.id,
                    OrgMember.org_id == select(Project.org_id)
                    .where(Project.id == trace.project_id)
                    .scalar_subquery(),
                )
            )
            if not member_result.scalar_one_or_none():
                raise AuthorizationError("Access denied")
            return True

        except JWTError as exc:
            raise AuthenticationError(f"Invalid JWT: {exc}") from exc


@router.websocket("/ws/traces/{trace_id}")
async def trace_websocket(
    websocket: WebSocket,
    trace_id: uuid.UUID,
    token: str | None = None,
) -> None:
    """Stream span events for a running trace."""
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        await _authenticate(token, trace_id)
    except (AuthenticationError, AuthorizationError) as exc:
        await websocket.close(code=4001, reason=str(exc))
        return

    await websocket.accept()
    channel = f"trace:{trace_id}"

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    async def _listen() -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json({"type": "span", "data": data})
                except Exception:
                    logger.debug("Failed to forward span message", exc_info=True)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    task = asyncio.create_task(_listen())

    try:
        while True:
            # Keep connection alive; client disconnect raises WebSocketDisconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
