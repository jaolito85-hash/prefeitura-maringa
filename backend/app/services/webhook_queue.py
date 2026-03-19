"""
webhook_queue.py - Fila simples de webhooks em Redis.
Os handlers aceitam a requisicao rapidamente e persistem o payload
para processamento posterior.
"""
from __future__ import annotations

import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings

_client: Redis | None = None


class QueueUnavailableError(RuntimeError):
    """Falha ao persistir eventos na fila Redis."""


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            health_check_interval=30,
        )
    return _client


def enqueue_webhook(queue_name: str, event: dict[str, Any]) -> int:
    try:
        return int(get_redis().rpush(queue_name, json.dumps(event, ensure_ascii=False)))
    except RedisError as exc:
        raise QueueUnavailableError(
            f"Falha ao enviar evento para a fila {queue_name}."
        ) from exc
