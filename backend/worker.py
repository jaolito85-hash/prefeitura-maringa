#!/usr/bin/env python3
"""
worker.py — Processador de webhooks da fila Redis.
Le mensagens brutas do Redis (rpush) e salva no Supabase.
Substitui o 'rq worker' que era incompativel com o formato de fila usado.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date
from typing import Any

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
QUEUES = ["queue:ocorrencias", "queue:denuncias", "queue:sos"]


# ── Helpers ────────────────────────────────────────────────────────────────

def extract_phone(remote_jid: str) -> str:
    """Extrai o numero de telefone do remoteJid do Evolution API."""
    phone = remote_jid.split("@")[0].split(":")[0]
    if not phone.startswith("+"):
        phone = "+" + phone
    return phone


def extract_text(message_data: dict) -> str:
    """Extrai o texto da mensagem do payload do Evolution API."""
    msg = message_data.get("message", {}) or {}
    if "conversation" in msg:
        return msg["conversation"]
    if "extendedTextMessage" in msg:
        return msg["extendedTextMessage"].get("text", "")
    if "imageMessage" in msg:
        return msg["imageMessage"].get("caption", "[Imagem]")
    if "videoMessage" in msg:
        return msg["videoMessage"].get("caption", "[Video]")
    if "audioMessage" in msg:
        return "[Audio]"
    if "documentMessage" in msg:
        return msg["documentMessage"].get("caption", "[Documento]")
    return "[Mensagem nao suportada]"


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


def detectar_categoria_ocorrencia(texto: str) -> str:
    t = texto.lower()
    if any(w in t for w in ["buraco", "cratera", "asfalto", "pavimento", "calcada"]):
        return "conservacao_de_vias"
    if any(w in t for w in ["lixo", "entulho", "descarte", "residuo"]):
        return "limpeza_urbana"
    if any(w in t for w in ["iluminacao", "poste", "lampada", "luz", "escuro"]):
        return "iluminacao_publica"
    if any(w in t for w in ["alagamento", "enchente", "esgoto", "bueiro", "agua"]):
        return "drenagem"
    if any(w in t for w in ["arvore", "poda", "galho"]):
        return "arborizacao"
    return "geral"


def detectar_categoria_denuncia(texto: str) -> str:
    t = texto.lower()
    if any(w in t for w in ["droga", "trafico", "entorpecente"]):
        return "trafico_drogas"
    if any(w in t for w in ["roubo", "furto", "assalto"]):
        return "roubo_furto"
    if any(w in t for w in ["violencia", "briga", "agressao"]):
        return "violencia"
    if any(w in t for w in ["barulho", "som", "perturbacao"]):
        return "perturbacao_sossego"
    return "outros"


# ── Processadores por canal ────────────────────────────────────────────────

def processar_ocorrencias(event: dict, sb: Client) -> None:
    payload = event.get("payload", {})
    data = payload.get("data", {}) if isinstance(payload, dict) else {}

    if isinstance(data, dict):
        key = data.get("key", {})
        if key.get("fromMe", False):
            logger.debug("Ignorando mensagem enviada pelo bot.")
            return
        phone = extract_phone(key.get("remoteJid", "desconhecido"))
        push_name = data.get("pushName", "")
        texto = extract_text(data)
    else:
        phone = "desconhecido"
        push_name = ""
        texto = str(payload)

    if not texto or texto.startswith("["):
        logger.info(f"Ignorando mensagem nao textual de {phone}: {texto}")
        return

    logger.info(f"Ocorrencia de {phone}: {texto[:80]}")
    protocolo = gerar_protocolo(sb)
    categoria = detectar_categoria_ocorrencia(texto)
    titulo = texto.split("\n")[0][:200]

    res = sb.table("ocorrencias").insert({
        "protocolo": protocolo,
        "categoria": categoria,
        "titulo": titulo,
        "endereco": texto[:500],
        "endereco_normalizado": texto[:500],
        "status": "aberto",
        "severidade": "baixa",
        "total_relatos": 1,
    }).execute()

    if res.data:
        ocorrencia_id = res.data[0]["id"]
        sb.table("ocorrencias_relatos").insert({
            "ocorrencia_id": ocorrencia_id,
            "telefone": phone,
            "nome": push_name or None,
            "mensagem": texto,
        }).execute()
        logger.info(f"Ocorrencia criada: {protocolo} (id={ocorrencia_id})")
    else:
        logger.error(f"Falha ao criar ocorrencia. Resposta: {res}")


def processar_denuncias(event: dict, sb: Client) -> None:
    payload = event.get("payload", {})
    data = payload.get("data", {}) if isinstance(payload, dict) else {}

    if isinstance(data, dict):
        key = data.get("key", {})
        if key.get("fromMe", False):
            return
        phone = extract_phone(key.get("remoteJid", "desconhecido"))
        push_name = data.get("pushName", "")
        texto = extract_text(data)
    else:
        phone = "desconhecido"
        push_name = ""
        texto = str(payload)

    if not texto or texto.startswith("["):
        return

    logger.info(f"Denuncia de {phone}: {texto[:80]}")
    protocolo = gerar_protocolo(sb)
    categoria = detectar_categoria_denuncia(texto)

    res = sb.table("denuncias").insert({
        "protocolo": protocolo,
        "telefone": phone,
        "nome": push_name or None,
        "categoria": categoria,
        "mensagem": texto,
        "status": "novo",
    }).execute()

    if res.data:
        logger.info(f"Denuncia criada: {protocolo}")
    else:
        logger.error(f"Falha ao criar denuncia. Resposta: {res}")


def processar_sos(event: dict, sb: Client) -> None:
    payload = event.get("payload", {})
    data = payload.get("data", {}) if isinstance(payload, dict) else {}

    if isinstance(data, dict):
        key = data.get("key", {})
        if key.get("fromMe", False):
            return
        phone = extract_phone(key.get("remoteJid", "desconhecido"))
        texto = extract_text(data)
    else:
        phone = "desconhecido"
        texto = str(payload)

    if not texto:
        return

    logger.info(f"SOS de {phone}: {texto[:80]}")

    # Verifica se ha cadastro vinculado
    cad = sb.table("sos_cadastros").select("id").eq("telefone", phone).execute()
    cadastro_id = cad.data[0]["id"] if cad.data else None

    res = sb.table("sos_alertas").insert({
        "telefone": phone,
        "codigo_usado": texto[:50],
        "cadastro_id": cadastro_id,
        "status": "active",
    }).execute()

    if res.data:
        logger.info(f"SOS alerta criado para {phone}")
    else:
        logger.error(f"Falha ao criar SOS alerta. Resposta: {res}")


PROCESSADORES: dict[str, Any] = {
    "queue:ocorrencias": processar_ocorrencias,
    "queue:denuncias": processar_denuncias,
    "queue:sos": processar_sos,
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
    logger.info("Worker iniciando...")
    logger.info(f"Redis: {REDIS_URL}")
    logger.info(f"Filas: {QUEUES}")

    r, sb = conectar()
    logger.info("Worker pronto, aguardando mensagens...")

    while True:
        try:
            resultado = r.blpop(QUEUES, timeout=5)
            if resultado is None:
                continue  # timeout — volta ao loop

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
