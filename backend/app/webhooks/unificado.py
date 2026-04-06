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
from app.services.classificador import classificar_mensagem, classificar_imagem, classificar_imagem_arborizacao, detectar_sos_rapido
from app.services.transcricao_audio import transcrever_audio, MAX_AUDIO_SECONDS
from app.services.rate_limiter import (
    checar_limite_consulta_protocolo,
    checar_limite_diario,
    truncar_mensagem,
)
from app.services.supabase_client import get_supabase
from app.services.webhook_queue import enqueue_webhook, QueueUnavailableError
import redis as redis_lib

# ── MODERAÇÃO DE LINGUAGEM ──────────────────────────────────────────
# Palavras proibidas (sem duplo sentido — apenas xingamentos claros)
_PALAVRAS_PROIBIDAS = {
    # Xingamentos diretos
    "puta", "puto", "putaria", "putinha", "putão", "putao",
    "caralho", "cacete", "pau no cu", "porra", "merda",
    "filho da puta", "filha da puta", "fdp", "fdp",
    "cuzão", "cuzao", "cu ", " cu,", " cu.", " cu!",
    "arrombado", "arrombada",
    "vagabundo", "vagabunda",
    "viado", "viada", "veado", "viadinho",
    "desgraçado", "desgraçada", "desgraca",
    "corno", "corna", "cornudo",
    "otário", "otaria", "otario",
    "imbecil", "idiota", "retardado", "retardada",
    "babaca", "bosta", "buceta", "boceta",
    "piranha", "prostituta", "quenga",
    "vá se fuder", "vai se fuder", "vai tomar no cu",
    "foda-se", "foda se", "fodase", "se foda", "se fuder",
    "cabaço", "cabaco",
    "punheta", "punheteiro",
    "pau no seu cu", "enfia no cu",
    "lixo humano", "seu lixo",
    "cretino", "cretina",
    "safado", "safada",
    "maldito", "maldita",
    "nojento", "nojenta",
    "inútil", "inutil",
}

def _contem_palavrao(texto: str) -> bool:
    """Verifica se o texto contém palavras proibidas."""
    if not texto:
        return False
    t = texto.lower()
    # Normalizar acentos
    import unicodedata
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # Adicionar espaços para match de bordas
    t = f" {t} "
    for palavra in _PALAVRAS_PROIBIDAS:
        p = unicodedata.normalize("NFKD", palavra)
        p = "".join(c for c in p if not unicodedata.combining(c))
        if p in t:
            return True
    return False

_REDIS_URL = settings.redis_url if hasattr(settings, 'redis_url') else "redis://redis:6379"

def _checar_moderacao(telefone: str, texto: str) -> dict | None:
    """Verifica linguagem e aplica sistema de 3 strikes.
    Retorna None se OK, ou dict com resposta de moderação."""
    if not _contem_palavrao(texto):
        return None
    try:
        r = redis_lib.Redis.from_url(_REDIS_URL, decode_responses=True, socket_timeout=2)
        # Verificar ban ativo
        ban_key = f"ban:{telefone}"
        if r.exists(ban_key):
            ttl = r.ttl(ban_key)
            horas = max(1, ttl // 3600)
            return {"blocked": True, "msg": f"🚫 Seu acesso está suspenso por uso de linguagem inadequada.\n\nTempo restante: ~{horas}h.\nRespeite para poder utilizar o serviço."}
        # Incrementar strikes
        strike_key = f"strikes:{telefone}"
        strikes = r.incr(strike_key)
        r.expire(strike_key, 86400 * 7)  # Strikes expiram em 7 dias
        if strikes == 1:
            return {"blocked": False, "msg": "⚠️ *Atenção:* Linguagem inadequada detectada.\n\nEste é um canal oficial da Prefeitura de Maringá. Por favor, mantenha o respeito nas mensagens.\n\n_Este é o seu 1º aviso._"}
        elif strikes == 2:
            return {"blocked": False, "msg": "🚨 *Último aviso:* Linguagem inadequada detectada novamente.\n\nNa próxima ocorrência, seu acesso será *suspenso por 72 horas*.\n\n_Este é o seu 2º e último aviso._"}
        else:
            # Strike 3+ → ban de 72 horas
            r.setex(ban_key, 86400 * 3, "banned")  # 72h
            r.delete(strike_key)
            return {"blocked": True, "msg": "🚫 *Acesso suspenso por 72 horas* devido ao uso repetido de linguagem inadequada.\n\nEste é um serviço público. Respeite para poder utilizar."}
    except Exception as exc:
        logger.error(f"Erro moderação: {exc}")
        return None
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
    # Normalizar celular BR: 55 + DDD(2) + 9 + numero(8) = 13 digitos
    # WhatsApp/Evolution API as vezes armazena sem o 9 (formato antigo)
    if phone.startswith("55") and len(phone) == 12:
        ddd = phone[2:4]
        phone = f"55{ddd}9{phone[4:]}"
    if not phone.startswith("+"):
        phone = "+" + phone

    texto = ""
    tipo_midia = None
    file_length = None
    mimetype = None
    audio_duration = None

    if "conversation" in msg:
        texto = msg["conversation"]
    elif "extendedTextMessage" in msg:
        texto = msg["extendedTextMessage"].get("text", "")
    elif "imageMessage" in msg:
        # ── DEBUG: log completo do payload de imagem ──
        # Copia msg sem base64 pra não poluir o log (base64 pode ter megabytes)
        msg_debug = {k: v for k, v in msg.items() if k != "base64"}
        if "imageMessage" in msg_debug and "jpegThumbnail" in (msg_debug["imageMessage"] or {}):
            msg_debug["imageMessage"] = {k: v for k, v in msg_debug["imageMessage"].items() if k != "jpegThumbnail"}
            msg_debug["imageMessage"]["jpegThumbnail"] = "[OMITIDO]"
        logger.info(f"=== PAYLOAD IMAGEM COMPLETO ===\n{json.dumps(msg_debug, indent=2, default=str)}")
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
        audio_duration = msg["audioMessage"].get("seconds")
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

    # ── Extrair metadados de origem da foto (red flag) ──
    # Evolution API pode colocar messageContextInfo dentro de imageMessage ou no nível msg
    msg_context = msg.get("messageContextInfo", {}) or {}
    is_forwarded = msg_context.get("isForwarded", False)
    forwarding_score = msg_context.get("forwardingScore", 0) or 0
    media_key_timestamp = None

    if "imageMessage" in msg:
        img = msg["imageMessage"]
        media_key_timestamp = img.get("mediaKeyTimestamp")
        # Fallback: isForwarded/forwardingScore podem vir dentro de imageMessage.contextInfo
        img_ctx = img.get("contextInfo", {}) or {}
        if not is_forwarded:
            is_forwarded = img_ctx.get("isForwarded", False)
        if not forwarding_score:
            forwarding_score = img_ctx.get("forwardingScore", 0) or 0
        # Log completo para debug de red flag
        logger.info(f"📷 imageMessage metadata: mediaKeyTimestamp={media_key_timestamp}, "
                    f"isForwarded={is_forwarded}, forwardingScore={forwarding_score}, "
                    f"contextInfo keys={list(img_ctx.keys())}, "
                    f"msgContextInfo keys={list(msg_context.keys())}")
    elif "videoMessage" in msg:
        vid = msg["videoMessage"]
        media_key_timestamp = vid.get("mediaKeyTimestamp")
        vid_ctx = vid.get("contextInfo", {}) or {}
        if not is_forwarded:
            is_forwarded = vid_ctx.get("isForwarded", False)
        if not forwarding_score:
            forwarding_score = vid_ctx.get("forwardingScore", 0) or 0

    if media_key_timestamp is not None:
        try:
            media_key_timestamp = int(media_key_timestamp)
        except (ValueError, TypeError):
            media_key_timestamp = None

    tem_localizacao = False
    latitude = None
    longitude = None
    if "locationMessage" in msg:
        tem_localizacao = True
        latitude = msg["locationMessage"].get("degreesLatitude")
        longitude = msg["locationMessage"].get("degreesLongitude")

    # ── Extrair base64 da mídia (quando Webhook Base64 está ON na Evolution) ──
    # A Evolution manda o base64 direto no payload — não precisa de segunda chamada
    media_base64 = msg.get("base64", "") or ""

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
        "media_base64": media_base64,
        "is_forwarded": is_forwarded,
        "forwarding_score": forwarding_score,
        "media_key_timestamp": media_key_timestamp,
        "audio_duration": audio_duration,
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
            # Handoff ativo SEMPRE retorna sessão (mesmo se "finalizado")
            if sessao.get("handoff_ativo"):
                return sessao
            # Sessao finalizada sem handoff nao conta
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
    # ── FILTRAR TIPO DE EVENTO ──
    # Evolution API manda varios tipos: messages.upsert (mensagem real),
    # messages.update (status leitura), etc. So queremos mensagens reais.
    event_type = payload.get("event", "") if isinstance(payload, dict) else ""
    if event_type and event_type not in ("messages.upsert", "send.message"):
        logger.debug(f"Evento ignorado: {event_type}")
        return {"status": "ignored", "reason": f"event_type:{event_type}"}

    dados = _extrair_dados_evolution(payload)

    if dados["from_me"]:
        return {"status": "ignored", "reason": "from_me"}

    if not dados["texto"] and not dados["tem_midia"] and not dados["tem_localizacao"]:
        return {"status": "ignored", "reason": "empty"}

    telefone = dados["telefone"]
    texto = dados["texto"]

    # ── DETECÇÃO SOS RÁPIDA (ANTES de moderação — emergência NUNCA é bloqueada) ──
    _SOS_CODES = {".", "socorro", "me ajuda", "ajuda", "femi", "sos"}
    _texto_sos = (texto or "").strip().lower()
    _is_sos = _texto_sos in _SOS_CODES or any(c in _texto_sos for c in ["socorro", "me ajuda", "femi"])
    # Se é SOS, pula moderação completamente
    if not _is_sos:
        # ── MODERAÇÃO DE LINGUAGEM ──
        moderacao = _checar_moderacao(telefone, texto)
        if moderacao:
            logger.warning(f"🚫 Moderação: {telefone} — blocked={moderacao.get('blocked')}")
            event = _montar_evento(dados, request, classificacao={
                "canal": "saudacao",
                "categoria": "moderacao",
                "resposta_whatsapp": moderacao["msg"],
            }, is_continuacao=False)
            return _enfileirar(event, "queue:saudacoes")

    # ── TRANSCRIÇÃO DE ÁUDIO (Whisper) ──
    # Se o cidadão mandou áudio, transcreve antes de tudo.
    # O texto transcrito entra no fluxo normal (classificação, sessão, etc.)
    if dados["tipo_midia"] == "audio":
        duration = dados.get("audio_duration")
        # Checar duração (máx 30s)
        if duration is not None and int(duration) > MAX_AUDIO_SECONDS:
            logger.info(f"🎙️ Áudio longo demais de {telefone}: {duration}s (max {MAX_AUDIO_SECONDS}s)")
            event = _montar_evento(dados, request, classificacao={
                "canal": "saudacao",
                "categoria": "audio_longo",
                "resposta_whatsapp": (
                    f"🎙️ Seu áudio tem mais de {MAX_AUDIO_SECONDS} segundos.\n\n"
                    f"Por favor, envie um áudio de *no máximo {MAX_AUDIO_SECONDS} segundos* "
                    f"para que eu consiga processar.\n\n"
                    f"Ou se preferir, *digite sua mensagem* por texto."
                ),
            }, is_continuacao=False)
            return _enfileirar(event, "queue:saudacoes")

        # Transcrever
        logger.info(f"🎙️ Transcrevendo áudio de {telefone} ({duration or '?'}s)...")
        resultado = await transcrever_audio(
            media_base64=dados.get("media_base64", ""),
            message_id=dados.get("message_id", ""),
            mimetype=dados.get("mimetype"),
        )

        if resultado["ok"]:
            texto = resultado["texto"]
            dados["texto"] = texto
            dados["texto_original_audio"] = True  # Flag: veio de transcrição
            dados["tipo_midia"] = None             # Não é mais mídia visual
            dados["tem_midia"] = False              # Áudio já foi processado
            logger.info(f"🎙️ Transcrição OK de {telefone}: '{texto[:80]}'")
        else:
            # Falha na transcrição — responde com erro
            event = _montar_evento(dados, request, classificacao={
                "canal": "saudacao",
                "categoria": "audio_erro",
                "resposta_whatsapp": resultado["erro"],
            }, is_continuacao=False)
            return _enfileirar(event, "queue:saudacoes")

    # ── PROTEÇÃO 1: TRUNCAR MENSAGENS LONGAS (600 chars) ──
    # Protege contra spam e economiza tokens da IA
    if texto:
        texto, foi_truncado = truncar_mensagem(texto)
        if foi_truncado:
            logger.info(f"Mensagem truncada de {telefone}: {len(dados['texto'])} → {len(texto)} chars")
            dados["texto"] = texto  # Atualiza pra propagar o texto truncado
            dados["texto_truncado"] = True  # Flag pra avisar o cidadão depois

    logger.info(f"Mensagem de {telefone}: {texto[:80] if texto else '[midia/localizacao]'}")

    # ── 1. CHECAR SESSAO ATIVA (ANTES de tudo) ──
    # Se tem sessao, mensagens curtas como "1", "3", "." sao respostas,
    # NAO codigos SOS. Isso evita falso-positivo de SOS durante conversa.
    sessao = _buscar_sessao_ativa(telefone)

    # ── 1b. HANDOFF ATIVO — operador controla a conversa, bot desligado ──
    # Mensagem NÃO é processada pelo bot, mas É SALVA no histórico pra o operador ver
    if sessao and sessao.get("handoff_ativo"):
        logger.info(f"🤝 Handoff ativo para {telefone} — salvando msg, bot desligado")
        canal = sessao.get("canal", "")
        registro_id = sessao.get("registro_id", "")
        push_name = dados["push_name"]
        msg_texto = texto or "[Mídia]"
        if dados["tem_localizacao"]:
            msg_texto = f"📍 Localização: {dados.get('latitude')}, {dados.get('longitude')}"

        try:
            sb = get_supabase()
            if canal == "sos_mulher" and registro_id:
                sb.table("sos_mensagens").insert({
                    "alerta_id": registro_id,
                    "telefone": telefone,
                    "nome": push_name or None,
                    "mensagem": msg_texto,
                    "remetente": "cidadao",
                }).execute()
            elif canal == "ocorrencia" and registro_id:
                sb.table("ocorrencias_relatos").insert({
                    "ocorrencia_id": registro_id,
                    "telefone": telefone,
                    "nome": push_name or None,
                    "mensagem": msg_texto,
                }).execute()
            elif canal == "feedback" and registro_id:
                # Verificar se o feedback existe (pode ser placeholder)
                check = sb.table("feedbacks").select("id").eq("id", registro_id).limit(1).execute()
                if check.data:
                    sb.table("feedbacks_mensagens").insert({
                        "feedback_id": registro_id,
                        "telefone": telefone,
                        "nome": push_name or None,
                        "mensagem": msg_texto,
                        "remetente": "cidadao",
                    }).execute()
        except Exception as exc:
            logger.error(f"Erro ao salvar msg durante handoff: {exc}")

        return {"status": "saved_handoff", "reason": "handoff_active"}

    # ── 2. SOS RAPIDO — so se NAO tem sessao ativa ──
    # ⚠️ SOS é ANTES do rate limit — vida em risco NUNCA é bloqueada
    if not sessao and texto and detectar_sos_rapido(texto):
        logger.warning(f"🚨 SOS RAPIDO detectado de {telefone}!")
        # Limpa qualquer sessao expirada residual
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

    # ── PROTEÇÃO 2: LIMITE DIÁRIO (30 msgs/dia) ──
    # Colocado DEPOIS do SOS — emergência nunca é bloqueada
    limite_dia = checar_limite_diario(telefone)
    if not limite_dia.allowed:
        horas = limite_dia.retry_after // 3600
        logger.warning(f"🚫 Limite diário: {telefone} bloqueado ({limite_dia.current}/{limite_dia.limit})")
        # Não enfileira, não processa — só retorna 202 (não revelar pro spammer)
        return {
            "status": "rate_limited",
            "reason": "daily_limit",
            "retry_after_hours": max(horas, 1),
        }

    # ── 3. CONSULTA DE PROTOCOLO — detecta MGA-XXXX-XXXXX antes da IA ──
    protocolo_match = re.search(r"(MGA|ARB)-\d{4}-[A-Z0-9]{4,8}", texto.upper()) if texto else None
    if protocolo_match and not sessao:
        protocolo_num = protocolo_match.group(0)
        logger.info(f"🔍 Consulta de protocolo detectada: {protocolo_num} de {telefone}")

        # ── PROTEÇÃO 3: LIMITE DE CONSULTAS (3/hora) ──
        # Evita brute-force de protocolos alheios
        limite_consulta = checar_limite_consulta_protocolo(telefone)
        if not limite_consulta.allowed:
            minutos = limite_consulta.retry_after // 60
            logger.warning(f"🚫 Limite consulta protocolo: {telefone} ({limite_consulta.current}/{limite_consulta.limit})")
            # Enfileira como consulta bloqueada — worker envia msg educada
            event = _montar_evento(dados, request, classificacao={
                "canal": "consulta_protocolo",
                "categoria": "consulta_bloqueada",
                "protocolo_consulta": protocolo_num,
                "rate_limited": True,
                "retry_after_minutos": max(minutos, 1),
            }, is_continuacao=False)
            return _enfileirar(event, "queue:consultas")

        event = _montar_evento(dados, request, classificacao={
            "canal": "consulta_protocolo",
            "categoria": "consulta",
            "protocolo_consulta": protocolo_num,
            "telefone_solicitante": telefone,  # PROTEÇÃO 4: pra validar privacidade no worker
        }, is_continuacao=False)
        return _enfileirar(event, "queue:consultas")

    # ── 3b. INTENÇÃO DE CONSULTA — palavras-chave sem protocolo ──
    _PALAVRAS_CONSULTA = {
        "protocolo", "consultar", "consulta", "status",
        "meu caso", "minha denúncia", "minha denuncia",
        "minha ocorrência", "minha ocorrencia",
        "acompanhar", "como está", "como esta", "como tá", "como ta",
        "resultado", "andamento", "verificar",
    }
    if not sessao and texto and not protocolo_match:
        texto_lower = texto.strip().lower()
        detectou_consulta = any(p in texto_lower for p in _PALAVRAS_CONSULTA)
        if detectou_consulta:
            logger.info(f"🔍 Intenção de consulta detectada de {telefone}: {texto[:60]}")
            event = _montar_evento(dados, request, classificacao={
                "canal": "consulta_protocolo",
                "categoria": "intencao_consulta",
            }, is_continuacao=False)
            return _enfileirar(event, "queue:consultas")

    # ── 4. SAUDAÇÃO RÁPIDA — só se NÃO tem sessão ativa ──
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

    # ── 5. SESSAO ATIVA — continuacao da conversa ──
    if sessao:
        # CONTINUACAO — mesmo protocolo, nao classifica de novo
        logger.info(f"Sessao ativa encontrada: canal={sessao['canal']} etapa={sessao['etapa']}")

        canal = sessao["canal"]
        fila_map = {
            "denuncia": "queue:denuncias",
            "sos_mulher": "queue:sos",
            "ocorrencia": "queue:ocorrencias",
            "arborizacao": "queue:arborizacao",
            "arborizacao_empresa": "queue:arborizacao",
            "feedback": "queue:feedbacks",
            "consulta_protocolo": "queue:consultas",
        }
        fila = fila_map.get(canal, "queue:feedbacks")

        event = _montar_evento(dados, request, classificacao={
            "canal": canal,
            "categoria": (sessao.get("contexto") or {}).get("categoria", ""),
        }, is_continuacao=True, sessao=sessao)
        return _enfileirar(event, fila)

    # ── 5b. EMPRESA DE ARBORIZAÇÃO sem sessão ativa? ──
    # Se o telefone pertence a uma empresa cadastrada E tem OS ativa → rotear direto
    try:
        sb_check = get_supabase()
        _tel_limpo = telefone.lstrip("+")
        empresa_cfg = sb_check.table("arborizacao_config").select("valor").eq("tipo", "empresa").execute()
        _empresa_match = None
        for ec in (empresa_cfg.data or []):
            if ec["valor"].get("telefone", "").lstrip("+") == _tel_limpo:
                _empresa_match = ec["valor"]
                break
        if _empresa_match:
            # Buscar OS ativa atribuída a esta empresa
            arb_ativo = sb_check.table("arborizacao").select("id, protocolo, status").eq(
                "empresa_telefone", _empresa_match["telefone"]
            ).in_("status", ["atribuido", "em_execucao"]).order("created_at", desc=True).limit(1).execute()
            if arb_ativo.data:
                arb = arb_ativo.data[0]
                logger.info(f"📱 Empresa reconhecida sem sessão: {_empresa_match['nome']} → {arb['protocolo']}")
                # Recriar sessão e rotear
                sessao_empresa = {
                    "canal": "arborizacao_empresa",
                    "etapa": "em_execucao",
                    "registro_id": arb["id"],
                    "contexto": {"protocolo": arb["protocolo"], "arb_id": arb["id"], "empresa_nome": _empresa_match["nome"]},
                }
                event = _montar_evento(dados, request, classificacao={
                    "canal": "arborizacao_empresa",
                    "categoria": "",
                }, is_continuacao=True, sessao=sessao_empresa)
                return _enfileirar(event, "queue:arborizacao")
    except Exception as exc:
        logger.error(f"Erro check empresa arborização: {exc}")

    # ── 6. MENSAGEM NOVA — classificar com IA ──

    # ── 6a. Se tem IMAGEM → classificar por visão (NOVO) ──
    if dados["tem_midia"] and dados["tipo_midia"] == "imagem" and dados.get("media_base64"):
        # Montar data URI a partir do base64 do webhook
        _mime = dados.get("mimetype", "image/jpeg") or "image/jpeg"
        _b64 = dados["media_base64"]
        if not _b64.startswith("data:"):
            image_url = f"data:{_mime};base64,{_b64}"
        else:
            image_url = _b64

        # Detectar palavras-chave de árvore no texto/caption
        _PALAVRAS_ARVORE = {"arvore", "árvore", "poda", "galho", "tronco", "toco", "raiz", "raízes", "copa", "caiu árvore", "arvore caiu"}
        _texto_lower = (texto or "").lower()
        _e_arvore = any(p in _texto_lower for p in _PALAVRAS_ARVORE)

        if _e_arvore:
            classificacao = await classificar_imagem_arborizacao(
                image_url=image_url,
                texto_acompanhante=texto or "",
                telefone=telefone,
            )
        else:
            classificacao = await classificar_imagem(
                image_url=image_url,
                texto_acompanhante=texto or "",
                telefone=telefone,
            )

        # Se moderação bloqueou a imagem
        if classificacao.get("bloqueado"):
            event = _montar_evento(dados, request, classificacao={
                "canal": "saudacao",
                "categoria": "imagem_bloqueada",
                "resposta_whatsapp": (
                    "Não consegui processar essa imagem. "
                    "Por favor, envie uma foto da ocorrência que deseja reportar."
                ),
            }, is_continuacao=False)
            return _enfileirar(event, "queue:saudacoes")

        # Marca confiança baixa pra worker mostrar menu
        if classificacao.get("confianca", 0) < 70:
            classificacao["mostrar_menu"] = True

    # ── 6b. Se NÃO tem imagem → classificar por texto (FLUXO ATUAL) ──
    else:
        classificacao = await classificar_mensagem(
            texto=texto or "[Mídia sem legenda]",
            telefone=telefone,
            tem_midia=dados["tem_midia"],
            tem_localizacao=dados["tem_localizacao"],
            push_name=dados["push_name"],
        )

    canal = classificacao.get("canal", "feedback")

    # ── SAFETY NET: diferenciar árvore emergência vs serviço ──
    _WEATHER_WORDS = {"temporal", "chuva", "vendaval", "tempestade", "enchente", "alagamento", "inundação", "inundacao", "tormenta", "ciclone", "granizo"}
    _SERVICE_WORDS = {"poda", "podar", "cortar", "cupim", "raiz", "raízes", "toco", "morta", "seca", "galho seco", "fiação", "fiacao", "iluminação", "calçada", "calcada"}
    _texto_lower = (texto or "").lower()
    _categoria = classificacao.get("categoria", "")

    # Se IA classificou como arvore em qualquer canal
    _is_arvore = (_categoria in ("queda_arvore", "arvore_caida", "risco_queda", "poda_geral", "poda_complexa", "poda_desbarra", "remocao", "retirada_toco") or
                  canal == "arborizacao")

    if _is_arvore:
        _tem_weather = any(w in _texto_lower for w in _WEATHER_WORDS)
        _tem_service = any(w in _texto_lower for w in _SERVICE_WORDS)

        if _tem_weather and not _tem_service:
            # Mencionou temporal/chuva → OCORRÊNCIA (Defesa Civil)
            canal = "ocorrencia"
            classificacao["canal"] = "ocorrencia"
            classificacao["categoria"] = "queda_arvore"
            logger.info(f"🌧️ SAFETY NET: árvore + weather → ocorrencia/queda_arvore")
        elif _tem_service and not _tem_weather:
            # Mencionou poda/cortar/cupim → ARBORIZAÇÃO (empresa)
            canal = "arborizacao"
            classificacao["canal"] = "arborizacao"
            if _categoria not in ("poda_geral", "poda_complexa", "poda_desbarra", "remocao", "retirada_toco", "risco_queda", "arvore_caida"):
                classificacao["categoria"] = "arvore_caida"
            logger.info(f"🌳 SAFETY NET: árvore + serviço → arborizacao")
        elif not _tem_weather and not _tem_service:
            # Ambíguo (ex: "árvore caiu na rua") → ARBORIZAÇÃO por padrão
            # (empresa remove, se for emergência o operador reclassifica)
            canal = "arborizacao"
            classificacao["canal"] = "arborizacao"
            if _categoria not in ("poda_geral", "poda_complexa", "poda_desbarra", "remocao", "retirada_toco", "risco_queda", "arvore_caida"):
                classificacao["categoria"] = "arvore_caida"
            logger.info(f"🔄 SAFETY NET: árvore ambígua → arborizacao (padrão)")

    # ── 6b. SAUDAÇÃO — responde sem criar protocolo ──
    if canal == "saudacao":
        resposta = classificacao.get("resposta_whatsapp", "")
        if not resposta:
            push = dados["push_name"]
            resposta = (f"Olá{', ' + push if push else ''}! 👋\n"
                        f"Sou a Clara, assistente da Prefeitura de Maringá.\n\n"
                        f"Como posso ajudar?\n"
                        f"📢 Denúncia\n📍 Ocorrência urbana\n💬 Feedback\n🔍 Consultar protocolo\n🆘 SOS Mulher")
        # Enfileira como saudacao pra responder sem criar registro
        event = _montar_evento(dados, request, classificacao=classificacao, is_continuacao=False)
        return _enfileirar(event, "queue:saudacoes")

    fila_map = {
        "denuncia": "queue:denuncias",
        "sos_mulher": "queue:sos",
        "ocorrencia": "queue:ocorrencias",
        "arborizacao": "queue:arborizacao",
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
        "media_base64": dados.get("media_base64", ""),
        "is_forwarded": dados.get("is_forwarded", False),
        "forwarding_score": dados.get("forwarding_score", 0),
        "media_key_timestamp": dados.get("media_key_timestamp"),
        "texto_truncado": dados.get("texto_truncado", False),
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
