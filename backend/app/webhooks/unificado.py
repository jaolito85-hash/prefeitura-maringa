"""
unificado.py — Webhook UNIFICADO para demo com numero unico.
=============================================================
Um unico endpoint recebe TODAS as mensagens do WhatsApp.
A IA do Claude classifica e roteia pro canal correto.

Fluxo:
  WhatsApp → Evolution API → /webhook/unificado → Redis fila → Worker processa

COMO FUNCIONA:
  1. Mensagem chega neste webhook
  2. Extrai texto, midia, localizacao do payload da Evolution
  3. Checa se e SOS rapido (< 2 segundos, sem IA)
  4. Se nao e SOS, chama Claude API pra classificar
  5. Coloca na fila Redis com a classificacao ja feita
  6. Worker consome, salva no Supabase, responde via Evolution
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.config import settings
from app.services.classificador import classificar_mensagem, detectar_sos_rapido
from app.services.webhook_queue import enqueue_webhook, QueueUnavailableError
from app.webhooks.common import require_evolution_apikey

logger = logging.getLogger("webhook.unificado")

router = APIRouter()


def _extrair_dados_evolution(payload: dict) -> dict[str, Any]:
    """
    Extrai os dados relevantes do payload da Evolution API.
    O payload da Evolution vem num formato especifico — essa funcao
    'traduz' pra um formato mais limpo que o resto do sistema usa.
    """
    data = payload.get("data", {}) if isinstance(payload, dict) else {}

    if not isinstance(data, dict):
        return {"texto": str(payload), "telefone": "desconhecido", "push_name": "",
                "tem_midia": False, "tem_localizacao": False, "from_me": False,
                "tipo_midia": None, "message_id": None}

    key = data.get("key", {})
    msg = data.get("message", {}) or {}

    # Extrair telefone
    remote_jid = key.get("remoteJid", "desconhecido")
    phone = remote_jid.split("@")[0].split(":")[0]
    if not phone.startswith("+"):
        phone = "+" + phone

    # Extrair texto
    texto = ""
    tipo_midia = None

    if "conversation" in msg:
        texto = msg["conversation"]
    elif "extendedTextMessage" in msg:
        texto = msg["extendedTextMessage"].get("text", "")
    elif "imageMessage" in msg:
        texto = msg["imageMessage"].get("caption", "")
        tipo_midia = "imagem"
    elif "videoMessage" in msg:
        texto = msg["videoMessage"].get("caption", "")
        tipo_midia = "video"
    elif "audioMessage" in msg:
        texto = ""
        tipo_midia = "audio"
    elif "documentMessage" in msg:
        texto = msg["documentMessage"].get("caption", "")
        tipo_midia = "documento"
    elif "locationMessage" in msg:
        texto = ""
        tipo_midia = "localizacao"

    # Extrair localizacao (pode vir como locationMessage)
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
    }


@router.post("/unificado", status_code=status.HTTP_202_ACCEPTED)
async def receber_webhook_unificado(
    payload: dict[str, Any],
    request: Request,
    _: str | None = Depends(require_evolution_apikey),
):
    """
    Endpoint UNICO que recebe todas as mensagens do WhatsApp.
    Classifica com IA e roteia pro canal correto.
    """
    # 1. Extrair dados do payload da Evolution
    dados = _extrair_dados_evolution(payload)

    # Ignorar mensagens enviadas pelo proprio bot
    if dados["from_me"]:
        return {"status": "ignored", "reason": "from_me"}

    # Ignorar mensagens vazias (sem texto e sem midia)
    if not dados["texto"] and not dados["tem_midia"] and not dados["tem_localizacao"]:
        return {"status": "ignored", "reason": "empty"}

    telefone = dados["telefone"]
    texto = dados["texto"]
    logger.info(f"Mensagem de {telefone}: {texto[:80]}")

    # 2. Checagem RAPIDA de SOS (< 2 segundos, sem chamar IA)
    if texto and detectar_sos_rapido(texto):
        logger.warning(f"🚨 SOS RAPIDO detectado de {telefone}!")
        classificacao = {
            "canal": "sos_mulher",
            "categoria": "emergencia",
            "sentimento": "negativo",
            "urgencia": "alta",
            "resumo": f"SOS emergencia - codigo: {texto}",
            "resposta_whatsapp": "✓ Recebido. Se puder, envie sua localização: 📎 > Localização",
            "pedir_midia": False,
            "pedir_localizacao": True,
        }
    else:
        # 3. Classificacao com Claude API (2-5 segundos)
        classificacao = await classificar_mensagem(
            texto=texto or "[Mídia sem legenda]",
            telefone=telefone,
            tem_midia=dados["tem_midia"],
            tem_localizacao=dados["tem_localizacao"],
            push_name=dados["push_name"],
        )

    # 4. Determinar a fila correta
    canal = classificacao.get("canal", "feedback")
    fila_map = {
        "denuncia": "queue:denuncias",
        "sos_mulher": "queue:sos",
        "ocorrencia": "queue:ocorrencias",
        "feedback": "queue:feedbacks",
    }
    fila = fila_map.get(canal, "queue:feedbacks")

    # 5. Montar evento enriquecido (com classificacao) e colocar na fila
    event = {
        "channel": canal,
        "instance_name": settings.wa_instance_name,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "client_ip": request.client.host if request.client else None,
        "path": str(request.url.path),
        "telefone": telefone,
        "push_name": dados["push_name"],
        "texto": texto,
        "tem_midia": dados["tem_midia"],
        "tipo_midia": dados["tipo_midia"],
        "tem_localizacao": dados["tem_localizacao"],
        "latitude": dados.get("latitude"),
        "longitude": dados.get("longitude"),
        "message_id": dados.get("message_id"),
        "classificacao": classificacao,
        "payload_original": payload,
    }

    try:
        queue_depth = enqueue_webhook(fila, event)
    except QueueUnavailableError as exc:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    logger.info(
        f"Classificado: canal={canal} categoria={classificacao.get('categoria')} "
        f"fila={fila} depth={queue_depth}"
    )

    return {
        "status": "accepted",
        "canal": canal,
        "categoria": classificacao.get("categoria"),
        "queue": fila,
        "queue_depth": queue_depth,
    }
