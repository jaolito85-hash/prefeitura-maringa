"""
unificado.py — Webhook UNIFICADO com SESSAO de conversa.
=========================================================
Agora o webhook verifica se o cidadao JA TEM uma conversa ativa.
Se tem → continua no mesmo protocolo (nao abre outro).
Se nao tem → classifica e abre protocolo novo.

Fluxo:
  1. Mensagem chega
  2. Checa SOS rapido (< 2s)
  3. Busca sessao ativa no Supabase pra esse telefone
  4. Se tem sessao → marca como CONTINUACAO (mesmo protocolo)
  5. Se nao tem → classifica com IA (protocolo novo)
  6. Coloca na fila Redis
  7. Worker processa, salva, responde
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.services.classificador import classificar_mensagem, detectar_sos_rapido
from app.services.supabase_client import get_supabase
from app.services.webhook_queue import enqueue_webhook, QueueUnavailableError
from app.webhooks.common import require_evolution_apikey

logger = logging.getLogger("webhook.unificado")

router = APIRouter()


def _extrair_dados_evolution(payload: dict) -> dict[str, Any]:
    """Extrai dados relevantes do payload da Evolution API."""
    data = payload.get("data", {}) if isinstance(payload, dict) else {}

    if not isinstance(data, dict):
        return {"texto": str(payload), "telefone": "desconhecido", "push_name": "",
                "tem_midia": False, "tem_localizacao": False, "from_me": False,
                "tipo_midia": None, "message_id": None}

    key = data.get("key", {})
    msg = data.get("message", {}) or {}

    remote_jid = key.get("remoteJid", "desconhecido")
    phone = remote_jid.split("@")[0].split(":")[0]
    if not phone.startswith("+"):
        phone = "+" + phone

    texto = ""
    tipo_midia = None
    file_length = None
    mimetype = None

    if "conversation" in msg:
        texto = msg["conversation"]
    elif "extendedTextMessage" in msg:
        texto = msg["extendedTextMessage"].get("text", "")
    elif "imageMessage" in msg:
        texto = msg["imageMessage"].get("caption", "")
        tipo_midia = "imagem"
        file_length = msg["imageMessage"].get("fileLength")
        mimetype = msg["imageMessage"].get("mimetype")
    elif "videoMessage" in msg:
        texto = msg["videoMessage"].get("caption", "")
        tipo_midia = "video"
        file_length = msg["videoMessage"].get("fileLength")
        mimetype = msg["videoMessage"].get("mimetype")
    elif "audioMessage" in msg:
        texto = ""
        tipo_midia = "audio"
        file_length = msg["audioMessage"].get("fileLength")
        mimetype = msg["audioMessage"].get("mimetype")
    elif "documentMessage" in msg:
        texto = msg["documentMessage"].get("caption", "")
        tipo_midia = "documento"
        file_length = msg["documentMessage"].get("fileLength")
        mimetype = msg["documentMessage"].get("mimetype")
    elif "locationMessage" in msg:
        texto = ""
        tipo_midia = "localizacao"

    # Normaliza fileLength pra int (Evolution pode mandar como string)
    if file_length is not None:
        try:
            file_length = int(file_length)
        except (ValueError, TypeError):
            file_length = None

    tem_localizacao = False
    latitude = None
    longitude = None
    if "locationMessage" in msg:
        tem_localizacao = True
        latitude = msg["locationMessage"].get("degreesLatitude")
        longitude = msg["locationMessage"].get("degreesLongitude")

    return {
        "texto": texto,
        "telefone": phone,
        "push_name": data.get("pushName", ""),
        "tem_midia": tipo_midia is not None and tipo_midia != "localizacao",
        "tem_localizacao": tem_localizacao,
        "from_me": key.get("fromMe", False),
        "tipo_midia": tipo_midia,
        "message_id": key.get("id"),
        "latitude": latitude,
        "longitude": longitude,
        "file_length": file_length,
        "mimetype": mimetype,
    }


def _buscar_sessao_ativa(telefone: str) -> dict | None:
    """Busca sessao ativa no Supabase pra esse telefone."""
    try:
        sb = get_supabase()
        result = sb.table("sessoes_conversa").select("*").eq(
            "telefone", telefone
        ).gt("expira_em", datetime.now(timezone.utc).isoformat()).execute()

        if result.data and len(result.data) > 0:
            sessao = result.data[0]
            # Sessao finalizada nao conta
            if sessao.get("etapa") == "finalizado":
                return None
            return sessao
        return None
    except Exception as exc:
        logger.error(f"Erro ao buscar sessao: {exc}")
        return None


@router.post("/unificado", status_code=status.HTTP_202_ACCEPTED)
async def receber_webhook_unificado(
    payload: dict[str, Any],
    request: Request,
    _: str | None = Depends(require_evolution_apikey),
):
    dados = _extrair_dados_evolution(payload)

    if dados["from_me"]:
        return {"status": "ignored", "reason": "from_me"}

    if not dados["texto"] and not dados["tem_midia"] and not dados["tem_localizacao"]:
        return {"status": "ignored", "reason": "empty"}

    telefone = dados["telefone"]
    texto = dados["texto"]
    logger.info(f"Mensagem de {telefone}: {texto[:80] if texto else '[midia/localizacao]'}")

    # ── 1. SOS RAPIDO — prioridade absoluta, sem checar sessao ──
    if texto and detectar_sos_rapido(texto):
        logger.warning(f"🚨 SOS RAPIDO detectado de {telefone}!")
        # Limpa qualquer sessao ativa — SOS sempre ganha
        try:
            sb = get_supabase()
            sb.table("sessoes_conversa").delete().eq("telefone", telefone).execute()
        except Exception:
            pass

        event = _montar_evento(dados, request, classificacao={
            "canal": "sos_mulher",
            "categoria": "emergencia",
            "sentimento": "negativo",
            "urgencia": "alta",
            "resumo": f"SOS emergencia - codigo: {texto}",
            "resposta_whatsapp": "✓ Recebido. Se puder, envie sua localização: 📎 > Localização",
            "pedir_midia": False,
            "pedir_localizacao": True,
        }, is_continuacao=False)
        return _enfileirar(event, "queue:sos")

    # ── 2. CONSULTA DE PROTOCOLO — detecta MGA-XXXX-XXXXX antes da IA ──
    protocolo_match = re.search(r"MGA-\d{4}-\d{4,6}", texto.upper()) if texto else None
    if protocolo_match and not _buscar_sessao_ativa(telefone):
        # Cidadão enviou um protocolo e NÃO tem sessão ativa → é uma consulta
        protocolo_num = protocolo_match.group(0)
        logger.info(f"🔍 Consulta de protocolo detectada: {protocolo_num} de {telefone}")

        event = _montar_evento(dados, request, classificacao={
            "canal": "consulta_protocolo",
            "categoria": "consulta",
            "protocolo_consulta": protocolo_num,
        }, is_continuacao=False)
        return _enfileirar(event, "queue:consultas")

    # ── 3. CHECAR SESSAO ATIVA ──
    sessao = _buscar_sessao_ativa(telefone)

    # ── 3b. SAUDAÇÃO RÁPIDA — só se NÃO tem sessão ativa ──
    # Se tem sessão, a mensagem pode ser resposta a uma pergunta (ex: "ok" = aceitar)
    _SAUDACOES_RAPIDAS = {
        "obrigado", "obrigada", "valeu", "muito obrigado", "muito obrigada",
        "agradeço", "agradeco", "tchau", "até mais", "ate mais",
        "bom dia", "boa tarde", "boa noite",
        "obg", "vlw", "tmj", "brigado", "brigada",
    }
    if not sessao and texto and texto.strip().lower().rstrip("!.?") in _SAUDACOES_RAPIDAS:
        logger.info(f"Saudação rápida detectada de {telefone}: {texto}")
        event = _montar_evento(dados, request, classificacao={
            "canal": "saudacao",
            "categoria": "saudacao",
            "resposta_whatsapp": "",
        }, is_continuacao=False)
        return _enfileirar(event, "queue:saudacoes")

    if sessao:
        # CONTINUACAO — mesmo protocolo, nao classifica de novo
        logger.info(f"Sessao ativa encontrada: canal={sessao['canal']} etapa={sessao['etapa']}")

        canal = sessao["canal"]
        fila_map = {
            "denuncia": "queue:denuncias",
            "sos_mulher": "queue:sos",
            "ocorrencia": "queue:ocorrencias",
            "feedback": "queue:feedbacks",
        }
        fila = fila_map.get(canal, "queue:feedbacks")

        event = _montar_evento(dados, request, classificacao={
            "canal": canal,
            "categoria": (sessao.get("contexto") or {}).get("categoria", ""),
        }, is_continuacao=True, sessao=sessao)
        return _enfileirar(event, fila)

    # ── 4. MENSAGEM NOVA — classificar com IA ──
    classificacao = await classificar_mensagem(
        texto=texto or "[Mídia sem legenda]",
        telefone=telefone,
        tem_midia=dados["tem_midia"],
        tem_localizacao=dados["tem_localizacao"],
        push_name=dados["push_name"],
    )

    canal = classificacao.get("canal", "feedback")

    # ── 4b. SAUDAÇÃO — responde sem criar protocolo ──
    if canal == "saudacao":
        resposta = classificacao.get("resposta_whatsapp", "")
        if not resposta:
            push = dados["push_name"]
            resposta = (f"Olá{', ' + push if push else ''}! 👋\n"
                        f"Sou a Clara, assistente da Prefeitura de Maringá.\n\n"
                        f"Como posso ajudar?\n"
                        f"📢 Denúncia\n📍 Ocorrência urbana\n💬 Feedback\n🆘 SOS Mulher")
        # Enfileira como saudacao pra responder sem criar registro
        event = _montar_evento(dados, request, classificacao=classificacao, is_continuacao=False)
        return _enfileirar(event, "queue:saudacoes")

    fila_map = {
        "denuncia": "queue:denuncias",
        "sos_mulher": "queue:sos",
        "ocorrencia": "queue:ocorrencias",
        "feedback": "queue:feedbacks",
    }
    fila = fila_map.get(canal, "queue:feedbacks")

    event = _montar_evento(dados, request, classificacao=classificacao, is_continuacao=False)
    return _enfileirar(event, fila)


def _montar_evento(dados: dict, request: Request, classificacao: dict,
                   is_continuacao: bool, sessao: dict = None) -> dict:
    """Monta o evento padrao pra colocar na fila."""
    return {
        "channel": classificacao.get("canal", "feedback"),
        "instance_name": settings.wa_instance_name,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "client_ip": request.client.host if request.client else None,
        "telefone": dados["telefone"],
        "push_name": dados["push_name"],
        "texto": dados["texto"],
        "tem_midia": dados["tem_midia"],
        "tipo_midia": dados["tipo_midia"],
        "tem_localizacao": dados["tem_localizacao"],
        "latitude": dados.get("latitude"),
        "longitude": dados.get("longitude"),
        "message_id": dados.get("message_id"),
        "file_length": dados.get("file_length"),
        "mimetype": dados.get("mimetype"),
        "classificacao": classificacao,
        "is_continuacao": is_continuacao,
        "sessao": sessao,
    }


def _enfileirar(event: dict, fila: str) -> dict:
    """Coloca o evento na fila Redis."""
    try:
        queue_depth = enqueue_webhook(fila, event)
    except QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    canal = event.get("channel", "?")
    cont = "CONTINUACAO" if event.get("is_continuacao") else "NOVO"
    logger.info(f"[{cont}] canal={canal} fila={fila} depth={queue_depth}")

    return {
        "status": "accepted",
        "canal": canal,
        "is_continuacao": event.get("is_continuacao", False),
        "queue": fila,
        "queue_depth": queue_depth,
    }
