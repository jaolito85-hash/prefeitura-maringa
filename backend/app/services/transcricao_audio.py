"""
transcricao_audio.py — Transcrição de áudio via OpenAI Whisper
==============================================================
Recebe bytes de áudio do WhatsApp (opus/ogg) e retorna texto transcrito.
Limite: 30 segundos de áudio.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("transcricao_audio")

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_MODEL = "whisper-1"
MAX_AUDIO_SECONDS = 30

# Mapeamento de mimetype do WhatsApp para extensão de arquivo
# Whisper precisa da extensão correta pra processar
AUDIO_EXT_MAP = {
    "audio/ogg; codecs=opus": ".ogg",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
}


def _obter_audio_bytes(media_base64: str, message_id: str) -> bytes | None:
    """
    Obtém bytes do áudio: primeiro tenta base64 do webhook,
    depois fallback pra Evolution API.
    """
    # 1. Base64 do webhook (mais rápido)
    if media_base64:
        try:
            b64 = media_base64
            if ";base64," in b64:
                b64 = b64.split(";base64,")[1]
            resultado = base64.b64decode(b64)
            if len(resultado) > 0:
                logger.info(f"Áudio obtido do webhook base64 ({len(resultado)} bytes)")
                return resultado
        except Exception as exc:
            logger.warning(f"Falha ao decodificar base64 do áudio: {exc}")

    # 2. Fallback: Evolution API
    evolution_url = settings.evolution_api_url
    evolution_key = settings.evolution_api_key
    wa_instance = settings.wa_instance_name

    if not evolution_url or not evolution_key or not message_id:
        return None

    url = f"{evolution_url}/chat/getBase64FromMediaMessage/{wa_instance}"
    try:
        logger.info(f"Baixando áudio via Evolution API: {message_id}")
        response = httpx.post(
            url,
            json={"message": {"key": {"id": message_id}}, "convertToMp4": False},
            headers={"Content-Type": "application/json", "apikey": evolution_key},
            timeout=30.0,
        )
        if response.status_code in (200, 201):
            data = response.json()
            b64 = data.get("base64", "")
            if b64:
                if ";base64," in b64:
                    b64 = b64.split(";base64,")[1]
                return base64.b64decode(b64)
        logger.error(f"Download áudio falhou: {response.status_code}")
    except Exception as exc:
        logger.error(f"Erro download áudio: {exc}")

    return None


async def transcrever_audio(
    media_base64: str,
    message_id: str,
    mimetype: str | None = None,
) -> dict[str, Any]:
    """
    Transcreve áudio via OpenAI Whisper API.

    Retorna dict:
      - sucesso: {"ok": True, "texto": "texto transcrito"}
      - erro:    {"ok": False, "erro": "mensagem de erro para o cidadão"}
    """
    # 1. Obter bytes do áudio
    audio_bytes = _obter_audio_bytes(media_base64, message_id)
    if not audio_bytes:
        logger.error("Não foi possível obter bytes do áudio")
        return {
            "ok": False,
            "erro": "⚠️ Não consegui receber seu áudio. Tente enviar novamente ou digite sua mensagem por texto.",
        }

    # 2. Determinar extensão do arquivo
    ext = AUDIO_EXT_MAP.get(mimetype, ".ogg")
    filename = f"audio{ext}"

    logger.info(f"Transcrevendo áudio: {len(audio_bytes)} bytes, mime={mimetype}, ext={ext}")

    # 3. Chamar Whisper API
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                WHISPER_URL,
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": (filename, io.BytesIO(audio_bytes), mimetype or "audio/ogg")},
                data={
                    "model": WHISPER_MODEL,
                    "language": "pt",
                    "response_format": "json",
                },
            )
            response.raise_for_status()

        resultado = response.json()
        texto = (resultado.get("text") or "").strip()

        if not texto:
            logger.warning("Whisper retornou texto vazio")
            return {
                "ok": False,
                "erro": "🎙️ Não consegui entender o áudio. Pode repetir ou digitar sua mensagem por texto?",
            }

        logger.info(f"Transcrição OK: '{texto[:80]}...' ({len(texto)} chars)")
        return {"ok": True, "texto": texto}

    except httpx.TimeoutException:
        logger.error("Timeout ao chamar Whisper API")
        return {
            "ok": False,
            "erro": "⚠️ O áudio demorou muito para processar. Tente enviar um áudio mais curto ou digite por texto.",
        }
    except httpx.HTTPStatusError as exc:
        logger.error(f"Erro HTTP do Whisper: {exc.response.status_code} - {exc.response.text[:300]}")
        return {
            "ok": False,
            "erro": "⚠️ Erro ao processar seu áudio. Por favor, tente novamente ou envie sua mensagem por texto.",
        }
    except Exception as exc:
        logger.exception(f"Erro inesperado na transcrição: {exc}")
        return {
            "ok": False,
            "erro": "⚠️ Erro ao processar seu áudio. Tente digitar sua mensagem por texto.",
        }
