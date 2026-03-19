"""
Webhook do canal SOS Mulher da Evolution API.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.config import settings
from app.webhooks.common import queue_incoming_webhook, require_evolution_apikey

router = APIRouter()


@router.post("/sos-mulher", status_code=status.HTTP_202_ACCEPTED)
async def receber_webhook_sos_mulher(
    payload: dict[str, Any],
    request: Request,
    _: str | None = Depends(require_evolution_apikey),
):
    return await queue_incoming_webhook(
        request,
        payload,
        channel="sos_mulher",
        queue_name="queue:sos",
        instance_name=settings.wa_instance_sos,
    )
