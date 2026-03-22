#!/usr/bin/env python3
"""
worker.py — Processador v3 — com SESSAO de conversa
=====================================================
Quando e NOVO: cria registro + cria sessao + responde
Quando e CONTINUACAO: atualiza registro + atualiza sessao + responde
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any

import httpx
import redis as redis_lib
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("worker")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

# ── Limites de mídia ──
MAX_FOTOS_POR_DENUNCIA = 5          # máx 5 fotos por registro
MAX_VIDEOS_POR_DENUNCIA = 1         # máx 1 vídeo por registro
MAX_VIDEO_SIZE_BYTES = 16 * 1024 * 1024   # 16MB
MAX_FOTO_SIZE_BYTES = 5 * 1024 * 1024     # 5MB
STORAGE_BUCKET = "evidencias"

# SOS primeiro — prioridade maxima
QUEUES = ["queue:sos", "queue:denuncias", "queue:ocorrencias", "queue:feedbacks"]


def gerar_protocolo(sb: Client) -> str:
    try:
        result = sb.rpc("nextval", {"seq_name": "protocolo_seq"}).execute()
        seq = result.data
        return f"MGA-{date.today().year}-{str(seq).zfill(5)}"
    except Exception as exc:
        logger.error(f"Falha ao gerar protocolo: {exc}")
        import uuid
        return f"MGA-{date.today().year}-{str(uuid.uuid4())[:8].upper()}"


def enviar_whatsapp(telefone: str, mensagem: str) -> bool:
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        logger.warning("Evolution API nao configurada")
        return False

    numero = telefone.lstrip("+")
    url = f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}"

    try:
        response = httpx.post(url, json={"number": numero, "text": mensagem},
                              headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY},
                              timeout=10.0)
        if response.status_code in (200, 201):
            logger.info(f"WhatsApp enviado para {telefone}")
            return True
        else:
            logger.error(f"Falha WhatsApp: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as exc:
        logger.error(f"Erro WhatsApp: {exc}")
        return False


def download_media(message_id: str) -> bytes | None:
    """Baixa a mídia de uma mensagem via Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not message_id:
        return None
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{WA_INSTANCE_NAME}"
    try:
        import base64
        response = httpx.post(
            url,
            json={"message": {"key": {"id": message_id}}, "convertToMp4": True},
            headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY},
            timeout=30.0,
        )
        if response.status_code in (200, 201):
            data = response.json()
            b64 = data.get("base64", "")
            if b64:
                # Remove prefixo data:image/...;base64, se houver
                if ";base64," in b64:
                    b64 = b64.split(";base64,")[1]
                return base64.b64decode(b64)
        logger.error(f"Download midia falhou: {response.status_code}")
    except Exception as exc:
        logger.error(f"Erro download midia: {exc}")
    return None


def upload_to_storage(sb: Client, file_bytes: bytes, registro_id: str,
                      tipo_midia: str, mimetype: str | None) -> str | None:
    """Faz upload para Supabase Storage e retorna a URL pública."""
    ext_map = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/3gpp": ".3gp", "video/quicktime": ".mov",
    }
    ext = ext_map.get(mimetype, ".jpg" if tipo_midia == "imagem" else ".mp4")
    filename = f"{registro_id}/{uuid.uuid4().hex[:12]}{ext}"

    try:
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": mimetype or "application/octet-stream"},
        )
        public_url = sb.storage.from_(STORAGE_BUCKET).get_public_url(filename)
        logger.info(f"Upload OK: {filename}")
        return public_url
    except Exception as exc:
        logger.error(f"Erro upload storage: {exc}")
        return None


def processar_midia(event: dict, sb: Client, registro_id: str, tabela: str) -> str | None:
    """
    Pipeline completo: valida limites → download → upload → atualiza midia_urls.
    Retorna mensagem de erro pro cidadão ou None se deu certo.
    """
    tipo_midia = event.get("tipo_midia")
    file_length = event.get("file_length")
    message_id = event.get("message_id")

    if not tipo_midia or tipo_midia not in ("imagem", "video"):
        return None  # Não é mídia processável

    # ── 1. Validar tamanho ──
    if file_length:
        if tipo_midia == "video" and file_length > MAX_VIDEO_SIZE_BYTES:
            mb = MAX_VIDEO_SIZE_BYTES // (1024 * 1024)
            return f"⚠️ Vídeo muito grande! O limite é {mb}MB. Tente gravar um vídeo mais curto (até 30s)."
        if tipo_midia == "imagem" and file_length > MAX_FOTO_SIZE_BYTES:
            mb = MAX_FOTO_SIZE_BYTES // (1024 * 1024)
            return f"⚠️ Foto muito grande! O limite é {mb}MB. Tente enviar uma foto com resolução menor."

    # ── 2. Verificar limites de quantidade ──
    try:
        result = sb.table(tabela).select("midia_urls").eq("id", registro_id).execute()
        urls_atuais = result.data[0].get("midia_urls") or [] if result.data else []
    except Exception:
        urls_atuais = []

    fotos_atuais = sum(1 for u in urls_atuais if not any(u.endswith(e) for e in (".mp4", ".3gp", ".mov")))
    videos_atuais = sum(1 for u in urls_atuais if any(u.endswith(e) for e in (".mp4", ".3gp", ".mov")))

    if tipo_midia == "imagem" and fotos_atuais >= MAX_FOTOS_POR_DENUNCIA:
        return f"📸 Limite de {MAX_FOTOS_POR_DENUNCIA} fotos atingido. Evidências suficientes para este registro."
    if tipo_midia == "video" and videos_atuais >= MAX_VIDEOS_POR_DENUNCIA:
        return f"🎥 Limite de {MAX_VIDEOS_POR_DENUNCIA} vídeo(s) atingido. Evidências suficientes para este registro."

    # ── 3. Download da Evolution API ──
    file_bytes = download_media(message_id)
    if not file_bytes:
        logger.warning(f"Não foi possível baixar mídia {message_id}")
        return None  # Falha silenciosa — não bloqueia o fluxo

    # ── 4. Validar tamanho real (fallback se fileLength não veio no payload) ──
    real_size = len(file_bytes)
    if tipo_midia == "video" and real_size > MAX_VIDEO_SIZE_BYTES:
        mb = MAX_VIDEO_SIZE_BYTES // (1024 * 1024)
        return f"⚠️ Vídeo muito grande ({real_size // (1024*1024)}MB)! O limite é {mb}MB."
    if tipo_midia == "imagem" and real_size > MAX_FOTO_SIZE_BYTES:
        mb = MAX_FOTO_SIZE_BYTES // (1024 * 1024)
        return f"⚠️ Foto muito grande! O limite é {mb}MB."

    # ── 5. Upload para Supabase Storage ──
    mimetype = event.get("mimetype")
    public_url = upload_to_storage(sb, file_bytes, registro_id, tipo_midia, mimetype)
    if not public_url:
        return None  # Falha silenciosa

    # ── 6. Atualizar midia_urls no banco ──
    novas_urls = urls_atuais + [public_url]
    try:
        sb.table(tabela).update({"midia_urls": novas_urls}).eq("id", registro_id).execute()
        logger.info(f"Mídia salva: {tabela}/{registro_id} ({len(novas_urls)} total)")
    except Exception as exc:
        logger.error(f"Erro ao atualizar midia_urls: {exc}")

    return None  # Sucesso


def criar_sessao(sb: Client, telefone: str, canal: str, etapa: str,
                 registro_id: str, contexto: dict) -> None:
    """Cria ou atualiza sessao de conversa pra esse telefone."""
    try:
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        sb.table("sessoes_conversa").upsert({
            "telefone": telefone,
            "canal": canal,
            "etapa": etapa,
            "registro_id": registro_id,
            "contexto": contexto,
            "expira_em": expira_em,
        }, on_conflict="telefone").execute()
        logger.info(f"Sessao criada/atualizada: {telefone} → {canal}/{etapa}")
    except Exception as exc:
        logger.error(f"Erro ao criar sessao: {exc}")


def finalizar_sessao(sb: Client, telefone: str) -> None:
    """Marca sessao como finalizada."""
    try:
        sb.table("sessoes_conversa").update({
            "etapa": "finalizado"
        }).eq("telefone", telefone).execute()
    except Exception as exc:
        logger.error(f"Erro ao finalizar sessao: {exc}")


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — DENUNCIA
# ══════════════════════════════════════════════════════════════

def processar_denuncia(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    classificacao = event.get("classificacao", {})

    if is_continuacao:
        _continuar_denuncia(event, sb)
        return

    # ── NOVA DENUNCIA ──
    protocolo = gerar_protocolo(sb)
    categoria = classificacao.get("categoria", "outros_crimes")

    res = sb.table("denuncias").insert({
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "mensagem": texto,
        "status": "novo",
    }).execute()

    if not res.data:
        logger.error(f"Falha ao criar denuncia")
        return

    registro_id = res.data[0]["id"]
    logger.info(f"Denuncia criada: {protocolo} ({categoria})")

    # Determinar proxima etapa
    tem_midia = event.get("tem_midia", False)
    tem_loc = event.get("tem_localizacao", False)

    # Processar mídia se veio junto com a primeira mensagem
    if tem_midia:
        erro_midia = processar_midia(event, sb, registro_id, "denuncias")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            # Continua o fluxo mesmo com erro de mídia

    if not tem_midia:
        etapa = "aguardando_midia"
        resposta = (f"✅ Recebido, {push_name or 'cidadão'}! Sua denúncia de *{categoria.replace('_', ' ')}* "
                    f"foi registrada.\n\n"
                    f"📸 Consegue enviar uma foto ou vídeo como evidência? "
                    f"Isso fortalece muito a investigação.\n\n"
                    f"📋 Protocolo: {protocolo}")
    elif not tem_loc:
        etapa = "aguardando_endereco"
        resposta = (f"✅ Evidência recebida! Agora preciso da localização.\n\n"
                    f"📍 Envie o endereço ou clique em: 📎 > Localização\n\n"
                    f"📋 Protocolo: {protocolo}")
    else:
        etapa = "finalizado"
        resposta = (f"✅ Denúncia completa registrada!\n\n"
                    f"A equipe já foi notificada e vai investigar.\n\n"
                    f"📋 Protocolo: {protocolo}")

    criar_sessao(sb, telefone, "denuncia", etapa, registro_id,
                 {"protocolo": protocolo, "categoria": categoria})

    if etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, resposta)


def _continuar_denuncia(event: dict, sb: Client) -> None:
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    registro_id = sessao.get("registro_id") if sessao else None
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    protocolo = contexto.get("protocolo", "")

    if not registro_id:
        logger.error("Continuacao sem registro_id")
        return

    update_data = {}
    tem_midia = event.get("tem_midia", False)
    tem_loc = event.get("tem_localizacao", False)
    texto = event.get("texto", "")

    if tem_midia and etapa_atual == "aguardando_midia":
        erro_midia = processar_midia(event, sb, registro_id, "denuncias")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        update_data["status"] = "novo"
        nova_etapa = "aguardando_endereco"
        resposta = (f"📸 Evidência recebida! Obrigado.\n\n"
                    f"📍 Agora me diz o endereço ou envia sua localização: 📎 > Localização")

    elif tem_loc:
        update_data["latitude"] = event.get("latitude")
        update_data["longitude"] = event.get("longitude")
        nova_etapa = "finalizado"
        resposta = (f"📍 Localização registrada!\n\n"
                    f"✅ Denúncia completa. A equipe já foi notificada.\n"
                    f"📋 Protocolo: {protocolo}")

    elif texto and etapa_atual == "aguardando_endereco":
        update_data["endereco"] = texto
        update_data["bairro"] = texto  # IA pode melhorar depois
        nova_etapa = "finalizado"
        resposta = (f"📍 Endereço registrado: {texto}\n\n"
                    f"✅ Denúncia completa. A equipe já foi notificada.\n"
                    f"📋 Protocolo: {protocolo}")

    elif tem_midia:
        # Midia em qualquer etapa — aceita com validação
        erro_midia = processar_midia(event, sb, registro_id, "denuncias")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        nova_etapa = etapa_atual
        resposta = f"📸 Evidência adicional recebida! Obrigado."

    else:
        # Texto extra — adiciona como nota
        nova_etapa = etapa_atual
        resposta = f"✅ Informação adicional registrada no protocolo {protocolo}."

    if update_data:
        sb.table("denuncias").update(update_data).eq("id", registro_id).execute()

    criar_sessao(sb, telefone, "denuncia", nova_etapa, registro_id, contexto)
    if nova_etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, resposta)


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — SOS MULHER
# ══════════════════════════════════════════════════════════════

def processar_sos(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    tem_loc = event.get("tem_localizacao", False)

    if is_continuacao and tem_loc:
        # Atualizou localizacao do SOS ativo
        sessao = event.get("sessao", {})
        registro_id = sessao.get("registro_id") if sessao else None
        if registro_id:
            sb.table("sos_alertas").update({
                "latitude": event.get("latitude"),
                "longitude": event.get("longitude"),
            }).eq("id", registro_id).execute()
            logger.warning(f"🚨 SOS localizacao atualizada para {telefone}")
        enviar_whatsapp(telefone, "📍 Localização recebida. Equipe a caminho. Mantenha-se segura.")
        finalizar_sessao(sb, telefone)
        return

    if is_continuacao:
        # Qualquer outra mensagem durante SOS ativo
        enviar_whatsapp(telefone, "✓ Recebido. Se puder, envie sua localização: 📎 > Localização")
        return

    # ── NOVO SOS ──
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
        registro_id = res.data[0]["id"]
        logger.warning(f"🚨 SOS ALERTA CRIADO (id={registro_id})")
        criar_sessao(sb, telefone, "sos_mulher", "aguardando_localizacao", registro_id,
                     {"tipo": "emergencia"})
        enviar_whatsapp(telefone, "✓ Recebido. Se puder, envie sua localização: 📎 > Localização")


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — OCORRENCIA
# ══════════════════════════════════════════════════════════════

def processar_ocorrencia(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    classificacao = event.get("classificacao", {})

    if is_continuacao:
        _continuar_ocorrencia(event, sb)
        return

    protocolo = gerar_protocolo(sb)
    categoria = classificacao.get("categoria", "outros_urbanos")
    resumo = classificacao.get("resumo", texto[:200] if texto else "Ocorrência")

    res = sb.table("ocorrencias").insert({
        "protocolo": protocolo,
        "categoria": categoria,
        "titulo": resumo,
        "endereco": texto[:500] if texto else "",
        "endereco_normalizado": texto[:500].lower() if texto else "",
        "status": "aberto",
        "severidade": "baixa",
        "total_relatos": 1,
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
    }).execute()

    if not res.data:
        logger.error("Falha ao criar ocorrencia")
        return

    registro_id = res.data[0]["id"]

    sb.table("ocorrencias_relatos").insert({
        "ocorrencia_id": registro_id,
        "telefone": telefone,
        "nome": push_name or None,
        "mensagem": texto,
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
    }).execute()

    tem_loc = event.get("tem_localizacao", False)
    tem_midia = event.get("tem_midia", False)

    # Processar mídia se veio junto
    if tem_midia:
        erro_midia = processar_midia(event, sb, registro_id, "ocorrencias_relatos")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)

    if not tem_loc:
        etapa = "aguardando_endereco"
        resposta = (f"⚠️ Ocorrência de *{categoria.replace('_', ' ')}* registrada!\n\n"
                    f"📍 Pode enviar a localização? Clique em: 📎 > Localização\n"
                    f"Ou me diga a rua e o bairro.\n\n"
                    f"📋 Protocolo: {protocolo}")
    elif not tem_midia:
        etapa = "aguardando_midia"
        resposta = (f"⚠️ Ocorrência registrada com localização!\n\n"
                    f"📸 Se puder, envie uma foto do problema.\n\n"
                    f"📋 Protocolo: {protocolo}")
    else:
        etapa = "finalizado"
        resposta = (f"⚠️ Ocorrência completa registrada!\n\n"
                    f"A equipe responsável já foi notificada.\n\n"
                    f"📋 Protocolo: {protocolo}")

    criar_sessao(sb, telefone, "ocorrencia", etapa, registro_id,
                 {"protocolo": protocolo, "categoria": categoria})

    if etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, resposta)


def _continuar_ocorrencia(event: dict, sb: Client) -> None:
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    registro_id = sessao.get("registro_id") if sessao else None
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    protocolo = contexto.get("protocolo", "")

    if not registro_id:
        return

    tem_loc = event.get("tem_localizacao", False)
    tem_midia = event.get("tem_midia", False)
    texto = event.get("texto", "")

    if tem_loc:
        sb.table("ocorrencias").update({
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
        }).eq("id", registro_id).execute()
        nova_etapa = "finalizado"
        resposta = (f"📍 Localização registrada!\n\n"
                    f"✅ Equipe notificada. Obrigado por reportar!\n"
                    f"📋 Protocolo: {protocolo}")

    elif texto and etapa_atual == "aguardando_endereco":
        sb.table("ocorrencias").update({
            "endereco": texto,
            "endereco_normalizado": texto.lower(),
        }).eq("id", registro_id).execute()
        nova_etapa = "finalizado"
        resposta = (f"📍 Endereço registrado: {texto}\n\n"
                    f"✅ Equipe notificada. Obrigado!\n"
                    f"📋 Protocolo: {protocolo}")

    elif tem_midia:
        erro_midia = processar_midia(event, sb, registro_id, "ocorrencias_relatos")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        nova_etapa = etapa_atual
        resposta = f"📸 Evidência recebida! Obrigado."

    else:
        nova_etapa = etapa_atual
        resposta = f"✅ Informação registrada no protocolo {protocolo}."

    criar_sessao(sb, telefone, "ocorrencia", nova_etapa, registro_id, contexto)
    if nova_etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, resposta)


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — FEEDBACK
# ══════════════════════════════════════════════════════════════

def processar_feedback(event: dict, sb: Client) -> None:
    classificacao = event.get("classificacao", {})
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")

    # Feedback nao tem sessao — cada mensagem e independente
    protocolo = gerar_protocolo(sb)
    sentimento = classificacao.get("sentimento", "neutro")
    categoria = classificacao.get("categoria", "outros")

    res = sb.table("feedbacks").insert({
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "sentimento": sentimento,
        "urgencia": classificacao.get("urgencia", "normal"),
        "mensagem": texto,
        "resumo": classificacao.get("resumo"),
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
        "status": "novo",
    }).execute()

    if res.data:
        logger.info(f"Feedback: {protocolo} ({sentimento})")

        emoji = {"positivo": "😊", "negativo": "😔", "neutro": "📝"}.get(sentimento, "📝")
        resposta_ia = classificacao.get("resposta_whatsapp", "")

        if resposta_ia:
            resposta = f"{resposta_ia}\n\n📋 Protocolo: {protocolo}"
        else:
            resposta = (f"{emoji} Obrigado pelo seu feedback, {push_name or 'cidadão'}!\n\n"
                        f"Vamos encaminhar para o setor de *{categoria.replace('_', ' ')}*.\n\n"
                        f"📋 Protocolo: {protocolo}")

        enviar_whatsapp(telefone, resposta)
        # Feedback nao cria sessao — mensagem unica


PROCESSADORES = {
    "queue:sos": processar_sos,
    "queue:denuncias": processar_denuncia,
    "queue:ocorrencias": processar_ocorrencia,
    "queue:feedbacks": processar_feedback,
}


def conectar():
    while True:
        try:
            r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True,
                                         socket_connect_timeout=5, socket_timeout=5)
            r.ping()
            sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Conectado ao Redis e Supabase!")
            return r, sb
        except Exception as exc:
            logger.error(f"Falha: {exc}. Retry em 5s...")
            time.sleep(5)


def main():
    logger.info("Worker v3 (com sessao) iniciando...")
    logger.info(f"Filas: {QUEUES}")
    r, sb = conectar()
    logger.info("Pronto!")

    while True:
        try:
            resultado = r.blpop(QUEUES, timeout=5)
            if resultado is None:
                continue

            fila, raw = resultado
            logger.info(f"Fila '{fila}' → processando...")
            event = json.loads(raw)
            proc = PROCESSADORES.get(fila)
            if proc:
                proc(event, sb)
            else:
                logger.warning(f"Sem processador: {fila}")

        except redis_lib.exceptions.ConnectionError as exc:
            logger.error(f"Redis off: {exc}")
            time.sleep(3)
            r, sb = conectar()
        except json.JSONDecodeError as exc:
            logger.error(f"JSON invalido: {exc}")
        except Exception as exc:
            logger.exception(f"Erro: {exc}")


if __name__ == "__main__":
    main()
