#!/usr/bin/env python3
"""
worker.py — Processador de webhooks da fila Redis (v2 — com IA)
================================================================
Le mensagens da fila Redis e:
  1. Salva no Supabase (na tabela correta conforme classificacao da IA)
  2. Responde o cidadao via Evolution API
  3. Cria/atualiza sessao de conversa

IMPORTANTE: A fila SOS vem PRIMEIRO no blpop — prioridade maxima.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date
from typing import Any

import httpx
import redis as redis_lib
from supabase import create_client, Client

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("worker")

# ── Config ─────────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

# PRIORIDADE: SOS primeiro, depois denuncias, ocorrencias, feedbacks
QUEUES = ["queue:sos", "queue:denuncias", "queue:ocorrencias", "queue:feedbacks"]


# ── Helpers ────────────────────────────────────────────────────────────────

def gerar_protocolo(sb: Client) -> str:
    """Gera protocolo unico via sequence do PostgreSQL."""
    try:
        result = sb.rpc("nextval", {"seq_name": "protocolo_seq"}).execute()
        seq = result.data
        return f"MGA-{date.today().year}-{str(seq).zfill(5)}"
    except Exception as exc:
        logger.error(f"Falha ao gerar protocolo via sequence: {exc}")
        import uuid
        return f"MGA-{date.today().year}-{str(uuid.uuid4())[:8].upper()}"


def enviar_whatsapp(telefone: str, mensagem: str) -> bool:
    """
    Envia mensagem pro cidadao via Evolution API.
    Retorna True se enviou, False se falhou.
    """
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        logger.warning("Evolution API nao configurada — mensagem nao enviada")
        return False

    numero = telefone.lstrip("+")
    url = f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}"

    payload = {
        "number": numero,
        "text": mensagem,
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.status_code in (200, 201):
            logger.info(f"Resposta enviada para {telefone}")
            return True
        else:
            logger.error(f"Falha ao enviar WhatsApp: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as exc:
        logger.error(f"Erro ao enviar WhatsApp para {telefone}: {exc}")
        return False


# ── Processadores por canal ────────────────────────────────────────────────

def processar_denuncia(event: dict, sb: Client) -> None:
    """Processa denuncia classificada pela IA."""
    classificacao = event.get("classificacao", {})
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")

    protocolo = gerar_protocolo(sb)
    categoria = classificacao.get("categoria", "outros")

    res = sb.table("denuncias").insert({
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "mensagem": texto,
        "bairro": classificacao.get("bairro"),
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
        "status": "novo",
    }).execute()

    if res.data:
        logger.info(f"Denuncia criada: {protocolo} ({categoria})")
        resposta = classificacao.get("resposta_whatsapp", "")
        if resposta:
            enviar_whatsapp(telefone, f"{resposta}\n\n📋 Protocolo: {protocolo}")
    else:
        logger.error(f"Falha ao criar denuncia. Resposta: {res}")


def processar_sos(event: dict, sb: Client) -> None:
    """Processa alerta SOS — PRIORIDADE MAXIMA."""
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    classificacao = event.get("classificacao", {})

    logger.warning(f"🚨🚨🚨 PROCESSANDO SOS de {telefone}")

    cad = sb.table("sos_cadastros").select("id").eq("telefone", telefone).execute()
    cadastro_id = cad.data[0]["id"] if cad.data else None

    res = sb.table("sos_alertas").insert({
        "telefone": telefone,
        "codigo_usado": texto[:50] if texto else "sem_texto",
        "cadastro_id": cadastro_id,
        "status": "active",
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
    }).execute()

    if res.data:
        logger.warning(f"🚨 SOS ALERTA CRIADO para {telefone} (id={res.data[0]['id']})")
        resposta = classificacao.get("resposta_whatsapp",
                                      "✓ Recebido. Se puder, envie sua localização: 📎 > Localização")
        enviar_whatsapp(telefone, resposta)
    else:
        logger.error(f"Falha ao criar SOS alerta. Resposta: {res}")


def processar_ocorrencia(event: dict, sb: Client) -> None:
    """Processa ocorrencia classificada pela IA."""
    classificacao = event.get("classificacao", {})
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")

    protocolo = gerar_protocolo(sb)
    categoria = classificacao.get("categoria", "outros_urbanos")
    titulo = classificacao.get("resumo", texto[:200] if texto else "Ocorrencia")

    res = sb.table("ocorrencias").insert({
        "protocolo": protocolo,
        "categoria": categoria,
        "titulo": titulo,
        "endereco": texto[:500] if texto else "",
        "endereco_normalizado": texto[:500].lower() if texto else "",
        "status": "aberto",
        "severidade": "baixa",
        "total_relatos": 1,
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
    }).execute()

    if res.data:
        ocorrencia_id = res.data[0]["id"]
        logger.info(f"Ocorrencia criada: {protocolo} ({categoria})")

        sb.table("ocorrencias_relatos").insert({
            "ocorrencia_id": ocorrencia_id,
            "telefone": telefone,
            "nome": push_name or None,
            "mensagem": texto,
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
        }).execute()

        resposta = classificacao.get("resposta_whatsapp", "")
        if resposta:
            enviar_whatsapp(telefone, f"{resposta}\n\n📋 Protocolo: {protocolo}")
    else:
        logger.error(f"Falha ao criar ocorrencia. Resposta: {res}")


def processar_feedback(event: dict, sb: Client) -> None:
    """Processa feedback classificado pela IA."""
    classificacao = event.get("classificacao", {})
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")

    protocolo = gerar_protocolo(sb)

    res = sb.table("feedbacks").insert({
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": classificacao.get("categoria", "outros"),
        "sentimento": classificacao.get("sentimento", "neutro"),
        "urgencia": classificacao.get("urgencia", "normal"),
        "mensagem": texto,
        "resumo": classificacao.get("resumo"),
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
        "status": "novo",
    }).execute()

    if res.data:
        logger.info(f"Feedback criado: {protocolo} (sentimento={classificacao.get('sentimento')})")
        resposta = classificacao.get("resposta_whatsapp", "")
        if resposta:
            enviar_whatsapp(telefone, f"{resposta}\n\n📋 Protocolo: {protocolo}")
    else:
        logger.error(f"Falha ao criar feedback. Resposta: {res}")


PROCESSADORES: dict[str, Any] = {
    "queue:sos": processar_sos,
    "queue:denuncias": processar_denuncia,
    "queue:ocorrencias": processar_ocorrencia,
    "queue:feedbacks": processar_feedback,
}


# ── Loop principal ─────────────────────────────────────────────────────────

def conectar() -> tuple[redis_lib.Redis, Client]:
    """Cria conexoes com Redis e Supabase, com retry."""
    while True:
        try:
            r = redis_lib.Redis.from_url(
                REDIS_URL, decode_responses=True,
                socket_connect_timeout=5, socket_timeout=5,
            )
            r.ping()
            sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Conectado ao Redis e Supabase!")
            return r, sb
        except Exception as exc:
            logger.error(f"Falha ao conectar: {exc}. Tentando novamente em 5s...")
            time.sleep(5)


def main() -> None:
    logger.info("Worker v2 (com IA) iniciando...")
    logger.info(f"Redis: {REDIS_URL}")
    logger.info(f"Filas (por prioridade): {QUEUES}")
    logger.info(f"Evolution API: {EVOLUTION_API_URL}")
    logger.info(f"Instancia WhatsApp: {WA_INSTANCE_NAME}")

    r, sb = conectar()
    logger.info("Worker pronto, aguardando mensagens...")

    while True:
        try:
            # blpop respeita a ORDEM das filas — SOS sempre primeiro!
            resultado = r.blpop(QUEUES, timeout=5)
            if resultado is None:
                continue

            fila, mensagem_raw = resultado
            logger.info(f"Mensagem recebida da fila '{fila}'")

            event = json.loads(mensagem_raw)
            processador = PROCESSADORES.get(fila)

            if processador:
                processador(event, sb)
            else:
                logger.warning(f"Nenhum processador para a fila: {fila}")

        except redis_lib.exceptions.ConnectionError as exc:
            logger.error(f"Redis desconectado: {exc}. Reconectando...")
            time.sleep(3)
            r, sb = conectar()

        except json.JSONDecodeError as exc:
            logger.error(f"Mensagem invalida (nao e JSON): {exc}")

        except Exception as exc:
            logger.exception(f"Erro ao processar mensagem: {exc}")


if __name__ == "__main__":
    main()
