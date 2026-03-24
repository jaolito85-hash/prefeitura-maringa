"""
rate_limiter.py — Proteções anti-abuso usando Redis.
=====================================================
Contadores com TTL automático no Redis pra limitar:
  - Mensagens por dia (30/dia por telefone)
  - Consultas de protocolo (3/hora por telefone)

Usa chaves Redis com prefixo "rl:" (rate limit).
O TTL garante que as chaves somem sozinhas — sem cron, sem limpeza manual.
"""
from __future__ import annotations

import logging
from typing import NamedTuple

from app.services.webhook_queue import get_redis

logger = logging.getLogger("rate_limiter")


# ── Constantes ──────────────────────────────────────────────
MAX_CHARS_MENSAGEM = 600          # ~10 linhas de WhatsApp
MAX_MENSAGENS_DIA = 500           # por telefone, por dia (500 para demo)
MAX_CONSULTAS_PROTOCOLO_HORA = 3  # por telefone, por hora

# TTLs em segundos
TTL_DIA = 86400     # 24 horas
TTL_HORA = 3600     # 1 hora


class RateLimitResult(NamedTuple):
    """Resultado de uma checagem de rate limit."""
    allowed: bool       # True = pode passar, False = bloqueado
    current: int        # Contagem atual (após incremento)
    limit: int          # Limite máximo
    retry_after: int    # Segundos até poder tentar de novo (0 se allowed)


def truncar_mensagem(texto: str) -> tuple[str, bool]:
    """
    Trunca texto em MAX_CHARS_MENSAGEM caracteres.
    Retorna (texto_truncado, foi_truncado).

    Se truncar, corta na última palavra completa pra não ficar
    palavra cortada no meio (ex: "denún" → corta antes).
    """
    if not texto or len(texto) <= MAX_CHARS_MENSAGEM:
        return texto, False

    # Corta no limite
    truncado = texto[:MAX_CHARS_MENSAGEM]

    # Tenta cortar na última palavra completa (último espaço)
    ultimo_espaco = truncado.rfind(" ")
    if ultimo_espaco > MAX_CHARS_MENSAGEM * 0.7:  # Só se não perder muito
        truncado = truncado[:ultimo_espaco]

    return truncado.rstrip(), True


def checar_limite_diario(telefone: str) -> RateLimitResult:
    """
    Verifica e incrementa o contador diário de mensagens.

    Chave Redis: rl:dia:{telefone}
    TTL: 24 horas (expira sozinha)

    Retorna RateLimitResult indicando se pode passar.
    """
    r = get_redis()
    key = f"rl:dia:{telefone}"

    try:
        # INCR atômico — cria a chave se não existe (valor 1)
        count = r.incr(key)

        # Se é a primeira mensagem do dia, seta o TTL
        if count == 1:
            r.expire(key, TTL_DIA)

        ttl = r.ttl(key)

        if count > MAX_MENSAGENS_DIA:
            logger.warning(
                f"⚠️ Limite diário atingido: {telefone} ({count}/{MAX_MENSAGENS_DIA})"
            )
            return RateLimitResult(
                allowed=False,
                current=count,
                limit=MAX_MENSAGENS_DIA,
                retry_after=max(ttl, 0),
            )

        return RateLimitResult(
            allowed=True, current=count,
            limit=MAX_MENSAGENS_DIA, retry_after=0,
        )
    except Exception as exc:
        # Se Redis falhar, deixa passar (fail-open)
        # Melhor aceitar uma msg a mais do que bloquear cidadão
        logger.error(f"Erro no rate limit diário: {exc}")
        return RateLimitResult(allowed=True, current=0, limit=MAX_MENSAGENS_DIA, retry_after=0)


def checar_limite_consulta_protocolo(telefone: str) -> RateLimitResult:
    """
    Verifica e incrementa o contador de consultas de protocolo por hora.

    Chave Redis: rl:consulta:{telefone}
    TTL: 1 hora

    Retorna RateLimitResult indicando se pode consultar.
    """
    r = get_redis()
    key = f"rl:consulta:{telefone}"

    try:
        count = r.incr(key)

        if count == 1:
            r.expire(key, TTL_HORA)

        ttl = r.ttl(key)

        if count > MAX_CONSULTAS_PROTOCOLO_HORA:
            logger.warning(
                f"⚠️ Limite consulta protocolo: {telefone} ({count}/{MAX_CONSULTAS_PROTOCOLO_HORA})"
            )
            return RateLimitResult(
                allowed=False,
                current=count,
                limit=MAX_CONSULTAS_PROTOCOLO_HORA,
                retry_after=max(ttl, 0),
            )

        return RateLimitResult(
            allowed=True, current=count,
            limit=MAX_CONSULTAS_PROTOCOLO_HORA, retry_after=0,
        )
    except Exception as exc:
        logger.error(f"Erro no rate limit consulta: {exc}")
        return RateLimitResult(
            allowed=True, current=0,
            limit=MAX_CONSULTAS_PROTOCOLO_HORA, retry_after=0,
        )
