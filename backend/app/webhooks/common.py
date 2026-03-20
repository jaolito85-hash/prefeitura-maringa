"""
common.py - Utilitarios compartilhados pelos webhooks da Evolution API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Header, HTTPException, Query, Request, status

from app.config import settings
from app.services.webhook_queue import QueueUnavailableError, enqueue_webhook


def require_evolution_apikey(
    apikey_header: str | None = Header(default=None, alias="apikey"),
    apikey_query: str | None = Query(default=None, alias="apikey"),
) -> str | None:
    # Aceita a chave tanto pelo header quanto pela URL (?apikey=...)
    apikey = apikey_header or apikey_query

    expected_key = (settings.evolution_api_key or "").strip()
    placeholder_key = "sua-chave-api-aqui"

    if not expected_key or expected_key == placeholder_key:
        if settings.debug:
            return apikey
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EVOLUTION_API_KEY nao configurada no backend.",
        )

    if apikey != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="apikey invalida.",
        )

    return apikey


async def queue_incoming_webhook(
    request: Request,
    payload: dict[str, Any],
    *,
    channel: str,
    queue_name: str,
    instance_name: str,
) -> dict[str, Any]:
    event = {
        "channel": channel,
        "instance_name": instance_name,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "client_ip": request.client.host if request.client else None,
        "path": str(request.url.path),
        "payload": payload,
    }

    try:
        queue_depth = enqueue_webhook(queue_name, event)
    except QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return {
        "status": "accepted",
        "channel": channel,
        "queue": queue_name,
        "queue_depth": queue_depth,
    }
