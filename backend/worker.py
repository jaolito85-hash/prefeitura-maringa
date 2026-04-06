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
import math
import os
import re
import secrets
import sys
import time
import unicodedata
import urllib.parse
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
QUEUES = ["queue:sos", "queue:denuncias", "queue:ocorrencias", "queue:arborizacao", "queue:feedbacks", "queue:consultas", "queue:saudacoes"]

# ── Programa Cidadão Ativo — Decreto 291/2026 ──
# APENAS as 5 categorias que a Prefeitura de Maringá paga recompensa.
# Mapeamento: categoria do classificador IA → categoria na recompensas_config
CATEGORIAS_ELEGIVEIS = {
    "pichacao": "pichacao",
    "trafico_drogas": "trafico",
    "trafico": "trafico",
    "descarte_irregular": "lixo",
    "lixo": "lixo",
    "furto_fios": "furto_fios",
    "depredacao": "depredacao",
}

# Menu de categorias — SOMENTE as 5 categorias pagas pelo Decreto 291/2026
MENU_CATEGORIAS = [
    ("1", "pichacao", "Pichação", "R$ 100"),
    ("2", "trafico_drogas", "Tráfico de drogas", "R$ 300"),
    ("3", "descarte_irregular", "Descarte irregular de lixo e entulhos", "R$ 80"),
    ("4", "furto_fios", "Furto de fios e cabos elétricos", "R$ 150"),
    ("5", "depredacao", "Depredação de patrimônio público", "R$ 150"),
]

# Mapa rápido: número ou texto → categoria
_MENU_LOOKUP = {}
for _num, _cat, _label, _ in MENU_CATEGORIAS:
    _MENU_LOOKUP[_num] = _cat
    _MENU_LOOKUP[_cat] = _cat
    # Adiciona versões simplificadas pra matching por texto
    for _palavra in _label.lower().split():
        if len(_palavra) > 3:  # ignora palavras curtas como "de", "ou"
            _MENU_LOOKUP[_palavra] = _cat

def _montar_menu_categorias() -> str:
    """Monta a mensagem do menu de categorias para WhatsApp."""
    linhas = ["📢 *Qual tipo de denúncia você gostaria de fazer?*\n"]
    for num, _, label, valor in MENU_CATEGORIAS:
        recomp = f" _(recompensa {valor})_" if valor != "—" else ""
        linhas.append(f"{num}️⃣ {label}{recomp}")
    linhas.append("\nResponda com o *número* da opção.")
    return "\n".join(linhas)

def _identificar_categoria_menu(texto: str) -> str | None:
    """Tenta identificar a categoria a partir da resposta do cidadão ao menu."""
    texto_limpo = texto.strip().lower().rstrip(".")
    # Primeiro tenta por número exato
    if texto_limpo in _MENU_LOOKUP:
        return _MENU_LOOKUP[texto_limpo]
    # Tenta match por palavras-chave
    for palavra in texto_limpo.split():
        palavra_limpa = palavra.strip(".,!?")
        if palavra_limpa in _MENU_LOOKUP:
            return _MENU_LOOKUP[palavra_limpa]
    return None


# ── CLASSIFICAÇÃO POR IMAGEM — helpers ──────────────────────────────────

# Menu genérico de categorias pra quando a IA não tem confiança na imagem
MENU_CATEGORIAS_IMAGEM = [
    ("1", "feedback", "buraco_via", "🕳️ Buraco / asfalto"),
    ("2", "feedback", "iluminacao", "💡 Iluminação / poste"),
    ("3", "feedback", "mato_alto", "🌿 Mato alto / terreno"),
    ("4", "ocorrencia", "queda_arvore", "🌳 Árvore caída"),
    ("5", "denuncia", "pichacao", "🎨 Pichação / vandalismo"),
    ("6", "denuncia", "trafico_drogas", "🚨 Tráfico / atividade suspeita"),
    ("7", "denuncia", "furto_fios", "⚡ Furto de fios / cabos"),
    ("8", "feedback", "outros", "📝 Outro"),
]

_MENU_IMAGEM_LOOKUP = {}
for _num, _canal, _cat, _label in MENU_CATEGORIAS_IMAGEM:
    _MENU_IMAGEM_LOOKUP[_num] = (_canal, _cat)


def _montar_menu_imagem() -> str:
    """Monta menu de categorias para classificação por imagem (fallback)."""
    linhas = ["Recebi a foto! Me ajuda a classificar — qual o tipo?\n"]
    for num, _, _, label in MENU_CATEGORIAS_IMAGEM:
        linhas.append(f"{num}️⃣ {label}")
    linhas.append("\nResponda com o *número* da opção.")
    return "\n".join(linhas)


def _identificar_categoria_menu_imagem(texto: str) -> tuple[str, str] | None:
    """Retorna (canal, categoria) a partir da resposta ao menu de imagem."""
    texto_limpo = texto.strip().lower().rstrip(".")
    if texto_limpo in _MENU_IMAGEM_LOOKUP:
        return _MENU_IMAGEM_LOOKUP[texto_limpo]
    return None


# Mapa de ícones por categoria (pra mensagem de confirmação)
_ICONE_CATEGORIA = {
    "buraco_via": "🕳️", "calcada": "🚧", "iluminacao": "💡", "mato_alto": "🌿",
    "esgoto": "🚰", "sinalizacao": "🚦", "veiculo_abandonado": "🚗",
    "queda_arvore": "🌳", "alagamento": "🌊", "deslizamento": "⛰️",
    "incendio": "🔥", "vendaval": "💨", "acidente": "🚨",
    "pichacao": "🎨", "trafico": "🚨", "trafico_drogas": "🚨",
    "descarte_irregular": "🗑️", "furto_fios": "⚡", "depredacao": "💥",
}


def classificar_foto_origem(event: dict) -> dict:
    """Classifica a origem da foto baseado nos metadados da Evolution API.
    Retorna dict com foto_origem, foto_flag e foto_flag_motivo.

    Lógica:
    - Sem mídia de imagem/vídeo → unknown (sem foto pra verificar)
    - Encaminhada (isForwarded/forwardingScore) → high (red flag)
    - Com mediaKeyTimestamp → compara com horário de recebimento
    - Sem mediaKeyTimestamp mas NÃO encaminhada → foto direta (confiável)
      A Evolution API nem sempre envia mediaKeyTimestamp, mas se não
      é encaminhada, a foto veio diretamente do celular do cidadão.
    """
    is_forwarded = event.get("is_forwarded", False)
    forwarding_score = event.get("forwarding_score", 0) or 0
    media_key_timestamp = event.get("media_key_timestamp")
    received_at = event.get("received_at", "")

    # Sem mídia de imagem/vídeo → unknown
    tipo_midia = event.get("tipo_midia")
    if tipo_midia not in ("imagem", "video"):
        return {"foto_origem": "desconhecida", "foto_flag": "unknown", "foto_flag_motivo": "Sem foto para verificar"}

    logger.info(f"📷 classificar_foto: tipo={tipo_midia}, forwarded={is_forwarded}, "
                f"fwd_score={forwarding_score}, mediaKeyTs={media_key_timestamp}")

    # 1. Foto encaminhada → RED FLAG ALTA
    if is_forwarded or forwarding_score > 0:
        return {
            "foto_origem": "encaminhada",
            "foto_flag": "high",
            "foto_flag_motivo": "Foto encaminhada de outra conversa",
        }

    # 2. Comparar mediaKeyTimestamp com horário de recebimento (quando disponível)
    if media_key_timestamp and received_at:
        try:
            ts_media = datetime.fromtimestamp(media_key_timestamp, tz=timezone.utc)
            ts_received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
            diff_seconds = (ts_received - ts_media).total_seconds()

            logger.info(f"📷 timestamp diff: {diff_seconds:.0f}s ({diff_seconds/60:.1f}min)")

            # Foto tirada na hora (< 5 min)
            if diff_seconds < 300:
                return {
                    "foto_origem": "camera_direta",
                    "foto_flag": "none",
                    "foto_flag_motivo": "Foto tirada na hora",
                }
            # Foto da galeria antiga (> 24h)
            elif diff_seconds > 86400:
                return {
                    "foto_origem": "galeria_antiga",
                    "foto_flag": "medium",
                    "foto_flag_motivo": "Foto da galeria com mais de 24h",
                }
            # Foto da galeria recente (entre 5min e 24h)
            else:
                return {
                    "foto_origem": "galeria_recente",
                    "foto_flag": "low",
                    "foto_flag_motivo": "Foto enviada da galeria",
                }
        except (ValueError, TypeError, OSError) as exc:
            logger.warning(f"📷 Erro ao comparar timestamps: {exc}")

    # 3. Sem timestamp mas NÃO encaminhada → foto direta (confiável)
    # A Evolution API nem sempre envia mediaKeyTimestamp.
    # Se chegou até aqui, não é encaminhada → veio do celular do cidadão.
    return {
        "foto_origem": "camera_direta",
        "foto_flag": "none",
        "foto_flag_motivo": "Foto enviada diretamente",
    }


# Chave AES para criptografia (em produção, vem do .env)
AES_KEY = os.environ.get("AES_KEY", "")


def gerar_protocolo(sb: Client) -> str:
    """Gera protocolo MGA-YYYY-XXXXX buscando MAX do banco + 1.
    Simples e à prova de conflito com dados de seed."""
    ano = date.today().year
    try:
        # Buscar o maior protocolo existente no banco
        result = sb.table("denuncias").select("protocolo").like(
            "protocolo", f"MGA-{ano}-%"
        ).order("protocolo", desc=True).limit(1).execute()

        if result.data and result.data[0].get("protocolo"):
            ultimo = result.data[0]["protocolo"]  # ex: MGA-2026-00580
            try:
                max_num = int(ultimo.split("-")[-1])
            except (ValueError, IndexError):
                max_num = 0
        else:
            max_num = 0

        novo = max_num + 1
        protocolo = f"MGA-{ano}-{str(novo).zfill(5)}"
        logger.info(f"Protocolo gerado: {protocolo} (max anterior: {max_num})")
        return protocolo

    except Exception as exc:
        logger.error(f"Falha ao gerar protocolo: {exc}")
        # Fallback com UUID — nunca colide
        return f"MGA-{ano}-{secrets.token_hex(4).upper()}"


AVISO_TRUNCAGEM = (
    "⚠️ _Sua mensagem era muito longa e foi resumida. "
    "Para melhor atendimento, envie textos mais curtos (até ~10 linhas)._\n\n"
)


def _com_aviso_truncagem(event: dict, resposta: str) -> str:
    """Prefixa o aviso de truncagem na resposta se a mensagem foi truncada."""
    if event.get("texto_truncado"):
        return AVISO_TRUNCAGEM + resposta
    return resposta


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


def enviar_whatsapp_imagem(telefone: str, image_url: str, caption: str = "") -> bool:
    """Envia imagem via Evolution API (sendMedia)."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        return False
    numero = telefone.lstrip("+")
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{WA_INSTANCE_NAME}"
    try:
        response = httpx.post(url, json={
            "number": numero,
            "mediatype": "image",
            "media": image_url,
            "caption": caption,
        }, headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY}, timeout=15.0)
        if response.status_code in (200, 201):
            logger.info(f"WhatsApp imagem enviada para {telefone}")
            return True
        else:
            logger.error(f"Falha WhatsApp imagem: {response.status_code}")
            return False
    except Exception as exc:
        logger.error(f"Erro WhatsApp imagem: {exc}")
        return False


def download_media(message_id: str, media_base64: str = "") -> bytes | None:
    """
    Baixa a mídia de uma mensagem.
    1º tenta usar o base64 que já veio no webhook (Webhook Base64 ON na Evolution)
    2º fallback: chama getBase64FromMediaMessage na Evolution API
    """
    import base64

    # ── 1. Usar base64 do webhook (mais rápido e confiável, especialmente pra vídeo) ──
    if media_base64:
        try:
            b64 = media_base64
            if ";base64," in b64:
                b64 = b64.split(";base64,")[1]
            resultado = base64.b64decode(b64)
            if len(resultado) > 0:
                logger.info(f"Mídia obtida do webhook base64 ({len(resultado)} bytes)")
                return resultado
        except Exception as exc:
            logger.warning(f"Falha ao decodificar base64 do webhook: {exc}")

    # ── 2. Fallback: chamar Evolution API ──
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY or not message_id:
        return None
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{WA_INSTANCE_NAME}"
    try:
        logger.info(f"Baixando mídia via API: {message_id}")
        response = httpx.post(
            url,
            json={"message": {"key": {"id": message_id}}, "convertToMp4": True},
            headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY},
            timeout=120.0,
        )
        if response.status_code in (200, 201):
            data = response.json()
            b64 = data.get("base64", "")
            if b64:
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

    # ── 3. Download (usa base64 do webhook primeiro, fallback pra API) ──
    media_base64 = event.get("media_base64", "")
    file_bytes = download_media(message_id, media_base64)
    if not file_bytes:
        logger.warning(f"Não foi possível baixar mídia {message_id}")
        return ("⚠️ Não consegui receber seu arquivo. Isso pode acontecer com vídeos grandes.\n\n"
                "💡 Dica: tente enviar novamente ou grave um vídeo mais curto (até 30s).")

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

    # ── 7. Se é relato de ocorrência, salvar URL também na tabela ocorrencias ──
    # Nota: nas chamadas do worker, registro_id é o ID da ocorrência (não do relato)
    if tabela == "ocorrencias_relatos":
        try:
            oc_id = registro_id
            oc_result = sb.table("ocorrencias").select("midia_urls").eq("id", oc_id).execute()
            oc_urls = oc_result.data[0].get("midia_urls") or [] if oc_result.data else []
            is_video = any(public_url.endswith(e) for e in (".mp4", ".3gp", ".mov"))
            sb.table("ocorrencias").update({
                "midia_urls": oc_urls + [public_url],
                "tem_foto": not is_video or any(not u.endswith((".mp4", ".3gp", ".mov")) for u in oc_urls),
                "tem_video": is_video or any(u.endswith((".mp4", ".3gp", ".mov")) for u in oc_urls),
            }).eq("id", oc_id).execute()
            logger.info(f"Mídia também salva em ocorrencias/{oc_id}")
        except Exception as exc:
            logger.error(f"Erro ao copiar mídia pra ocorrência: {exc}")

    return None  # Sucesso


SESSAO_TTL_MINUTOS = 5  # Tempo de vida da sessão (minutos)

def criar_sessao(sb: Client, telefone: str, canal: str, etapa: str,
                 registro_id: str, contexto: dict, ttl_minutos: int = None) -> None:
    """Cria ou atualiza sessao de conversa pra esse telefone."""
    try:
        ttl = ttl_minutos or SESSAO_TTL_MINUTOS
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=ttl)).isoformat()
        sb.table("sessoes_conversa").upsert({
            "telefone": telefone,
            "canal": canal,
            "etapa": etapa,
            "registro_id": registro_id,
            "contexto": contexto,
            "expira_em": expira_em,
            "handoff_ativo": False,
            "handoff_operador": "",
        }, on_conflict="telefone").execute()
        logger.info(f"Sessao criada/atualizada: {telefone} → {canal}/{etapa}")
    except Exception as exc:
        logger.error(f"Erro ao criar sessao: {exc}")


def atualizar_sessao(sb: Client, telefone: str, etapa: str, contexto: dict, ttl_minutos: int = None) -> None:
    """Atualiza a etapa e contexto da sessao ativa sem mudar canal/registro_id."""
    try:
        ttl = ttl_minutos or SESSAO_TTL_MINUTOS
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=ttl)).isoformat()
        sb.table("sessoes_conversa").update({
            "etapa": etapa,
            "contexto": contexto,
            "expira_em": expira_em,
        }).eq("telefone", telefone).execute()
        logger.info(f"Sessao atualizada: {telefone} → etapa={etapa}")
    except Exception as exc:
        logger.error(f"Erro ao atualizar sessao: {exc}")


def finalizar_sessao(sb: Client, telefone: str) -> None:
    """Marca sessao como finalizada."""
    try:
        sb.table("sessoes_conversa").update({
            "etapa": "finalizado"
        }).eq("telefone", telefone).execute()
    except Exception as exc:
        logger.error(f"Erro ao finalizar sessao: {exc}")


# ══════════════════════════════════════════════════════════════
# CIDADÃO ATIVO — Helpers para recompensa
# ══════════════════════════════════════════════════════════════

def _encriptar_dado(valor: str) -> str:
    """
    Encripta dado sensível com AES-256.
    Na demo: usa base64 reversível com prefixo ENC_.
    Em produção: usa AES real com a AES_KEY do .env.
    """
    if not valor:
        return ""
    import base64
    if AES_KEY:
        # TODO Fase 2: implementar AES-256-GCM real
        pass
    # Demo: base64 reversível (permite ver dados no painel financeiro)
    encoded = base64.b64encode(valor.encode('utf-8')).decode('utf-8')
    return f"ENC_{encoded}"


def _decriptar_dado(valor_enc: str) -> str:
    """Decripta dado sensível. Demo: reverte base64."""
    if not valor_enc:
        return "—"
    import base64
    if valor_enc.startswith("ENC_"):
        try:
            encoded = valor_enc[4:]  # Remove prefixo "ENC_"
            return base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
        except Exception:
            pass
    # Fallback para dados antigos (ENC_AES256_xxxx)
    if valor_enc.startswith("ENC_AES256_"):
        return f"***{valor_enc[-4:]}"
    return valor_enc


def _buscar_valor_recompensa(sb: Client, categoria_ia: str) -> float | None:
    """
    Busca o valor da recompensa na tabela de configuração.
    Converte a categoria do classificador IA pra categoria da config.
    """
    cat_config = CATEGORIAS_ELEGIVEIS.get(categoria_ia)
    if not cat_config:
        return None
    try:
        result = sb.table("recompensas_config").select(
            "valor_padrao, ativo"
        ).eq("categoria", cat_config).execute()
        if result.data and result.data[0].get("ativo"):
            return float(result.data[0]["valor_padrao"])
    except Exception as exc:
        logger.error(f"Erro ao buscar valor recompensa: {exc}")
    return None


def _criar_recompensa(sb: Client, denuncia_id: str, protocolo: str,
                      valor: float, cpf: str, chave_pix: str,
                      tipo_pix: str, _pre_encrypted: bool = False) -> bool:
    """
    Cria o registro de recompensa vinculado à denúncia.
    Dados sensíveis são encriptados antes de salvar.
    Se _pre_encrypted=True, os dados já vêm encriptados (reutilização).
    """
    cpf_enc = cpf if _pre_encrypted else _encriptar_dado(cpf)
    pix_enc = chave_pix if _pre_encrypted else _encriptar_dado(chave_pix)

    try:
        sb.table("recompensas").insert({
            "denuncia_id": denuncia_id,
            "protocolo": protocolo,
            "status": "pendente_validacao",
            "valor": valor,
            "cpf_encrypted": cpf_enc,
            "chave_pix_encrypted": pix_enc,
            "tipo_chave_pix": tipo_pix,
        }).execute()

        # Atualizar denúncia com flag e valor
        sb.table("denuncias").update({
            "cidadania_ativa": True,
            "cpf_encrypted": cpf_enc,
            "dados_bancarios_encrypted": pix_enc,
            "valor_recompensa": valor,
        }).eq("id", denuncia_id).execute()

        logger.info(f"Recompensa criada: {protocolo} (R$ {valor})")
        return True
    except Exception as exc:
        logger.error(f"Erro ao criar recompensa: {exc}")
        return False


def _validar_cpf(cpf: str) -> bool:
    """
    Valida CPF com verificação de dígitos (algoritmo oficial Receita Federal).
    Retorna True se o CPF é válido, False caso contrário.
    """
    cpf_limpo = cpf.strip().replace(".", "").replace("-", "").replace(" ", "")
    if len(cpf_limpo) != 11 or not cpf_limpo.isdigit():
        return False
    # Rejeitar sequências repetidas (ex: 111.111.111-11)
    if cpf_limpo == cpf_limpo[0] * 11:
        return False
    # Primeiro dígito verificador
    soma = sum(int(cpf_limpo[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(cpf_limpo[9]) != d1:
        return False
    # Segundo dígito verificador
    soma = sum(int(cpf_limpo[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    if int(cpf_limpo[10]) != d2:
        return False
    return True


def _detectar_nova_intencao_cpf(texto: str) -> bool:
    """
    Detecta se o texto enviado na etapa aguardando_cpf é uma nova intenção
    em vez de uma resposta com CPF.
    Ex: "estao traficando drogas no centro" claramente não é CPF.
    """
    if not texto:
        return False
    texto_limpo = texto.strip().replace(".", "").replace("-", "").replace(" ", "")
    parece_cpf = texto_limpo.isdigit() and len(texto_limpo) <= 14
    # Se não parece CPF e o texto tem mais de 15 caracteres, é nova intenção
    if not parece_cpf and len(texto.strip()) > 15:
        return True
    return False


def _detectar_tipo_pix(chave: str) -> str:
    """
    Detecta automaticamente o tipo de chave PIX pelo formato.
    Telefone BR: 11 dígitos com DDD + 9 (celular) | CPF: 11 dígitos sem padrão celular
    Email: tem @ | Telefone intl: começa com + | Aleatória: resto
    """
    chave_limpa = chave.strip().replace(".", "").replace("-", "").replace(" ", "")
    # Email — mais fácil de detectar
    if "@" in chave:
        return "email"
    # Telefone com + (internacional)
    if chave_limpa.startswith("+"):
        return "telefone"
    # 11 dígitos: pode ser CPF ou telefone celular BR
    # Telefone celular BR: DDD(2) + 9(1) + número(8) = 11 dígitos
    # O 3º dígito (índice 2) é sempre 9 em celulares brasileiros
    if len(chave_limpa) == 11 and chave_limpa.isdigit():
        if chave_limpa[2] == '9':
            return "telefone"
        return "cpf"
    # 10 ou 13 dígitos numéricos = provavelmente telefone
    if len(chave_limpa) in (10, 13) and chave_limpa.isdigit():
        return "telefone"
    return "aleatoria"


def _resposta_sim(texto: str) -> bool:
    """Detecta se o cidadão respondeu SIM (aceita variações)."""
    t = texto.strip().lower().rstrip("!.")
    return t in ("sim", "s", "quero", "aceito", "pode", "pode sim", "claro", "bora", "yes", "1")


def _resposta_nao(texto: str) -> bool:
    """Detecta se o cidadão respondeu NÃO."""
    t = texto.strip().lower().rstrip("!.")
    return t in ("nao", "não", "n", "nope", "não quero", "nao quero", "não aceito", "2")


def _buscar_dados_anteriores(sb: Client, telefone: str) -> dict | None:
    """
    Verifica se esse telefone já tem CPF e PIX cadastrados de uma denúncia anterior.
    Se sim, retorna os dados encriptados pra reutilizar (evita pedir de novo).
    """
    try:
        result = sb.table("recompensas").select(
            "cpf_encrypted, chave_pix_encrypted, tipo_chave_pix, denuncia_id"
        ).order("created_at", desc=True).limit(10).execute()

        if not result.data:
            return None

        # Procura uma recompensa vinculada a uma denúncia desse telefone
        for recomp in result.data:
            den = sb.table("denuncias").select("telefone").eq(
                "id", recomp["denuncia_id"]).execute()
            if den.data and den.data[0].get("telefone") == telefone:
                if recomp.get("cpf_encrypted") and recomp.get("chave_pix_encrypted"):
                    return {
                        "cpf_encrypted": recomp["cpf_encrypted"],
                        "chave_pix_encrypted": recomp["chave_pix_encrypted"],
                        "tipo_chave_pix": recomp["tipo_chave_pix"],
                    }
        return None
    except Exception as exc:
        logger.error(f"Erro ao buscar dados anteriores: {exc}")
        return None


def _extrair_bairro_endereco(texto: str) -> tuple[str, str]:
    """
    Tenta separar bairro do endereço.
    Ex: "Rua Marina 353 bairro Alvorada" → ("Alvorada", "Rua Marina 353")
    Ex: "Rua Marina 353, Alvorada" → ("Alvorada", "Rua Marina 353")
    Ex: "Zona 7" → ("Zona 7", "Zona 7")
    """
    texto_limpo = texto.strip()

    # Tenta separar por "bairro"
    import re
    match = re.search(r'[,\s]+bairro\s+(.+)', texto_limpo, re.IGNORECASE)
    if match:
        bairro = match.group(1).strip().rstrip(".")
        endereco = texto_limpo[:match.start()].strip().rstrip(",")
        return (bairro, endereco)

    # Tenta separar por vírgula (último trecho após vírgula = bairro)
    if "," in texto_limpo:
        partes = [p.strip() for p in texto_limpo.rsplit(",", 1)]
        if len(partes) == 2 and partes[1]:
            return (partes[1], partes[0])

    # Tenta separar por " - " (traço)
    if " - " in texto_limpo:
        partes = [p.strip() for p in texto_limpo.rsplit(" - ", 1)]
        if len(partes) == 2 and partes[1]:
            return (partes[1], partes[0])

    # Não conseguiu separar — usa texto inteiro como endereço, bairro vazio
    return ("", texto_limpo)


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
        resultado = _continuar_denuncia(event, sb)
        if resultado is None:
            # Nova intenção detectada — reprocessar como mensagem nova
            event_novo = {**event, "is_continuacao": False, "sessao": None}
            processar_denuncia(event_novo, sb)
        return

    # ── CLASSIFICAÇÃO POR IMAGEM — confirmar ou mostrar menu ──
    if classificacao.get("classificacao_por_imagem"):
        confianca = classificacao.get("confianca", 0)
        categoria_img = classificacao.get("categoria", "")
        categoria_display = classificacao.get("categoria_display", categoria_img.replace("_", " "))
        icone = _ICONE_CATEGORIA.get(categoria_img, "📸")

        # Upload da imagem pra storage antecipadamente (pra não perder)
        midia_url_temp = None
        if event.get("tem_midia") and (event.get("media_base64") or event.get("message_id")):
            temp_id = str(uuid.uuid4())
            file_bytes = download_media(event.get("message_id", ""), event.get("media_base64", ""))
            if file_bytes:
                midia_url_temp = upload_to_storage(sb, file_bytes, temp_id,
                                                   event.get("tipo_midia", "imagem"),
                                                   event.get("mimetype"))
                logger.info(f"📸 Imagem pré-uploadada: {midia_url_temp}")

        if confianca >= 70:
            # Confiança alta — pedir confirmação
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "denuncia", "aguardando_confirmacao_imagem", placeholder_id, {
                "push_name": push_name,
                "categoria": categoria_img,
                "categoria_display": categoria_display,
                "mensagem_original": texto,
                "midia_url_temp": midia_url_temp,
                "resumo": classificacao.get("resumo", ""),
                "confianca": confianca,
                "classificacao": classificacao,
                "_placeholder": True,
            })
            resposta = (f"📸 Analisei a imagem!\n\n"
                        f"Identifiquei como: {icone} *{categoria_display}*\n\n"
                        f"Tá certo?\n"
                        f"1️⃣ Sim, é isso\n"
                        f"2️⃣ Não, é outra coisa")
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            logger.info(f"📸 Confirmação imagem enviada: {categoria_img} (confiança {confianca}%)")
            return
        else:
            # Confiança baixa — mostra menu de categorias
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "denuncia", "aguardando_categoria", placeholder_id, {
                "push_name": push_name,
                "mensagem_original": texto,
                "midia_url_temp": midia_url_temp,
                "_placeholder": True,
            })
            menu = _montar_menu_categorias()
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, menu))
            logger.info(f"📸 Imagem com confiança baixa ({confianca}%) — menu enviado")
            return

    # ── DENÚNCIA GENÉRICA — envia menu de categorias ──
    categoria = classificacao.get("categoria", "generica")
    if categoria == "generica":
        menu = _montar_menu_categorias()
        # Cria sessão aguardando escolha (sem criar registro ainda)
        # IMPORTANTE: registro_id não pode ser vazio — usa placeholder UUID
        placeholder_id = str(uuid.uuid4())
        criar_sessao(sb, telefone, "denuncia", "aguardando_categoria", placeholder_id,
                     {"push_name": push_name, "mensagem_original": texto,
                      "_placeholder": True})
        enviar_whatsapp(telefone, _com_aviso_truncagem(event, menu))
        logger.info(f"Menu de categorias enviado para {telefone}")
        return

    # ── NOVA DENUNCIA (categoria já definida pela IA) ──
    tem_midia = event.get("tem_midia", False)
    tem_loc = event.get("tem_localizacao", False)

    # ── BUG 2 FIX: Se NÃO tem mídia, NÃO gera protocolo ainda ──
    # Cria sessão aguardando mídia sem registro no banco.
    # O protocolo e registro só são criados quando a foto/vídeo chegar.
    if not tem_midia:
        placeholder_id = str(uuid.uuid4())
        criar_sessao(sb, telefone, "denuncia", "aguardando_midia", placeholder_id,
                     {"push_name": push_name, "mensagem_original": texto,
                      "categoria": categoria, "_placeholder": True})
        cat_label = categoria.replace("_", " ")
        resposta = (f"✅ Recebido, {push_name or 'cidadão'}! Sua denúncia de *{cat_label}* "
                    f"foi identificada.\n\n"
                    f"📸 Agora envie uma *foto ou vídeo* como evidência.\n"
                    f"Isso é essencial para registrar a denúncia e gerar seu protocolo.\n\n"
                    f"_Aguardando sua evidência..._")
        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
        logger.info(f"Aguardando mídia de {telefone} para criar denúncia ({categoria})")
        return

    # ── Tem mídia na primeira mensagem — cria registro completo ──
    protocolo = gerar_protocolo(sb)

    # Classificar origem da foto (red flag)
    foto_info = classificar_foto_origem(event)
    logger.info(f"📷 Classificação foto: {foto_info}")

    insert_data = {
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "mensagem": texto,
        "status": "novo",
        "foto_origem": foto_info["foto_origem"],
        "foto_flag": foto_info["foto_flag"],
        "foto_flag_motivo": foto_info["foto_flag_motivo"],
    }
    if foto_info["foto_flag"] != "none":
        logger.info(f"🚩 Red flag detectada: {foto_info['foto_flag']} — {foto_info['foto_flag_motivo']}")

    # Salvar localização se veio junto
    if tem_loc and event.get("latitude"):
        insert_data["latitude"] = event["latitude"]
        insert_data["longitude"] = event["longitude"]
        endereco_geo, bairro_geo = _geocodificar_sync(event["latitude"], event["longitude"])
        if endereco_geo:
            insert_data["endereco"] = endereco_geo
        if bairro_geo:
            insert_data["bairro"] = bairro_geo
        else:
            insert_data["bairro"] = f"GPS: {event['latitude']:.4f}, {event['longitude']:.4f}"

    res = sb.table("denuncias").insert(insert_data).execute()

    if not res.data:
        logger.error(f"Falha ao criar denuncia")
        return

    registro_id = res.data[0]["id"]
    logger.info(f"Denuncia criada: {protocolo} ({categoria})")

    # Processar mídia (upload para storage)
    erro_midia = processar_midia(event, sb, registro_id, "denuncias")
    if erro_midia:
        enviar_whatsapp(telefone, erro_midia)

    if not tem_loc:
        etapa = "aguardando_endereco"
        resposta = (f"✅ Evidência recebida! Agora preciso da localização.\n\n"
                    f"📍 Envie o endereço ou clique em: 📎 > Localização\n\n"
                    f"📋 Protocolo: {protocolo}")
    else:
        # Denúncia completa — checar se é elegível pro Cidadão Ativo
        valor = _buscar_valor_recompensa(sb, categoria)
        if valor:
            dados_ant = _buscar_dados_anteriores(sb, telefone)
            if dados_ant:
                # Marcar como elegível + salvar dados na denúncia (NÃO cria recompensa ainda)
                sb.table("denuncias").update({
                    "cidadania_ativa": True,
                    "valor_recompensa": valor,
                    "cpf_encrypted": dados_ant["cpf_encrypted"],
                    "dados_bancarios_encrypted": dados_ant["chave_pix_encrypted"],
                }).eq("id", registro_id).execute()
                etapa = "finalizado"
                resposta = (f"✅ Denúncia registrada com sucesso!\n\n"
                            f"💰 *Programa Cidadão Ativo*\n"
                            f"Sua denúncia é elegível a *R$ {valor:.2f}*.\n"
                            f"Após validação pela equipe, o pagamento será processado.\n\n"
                            f"📋 Protocolo: {protocolo}")
            else:
                etapa = "aguardando_cidadania"
                resposta = (f"✅ Denúncia registrada com sucesso!\n\n"
                            f"💰 *Programa Cidadão Ativo*\n"
                            f"Sua denúncia de *{categoria.replace('_', ' ')}* é elegível "
                            f"a uma recompensa de *R$ {valor:.2f}*.\n\n"
                            f"Deseja se cadastrar para receber? "
                            f"Seus dados ficam protegidos e só o setor financeiro terá acesso.\n\n"
                            f"Responda *SIM* ou *NÃO*")
        else:
            etapa = "finalizado"
            resposta = (f"✅ Denúncia completa registrada!\n\n"
                        f"A equipe já foi notificada e vai investigar.\n\n"
                        f"📋 Protocolo: {protocolo}")

    criar_sessao(sb, telefone, "denuncia", etapa, registro_id,
                 {"protocolo": protocolo, "categoria": categoria})

    if etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))


def _continuar_denuncia(event: dict, sb: Client):
    """Retorna None se detectar nova intenção (sinaliza para reprocessar como nova)."""
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    registro_id = sessao.get("registro_id") if sessao else None
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    protocolo = contexto.get("protocolo", "")
    categoria = contexto.get("categoria", "")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "") or contexto.get("push_name", "")

    logger.info(f"Continuando denuncia: tel={telefone} etapa={etapa_atual} texto={texto[:50] if texto else '[vazio]'}")

    # ── DETECÇÃO DE NOVA INTENÇÃO (aguardando_cpf) ──
    # Se o texto não parece CPF e é longo, provavelmente é uma nova denúncia/ocorrência
    if etapa_atual == "aguardando_cpf" and texto and _detectar_nova_intencao_cpf(texto):
        logger.info(f"Texto não parece CPF e é longo demais. Nova intenção: {texto[:50]}")
        finalizar_sessao(sb, telefone)
        return None  # Sinaliza para reprocessar como mensagem nova

    # Proteção: se algo crashar, o cidadão recebe uma mensagem em vez de ficar no vácuo
    try:
        _executar_continuacao_denuncia(event, sb, sessao, telefone, contexto,
                                       registro_id, etapa_atual, protocolo,
                                       categoria, texto, push_name)
    except Exception as exc:
        logger.exception(f"ERRO em _continuar_denuncia para {telefone}: {exc}")
        enviar_whatsapp(telefone,
                        "⚠️ Ocorreu um erro ao processar sua mensagem. "
                        "Por favor, tente enviar novamente.")
    return True  # Processado com sucesso — NÃO reprocessar


def _executar_continuacao_denuncia(event, sb, sessao, telefone, contexto,
                                    registro_id, etapa_atual, protocolo,
                                    categoria, texto, push_name) -> None:
    """Lógica real da continuação — separada pra ter try/except no caller."""

    # ══════════════════════════════════════════════════════════
    # ETAPA CONFIRMAÇÃO IMAGEM — cidadão confirma classificação da foto
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_confirmacao_imagem":
        if _resposta_sim(texto):
            # Cidadão confirmou — criar registro com a imagem pré-uploadada
            cat = contexto.get("categoria", "pichacao")
            midia_url_temp = contexto.get("midia_url_temp")
            mensagem_original = contexto.get("mensagem_original", "")

            protocolo = gerar_protocolo(sb)

            insert_data = {
                "protocolo": protocolo,
                "telefone": telefone,
                "nome": push_name or None,
                "categoria": cat,
                "mensagem": contexto.get("resumo") or mensagem_original or "Denúncia por imagem",
                "status": "novo",
                "midia_urls": [midia_url_temp] if midia_url_temp else [],
            }

            res = sb.table("denuncias").insert(insert_data).execute()
            if not res.data:
                logger.error("Falha ao criar denúncia confirmada por imagem")
                enviar_whatsapp(telefone, "Desculpe, ocorreu um erro. Tente novamente.")
                return
            registro_id = res.data[0]["id"]
            contexto["protocolo"] = protocolo
            contexto["categoria"] = cat
            contexto.pop("_placeholder", None)

            nova_etapa = "aguardando_endereco"
            resposta = (f"✅ Denúncia registrada!\n\n"
                        f"📍 Agora me diz o endereço ou envia sua localização: 📎 > Localização\n\n"
                        f"📋 Protocolo: {protocolo}")
            criar_sessao(sb, telefone, "denuncia", nova_etapa, registro_id, contexto)
            enviar_whatsapp(telefone, resposta)
            logger.info(f"📸 Denúncia confirmada por imagem: {protocolo} ({cat})")
            return

        elif _resposta_nao(texto):
            # Cidadão negou — mostrar menu de categorias
            midia_url_temp = contexto.get("midia_url_temp")
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "denuncia", "aguardando_categoria", placeholder_id, {
                "push_name": push_name,
                "mensagem_original": contexto.get("mensagem_original", ""),
                "midia_url_temp": midia_url_temp,
                "_placeholder": True,
            })
            menu = _montar_menu_categorias()
            enviar_whatsapp(telefone, menu)
            logger.info(f"📸 Cidadão negou classificação de imagem — menu enviado")
            return

        else:
            # Não entendeu — reenvia pergunta
            cat_display = contexto.get("categoria_display", "")
            icone = _ICONE_CATEGORIA.get(contexto.get("categoria", ""), "📸")
            criar_sessao(sb, telefone, "denuncia", etapa_atual, registro_id, contexto)
            resposta = (f"Não entendi. A foto parece ser: {icone} *{cat_display}*\n\n"
                        f"Responda:\n1️⃣ *Sim*, é isso\n2️⃣ *Não*, é outra coisa")
            enviar_whatsapp(telefone, resposta)
            return

    # ══════════════════════════════════════════════════════════
    # ETAPA MENU — cidadão está escolhendo a categoria
    # (registro_id ainda não existe, será criado aqui)
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_categoria":
        cat_escolhida = _identificar_categoria_menu(texto)
        if not cat_escolhida:
            # Não entendeu — reenvia menu
            resposta = "Não entendi. Por favor, responda com o *número* da opção:\n\n" + _montar_menu_categorias()
            criar_sessao(sb, telefone, "denuncia", "aguardando_categoria",
                         registro_id or str(uuid.uuid4()), contexto)
            enviar_whatsapp(telefone, resposta)
            return

        # Categoria escolhida!
        mensagem_original = contexto.get("mensagem_original", texto)
        cat_label = cat_escolhida.replace("_", " ")
        for _, cat_id, label, _ in MENU_CATEGORIAS:
            if cat_id == cat_escolhida:
                cat_label = label
                break

        # Se já tem imagem pré-uploadada (veio da classificação por imagem),
        # pula a etapa de mídia e cria registro direto
        midia_url_temp = contexto.get("midia_url_temp")
        if midia_url_temp:
            protocolo = gerar_protocolo(sb)
            insert_data = {
                "protocolo": protocolo,
                "telefone": telefone,
                "nome": push_name or None,
                "categoria": cat_escolhida,
                "mensagem": mensagem_original or f"Denúncia de {cat_label}",
                "status": "novo",
                "midia_urls": [midia_url_temp],
            }
            res = sb.table("denuncias").insert(insert_data).execute()
            if not res.data:
                enviar_whatsapp(telefone, "Desculpe, ocorreu um erro. Tente novamente.")
                return
            novo_registro_id = res.data[0]["id"]
            criar_sessao(sb, telefone, "denuncia", "aguardando_endereco", novo_registro_id, {
                "push_name": push_name, "protocolo": protocolo, "categoria": cat_escolhida,
            })
            resposta = (f"✅ Registrado como *{cat_label}*!\n\n"
                        f"📍 Agora me diz o endereço ou envia sua localização: 📎 > Localização\n\n"
                        f"📋 Protocolo: {protocolo}")
            enviar_whatsapp(telefone, resposta)
            logger.info(f"📸 Denúncia criada com imagem pré-uploadada: {protocolo} ({cat_escolhida})")
            return

        # Sem imagem pré-uploadada — aguardar mídia normalmente
        placeholder_id = str(uuid.uuid4())
        etapa = "aguardando_midia"
        resposta = (f"✅ Registrado como *{cat_label}*!\n\n"
                    f"📸 Agora envie uma *foto ou vídeo* como evidência.\n"
                    f"Isso é essencial para gerar seu protocolo.\n\n"
                    f"_Aguardando sua evidência..._")

        criar_sessao(sb, telefone, "denuncia", etapa, placeholder_id,
                     {"push_name": push_name, "mensagem_original": mensagem_original,
                      "categoria": cat_escolhida, "_placeholder": True})
        enviar_whatsapp(telefone, resposta)
        logger.info(f"Menu: categoria={cat_escolhida}, aguardando mídia de {telefone}")
        return

    if not registro_id:
        logger.error("Continuacao sem registro_id")
        return

    update_data = {}
    tem_midia = event.get("tem_midia", False)
    tem_loc = event.get("tem_localizacao", False)
    texto = event.get("texto", "")

    # ══════════════════════════════════════════════════════════
    # ETAPAS DO CIDADÃO ATIVO (novas)
    # ══════════════════════════════════════════════════════════

    if etapa_atual == "aguardando_cidadania":
        # Cidadão respondeu SIM ou NÃO ao Programa Cidadão Ativo
        if _resposta_sim(texto):
            nova_etapa = "aguardando_cpf"
            contexto["cidadania_aceita"] = True
            resposta = (f"Ótimo! Seus dados são protegidos por criptografia "
                        f"e só o setor financeiro terá acesso.\n\n"
                        f"📝 Por favor, me envie seu *CPF* (só números, ex: 12345678900)")
        elif _resposta_nao(texto):
            nova_etapa = "finalizado"
            resposta = (f"Tudo bem! Sua denúncia continua registrada e será investigada normalmente.\n\n"
                        f"Obrigado por ajudar Maringá! 🏙️\n"
                        f"📋 Protocolo: {protocolo}")
        else:
            # Não entendeu — pede de novo
            nova_etapa = etapa_atual
            resposta = (f"Não entendi. Por favor, responda *SIM* para participar "
                        f"do Programa Cidadão Ativo ou *NÃO* para continuar sem cadastro.")

        criar_sessao(sb, telefone, "denuncia", nova_etapa, registro_id, contexto)
        if nova_etapa == "finalizado":
            finalizar_sessao(sb, telefone)
        enviar_whatsapp(telefone, resposta)
        return

    if etapa_atual == "aguardando_cpf":
        # Cidadão enviou o CPF
        cpf_limpo = texto.strip().replace(".", "").replace("-", "").replace(" ", "")

        if not cpf_limpo.isdigit():
            # Texto não é numérico — responde com instrução
            nova_etapa = etapa_atual
            resposta = ("⚠️ CPF inválido. Por favor, envie apenas os 11 números.\n"
                        "Exemplo: *12345678900*")
        elif len(cpf_limpo) != 11:
            # Número de dígitos errado
            nova_etapa = etapa_atual
            resposta = (f"⚠️ CPF inválido ({len(cpf_limpo)} dígitos). "
                        f"Por favor, envie os 11 números.\n"
                        f"Exemplo: *12345678900*")
        elif not _validar_cpf(cpf_limpo):
            # 11 dígitos mas dígitos verificadores incorretos
            nova_etapa = etapa_atual
            resposta = ("⚠️ CPF inválido. Verifique os números e tente novamente.\n"
                        "Exemplo: *12345678900*")
        else:
            # CPF válido!
            contexto["cpf"] = cpf_limpo
            nova_etapa = "aguardando_pix"
            resposta = (f"✅ CPF recebido!\n\n"
                        f"Agora me envie sua *chave PIX*.\n"
                        f"Pode ser: CPF, e-mail, telefone ou chave aleatória.")

        criar_sessao(sb, telefone, "denuncia", nova_etapa, registro_id, contexto)
        enviar_whatsapp(telefone, resposta)
        return

    if etapa_atual == "aguardando_pix":
        # Cidadão enviou a chave PIX
        chave_pix = texto.strip()
        if len(chave_pix) < 5:
            resposta = "⚠️ Chave PIX parece inválida. Envie novamente (CPF, e-mail, telefone ou chave aleatória)."
            criar_sessao(sb, telefone, "denuncia", etapa_atual, registro_id, contexto)
            enviar_whatsapp(telefone, resposta)
            return

        cpf = contexto.get("cpf", "")
        tipo_pix = _detectar_tipo_pix(chave_pix)
        valor = _buscar_valor_recompensa(sb, categoria)

        # Salvar CPF/PIX na denúncia + marcar como elegível (NÃO cria recompensa)
        cpf_enc = _encriptar_dado(cpf)
        pix_enc = _encriptar_dado(chave_pix)
        sb.table("denuncias").update({
            "cidadania_ativa": True,
            "valor_recompensa": valor or 0,
            "cpf_encrypted": cpf_enc,
            "dados_bancarios_encrypted": pix_enc,
        }).eq("id", registro_id).execute()
        if valor:
            nova_etapa = "finalizado"
            resposta = (f"✅ *Cadastro no Cidadão Ativo concluído!*\n\n"
                        f"📋 Protocolo: {protocolo}\n"
                        f"💰 Valor: R$ {valor:.2f}\n"
                        f"🔐 Seus dados estão protegidos por criptografia\n\n"
                        f"Quando sua denúncia for validada pela equipe, "
                        f"o pagamento será feito via PIX.\n\n"
                        f"Obrigado por ajudar Maringá! 🏙️")
            logger.info(f"Cidadão Ativo cadastrado (aguardando validação): {protocolo} (R$ {valor})")
        else:
            nova_etapa = "finalizado"
            resposta = (f"Ocorreu um erro ao processar seu cadastro, mas "
                        f"sua denúncia continua registrada.\n\n"
                        f"📋 Protocolo: {protocolo}\n"
                        f"Obrigado por ajudar Maringá! 🏙️")

        criar_sessao(sb, telefone, "denuncia", nova_etapa, registro_id, contexto)
        finalizar_sessao(sb, telefone)
        enviar_whatsapp(telefone, resposta)
        return

    # ══════════════════════════════════════════════════════════
    # ETAPAS NORMAIS DA DENÚNCIA (existentes)
    # ══════════════════════════════════════════════════════════

    if tem_midia and etapa_atual == "aguardando_midia":
        # ── BUG 2 FIX: Se registro_id é placeholder, criar o registro agora ──
        is_placeholder = contexto.get("_placeholder", False)
        if is_placeholder:
            mensagem_original = contexto.get("mensagem_original", texto)
            cat = contexto.get("categoria", categoria) or categoria
            protocolo = gerar_protocolo(sb)

            # Classificar origem da foto (red flag) — BUG 1 FIX
            foto_info = classificar_foto_origem(event)
            logger.info(f"📷 Classificação foto (continuação): {foto_info}")

            insert_data_new = {
                "protocolo": protocolo,
                "telefone": telefone,
                "nome": push_name or None,
                "categoria": cat,
                "mensagem": mensagem_original,
                "status": "novo",
                "foto_origem": foto_info["foto_origem"],
                "foto_flag": foto_info["foto_flag"],
                "foto_flag_motivo": foto_info["foto_flag_motivo"],
            }
            if foto_info["foto_flag"] != "none":
                logger.info(f"🚩 Red flag detectada: {foto_info['foto_flag']} — {foto_info['foto_flag_motivo']}")

            res = sb.table("denuncias").insert(insert_data_new).execute()
            if not res.data:
                logger.error("Falha ao criar denuncia na etapa aguardando_midia")
                enviar_whatsapp(telefone, "Desculpe, ocorreu um erro. Tente novamente.")
                return
            registro_id = res.data[0]["id"]
            categoria = cat
            contexto["protocolo"] = protocolo
            contexto["categoria"] = categoria
            contexto.pop("_placeholder", None)
            logger.info(f"Denuncia criada ao receber mídia: {protocolo} ({categoria})")
        else:
            # Registro já existe — atualizar red flag com os metadados da foto
            foto_info = classificar_foto_origem(event)
            logger.info(f"📷 Classificação foto (update): {foto_info}")
            update_data["foto_origem"] = foto_info["foto_origem"]
            update_data["foto_flag"] = foto_info["foto_flag"]
            update_data["foto_flag_motivo"] = foto_info["foto_flag_motivo"]
            if foto_info["foto_flag"] != "none":
                logger.info(f"🚩 Red flag detectada: {foto_info['foto_flag']} — {foto_info['foto_flag_motivo']}")

        erro_midia = processar_midia(event, sb, registro_id, "denuncias")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        update_data["status"] = "novo"
        nova_etapa = "aguardando_endereco"
        resposta = (f"📸 Evidência recebida! Obrigado.\n\n"
                    f"📍 Agora me diz o endereço ou envia sua localização: 📎 > Localização\n\n"
                    f"📋 Protocolo: {protocolo}")

    elif tem_loc:
        lat = event.get("latitude")
        lng = event.get("longitude")
        update_data["latitude"] = lat
        update_data["longitude"] = lng
        endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
        if endereco_geo:
            update_data["endereco"] = endereco_geo
        if bairro_geo:
            update_data["bairro"] = bairro_geo
        else:
            update_data["bairro"] = f"GPS: {lat:.4f}, {lng:.4f}"
        # Checar se é elegível ao Cidadão Ativo antes de finalizar
        valor = _buscar_valor_recompensa(sb, categoria)
        if valor:
            dados_ant = _buscar_dados_anteriores(sb, telefone)
            if dados_ant:
                sb.table("denuncias").update({
                    "cidadania_ativa": True, "valor_recompensa": valor,
                    "cpf_encrypted": dados_ant["cpf_encrypted"],
                    "dados_bancarios_encrypted": dados_ant["chave_pix_encrypted"],
                }).eq("id", registro_id).execute()
                nova_etapa = "finalizado"
                resposta = (f"📍 Localização registrada!\n\n"
                            f"💰 *Programa Cidadão Ativo* — Elegível a *R$ {valor:.2f}*!\n"
                            f"Após validação pela equipe, o pagamento será processado.\n\n"
                            f"📋 Protocolo: {protocolo}")
            else:
                nova_etapa = "aguardando_cidadania"
                resposta = (f"📍 Localização registrada!\n\n"
                            f"💰 *Programa Cidadão Ativo*\n"
                            f"Sua denúncia de *{categoria.replace('_', ' ')}* é elegível "
                            f"a uma recompensa de *R$ {valor:.2f}*.\n\n"
                            f"Deseja se cadastrar para receber? "
                            f"Seus dados ficam protegidos e só o setor financeiro terá acesso.\n\n"
                            f"Responda *SIM* ou *NÃO*")
        else:
            nova_etapa = "finalizado"
            resposta = (f"📍 Localização registrada!\n\n"
                        f"✅ Denúncia completa. A equipe já foi notificada.\n"
                        f"📋 Protocolo: {protocolo}")

    elif texto and etapa_atual == "aguardando_endereco":
        # Separar bairro do endereço
        bairro, endereco = _extrair_bairro_endereco(texto)
        update_data["endereco"] = endereco or texto
        if bairro:
            update_data["bairro"] = bairro
        # Checar se é elegível ao Cidadão Ativo antes de finalizar
        valor = _buscar_valor_recompensa(sb, categoria)
        if valor:
            dados_ant = _buscar_dados_anteriores(sb, telefone)
            if dados_ant:
                sb.table("denuncias").update({
                    "cidadania_ativa": True, "valor_recompensa": valor,
                    "cpf_encrypted": dados_ant["cpf_encrypted"],
                    "dados_bancarios_encrypted": dados_ant["chave_pix_encrypted"],
                }).eq("id", registro_id).execute()
                nova_etapa = "finalizado"
                resposta = (f"📍 Endereço registrado: {texto}\n\n"
                            f"💰 *Programa Cidadão Ativo* — Elegível a *R$ {valor:.2f}*!\n"
                            f"Após validação pela equipe, o pagamento será processado.\n\n"
                            f"📋 Protocolo: {protocolo}")
            else:
                nova_etapa = "aguardando_cidadania"
                resposta = (f"📍 Endereço registrado: {texto}\n\n"
                            f"💰 *Programa Cidadão Ativo*\n"
                            f"Sua denúncia de *{categoria.replace('_', ' ')}* é elegível "
                            f"a uma recompensa de *R$ {valor:.2f}*.\n\n"
                            f"Deseja se cadastrar para receber? "
                            f"Seus dados ficam protegidos e só o setor financeiro terá acesso.\n\n"
                            f"Responda *SIM* ou *NÃO*")
        else:
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

def _salvar_msg_sos(sb: Client, alerta_id: str, telefone: str, nome: str | None,
                    mensagem: str, remetente: str = "cidadao") -> None:
    """Salva uma mensagem no histórico do chat SOS."""
    if not alerta_id or not mensagem:
        return
    try:
        sb.table("sos_mensagens").insert({
            "alerta_id": alerta_id,
            "telefone": telefone,
            "nome": nome,
            "mensagem": mensagem,
            "remetente": remetente,
        }).execute()
    except Exception as exc:
        logger.error(f"Erro ao salvar msg SOS: {exc}")


def processar_sos(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    tem_loc = event.get("tem_localizacao", False)
    classificacao = event.get("classificacao", {})
    categoria_sos = classificacao.get("categoria", "emergencia")
    push_name = event.get("push_name", "")

    # ── CADASTRO — mulher quer se cadastrar no Mulher Segura ──
    if categoria_sos == "cadastro" and not is_continuacao:
        logger.info(f"🛡️ Iniciando cadastro Mulher Segura para {telefone}")
        # Verifica se já tem cadastro
        existente = sb.table("sos_cadastros").select("id").eq("telefone", telefone).execute()
        if existente.data:
            enviar_whatsapp(telefone,
                "Você já está cadastrada no Programa Mulher Segura. 🛡️\n\n"
                "Em caso de emergência, envie apenas um ponto (.) que acionamos ajuda imediata.\n\n"
                "Se precisar atualizar seus dados, envie *atualizar cadastro*.")
            return
        placeholder_id = str(uuid.uuid4())
        criar_sessao(sb, telefone, "sos_mulher", "cadastro_nome", placeholder_id,
                     {"tipo": "cadastro", "push_name": event.get("push_name", "")})
        enviar_whatsapp(telefone,
            "🛡️ *Programa Mulher Segura — Prefeitura de Maringá*\n\n"
            "Vamos fazer seu cadastro sigiloso. Seus dados ficam protegidos e só são acessados em caso de emergência.\n\n"
            "📝 *Qual é o seu nome completo?*")
        return

    # ── CONTINUAÇÃO de cadastro ──
    if is_continuacao:
        sessao = event.get("sessao", {})
        contexto = sessao.get("contexto") or {}
        etapa = sessao.get("etapa", "")

        # Continuação de cadastro
        if contexto.get("tipo") == "cadastro":
            _continuar_cadastro_sos(event, sb, sessao)
            return

        # Continuação de SOS ativo — recebeu localização GPS
        registro_id = sessao.get("registro_id") if sessao else None
        if tem_loc:
            if registro_id:
                sb.table("sos_alertas").update({
                    "latitude": event.get("latitude"),
                    "longitude": event.get("longitude"),
                }).eq("id", registro_id).execute()
                _salvar_msg_sos(sb, registro_id, telefone, push_name,
                                f"📍 Localização GPS enviada: {event.get('latitude')}, {event.get('longitude')}")
                logger.warning(f"🚨 SOS localizacao GPS atualizada para {telefone}")
            enviar_whatsapp(telefone, "📍 Localização recebida. Equipe a caminho. Mantenha-se segura.")
            finalizar_sessao(sb, telefone)
            return

        # Continuação de SOS ativo — recebeu endereço por texto
        if texto and len(texto) >= 3:
            logger.warning(f"🚨 SOS endereço texto de {telefone}: {texto[:80]}")
            # Tenta geocodificar o endereço pra obter coordenadas
            update_data = {}
            try:
                geo_url = (
                    f"https://api.mapbox.com/geocoding/v5/mapbox.places/"
                    f"{texto}, Maringá, Paraná, Brasil.json"
                    f"?access_token=pk.eyJ1Ijoibm9kZWRhdGEiLCJhIjoiY21tejgxMm1hMDVxajJ3cTU2Z3ZrNTBiZSJ9.t6vT60mOCmGpYrHfRSykrw"
                    f"&limit=1&language=pt"
                )
                geo_res = httpx.get(geo_url, timeout=10)
                geo_data = geo_res.json()
                if geo_data.get("features"):
                    coords = geo_data["features"][0]["center"]
                    update_data["latitude"] = coords[1]
                    update_data["longitude"] = coords[0]
                    logger.info(f"🚨 SOS geocodificado: {texto} → {coords[1]:.5f}, {coords[0]:.5f}")
            except Exception as exc:
                logger.warning(f"Geocoding falhou para SOS: {exc}")

            # Salvar endereço no alerta (e coordenadas se geocodificou)
            if registro_id:
                # Buscar cadastro e atualizar endereço lá também
                try:
                    alerta = sb.table("sos_alertas").select("cadastro_id").eq("id", registro_id).execute()
                    cad_id = alerta.data[0].get("cadastro_id") if alerta.data else None
                    if cad_id:
                        sb.table("sos_cadastros").update({"endereco": texto}).eq("id", cad_id).execute()
                except Exception:
                    pass
                if update_data:
                    sb.table("sos_alertas").update(update_data).eq("id", registro_id).execute()

            if registro_id:
                _salvar_msg_sos(sb, registro_id, telefone, push_name, texto)
            enviar_whatsapp(telefone,
                f"📍 Endereço registrado: *{texto}*\n\n"
                "Equipe a caminho. Mantenha-se segura.\n\n"
                "Se puder, envie também a localização pelo celular (📎 > Localização) para maior precisão.")
            finalizar_sessao(sb, telefone)
            return

        # Mensagem muito curta ou mídia — salva mesmo assim
        if registro_id and texto:
            _salvar_msg_sos(sb, registro_id, telefone, push_name, texto)
        enviar_whatsapp(telefone,
            "✓ Recebido. Para te encontrar, envie:\n\n"
            "📍 Sua *localização* pelo celular (📎 > Localização)\n"
            "ou\n"
            "📝 Seu *endereço completo* por texto (rua, número, bairro)")
        return

    # ── NOVO SOS — emergência ──
    logger.warning(f"🚨🚨🚨 PROCESSANDO SOS de {telefone}")

    # Buscar cadastro
    cad = sb.table("sos_cadastros").select("id,nome").eq("telefone", telefone).execute()
    cadastro_id = cad.data[0]["id"] if cad.data else None
    nome_cadastro = cad.data[0]["nome"] if cad.data else None

    # DEDUPLICAR: se já tem alerta ativo do mesmo telefone, apenas atualizar
    existente = sb.table("sos_alertas").select("id").eq("telefone", telefone) \
        .in_("status", ["active", "attending"]).execute()
    if existente.data:
        registro_id = existente.data[0]["id"]
        logger.warning(f"🚨 SOS duplicado de {telefone} — atualizando alerta {registro_id}")
        update_data = {"codigo_usado": texto[:50] if texto else "sem_texto"}
        if event.get("latitude"):
            update_data["latitude"] = event.get("latitude")
            update_data["longitude"] = event.get("longitude")
        sb.table("sos_alertas").update(update_data).eq("id", registro_id).execute()
        enviar_whatsapp(telefone, "✓ Recebido. Equipe já foi acionada. Mantenha-se segura.")
        return

    # Gerar token único para rastreamento GPS
    token_rastreamento = secrets.token_urlsafe(8)[:10]

    # Criar novo alerta (com token de rastreamento)
    res = sb.table("sos_alertas").insert({
        "telefone": telefone,
        "codigo_usado": texto[:50] if texto else "sem_texto",
        "cadastro_id": cadastro_id,
        "status": "active",
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
        "token_rastreamento": token_rastreamento,
    }).execute()

    if res.data:
        registro_id = res.data[0]["id"]
        logger.warning(f"🚨 SOS ALERTA CRIADO (id={registro_id})")
        _salvar_msg_sos(sb, registro_id, telefone, push_name or nome_cadastro,
                        texto or "[Código SOS]")
        criar_sessao(sb, telefone, "sos_mulher", "aguardando_localizacao", registro_id,
                     {"tipo": "emergencia"})

        # Criar sessão de rastreamento GPS
        try:
            sb.table("emergencia_sessoes").insert({
                "token": token_rastreamento,
                "alerta_id": registro_id,
                "telefone": telefone,
                "nome": nome_cadastro or "Não identificada",
                "status": "ativa",
            }).execute()
            logger.info(f"📍 Sessão GPS criada (token={token_rastreamento})")
        except Exception as e:
            logger.error(f"Erro ao criar sessão GPS: {e}")

        # Enviar confirmação + link de rastreamento
        DOMINIO = "maringa.nodedata.com.br"
        link_rastreamento = f"https://{DOMINIO}/mulher-segura.html?t={token_rastreamento}"

        if nome_cadastro:
            enviar_whatsapp(telefone,
                f"✓ {nome_cadastro}, recebemos seu alerta. Equipe acionada.\n"
                "Se puder, envie sua localização: 📎 > Localização")
        else:
            enviar_whatsapp(telefone,
                "✓ Recebido. Equipe acionada.\n"
                "Se puder, envie sua localização: 📎 > Localização")

        # Link discreto de rastreamento GPS
        enviar_whatsapp(telefone, f"📍 {link_rastreamento}")


def _continuar_cadastro_sos(event: dict, sb: Client, sessao: dict) -> None:
    """Fluxo passo a passo do cadastro Mulher Segura."""
    telefone = event.get("telefone", "desconhecido")
    texto = (event.get("texto") or "").strip()
    etapa = sessao.get("etapa", "")
    contexto = sessao.get("contexto") or {}
    registro_id = sessao.get("registro_id", "")

    if etapa == "cadastro_nome":
        if len(texto) < 3:
            enviar_whatsapp(telefone, "Por favor, informe seu nome completo:")
            return
        contexto["nome"] = texto
        atualizar_sessao(sb, telefone, "cadastro_endereco", contexto)
        enviar_whatsapp(telefone,
            f"Obrigada, {texto}. 🙏\n\n"
            "📍 *Qual é o seu endereço completo?*\n"
            "(Rua, número, bairro — ou envie sua localização pelo 📎)")
        return

    if etapa == "cadastro_endereco":
        tem_loc = event.get("tem_localizacao", False)
        if tem_loc:
            lat = event.get("latitude")
            lng = event.get("longitude")
            endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
            contexto["endereco"] = endereco_geo or f"GPS: {lat}, {lng}"
        elif len(texto) < 5:
            enviar_whatsapp(telefone, "Por favor, informe seu endereço completo (rua, número, bairro):")
            return
        else:
            contexto["endereco"] = texto
        atualizar_sessao(sb, telefone, "cadastro_agressor", contexto)
        enviar_whatsapp(telefone,
            "📋 *Qual o nome do agressor?*\n"
            "(Se preferir não informar agora, envie *pular*)")
        return

    if etapa == "cadastro_agressor":
        if texto.lower() in ("pular", "nao", "não", "n", "prefiro nao", "prefiro não"):
            contexto["agressor"] = None
        else:
            contexto["agressor"] = texto
        atualizar_sessao(sb, telefone, "cadastro_contato", contexto)
        enviar_whatsapp(telefone,
            "👤 *Qual o nome e telefone de uma pessoa de confiança?*\n"
            "(Ex: Minha mãe Maria — 44999001234)\n"
            "Essa pessoa será avisada em caso de emergência.\n\n"
            "Se preferir não informar, envie *pular*")
        return

    if etapa == "cadastro_contato":
        if texto.lower() in ("pular", "nao", "não", "n"):
            contexto["contato_nome"] = None
            contexto["contato_tel"] = None
        else:
            # Tenta separar nome e telefone
            import re
            nums = re.findall(r"\d{10,11}", texto.replace(" ", ""))
            tel_contato = nums[0] if nums else None
            # Remove telefone do texto pra pegar o nome
            nome_contato = re.sub(r"[\d\-\(\)\+\s]{8,}", "", texto).strip(" -—–:")
            if not nome_contato:
                nome_contato = "Contato de confiança"
            contexto["contato_nome"] = nome_contato
            contexto["contato_tel"] = tel_contato

        # ── SALVAR CADASTRO ──
        try:
            # Normaliza telefone (remove + se tiver)
            tel_limpo = telefone.lstrip("+")
            dados_cadastro = {
                "telefone": telefone,
                "nome": contexto.get("nome", ""),
                "endereco": contexto.get("endereco"),
                "agressor": contexto.get("agressor"),
                "contato_confianca_nome": contexto.get("contato_nome"),
                "contato_confianca_telefone": contexto.get("contato_tel"),
                "ativo": True,
            }
            res = sb.table("sos_cadastros").insert(dados_cadastro).execute()
            if res.data:
                logger.info(f"🛡️ Cadastro Mulher Segura criado para {telefone}: {contexto.get('nome')}")
                enviar_whatsapp(telefone,
                    f"✅ *Cadastro realizado com sucesso, {contexto.get('nome')}!*\n\n"
                    "🛡️ Você está protegida pelo Programa Mulher Segura da Prefeitura de Maringá.\n\n"
                    "Em caso de emergência, envie apenas:\n"
                    "• Um ponto: *.*\n"
                    "• Ou a palavra: *socorro*\n\n"
                    "A equipe será acionada imediatamente. 💜\n"
                    "Seus dados são sigilosos e protegidos pela LGPD.")
            else:
                logger.error(f"Falha ao criar cadastro SOS para {telefone}")
                enviar_whatsapp(telefone,
                    "Ocorreu um erro ao salvar seu cadastro. Por favor, tente novamente mais tarde.")
        except Exception as e:
            logger.error(f"Erro ao criar cadastro SOS: {e}")
            enviar_whatsapp(telefone,
                "Ocorreu um erro ao salvar seu cadastro. Por favor, tente novamente mais tarde.")

        finalizar_sessao(sb, telefone)
        return


# ══════════════════════════════════════════════════════════════
# HELPERS — OCORRENCIA (agrupamento, geocodificação, severidade)
# ══════════════════════════════════════════════════════════════

MAPBOX_TOKEN = "pk.eyJ1Ijoibm9kZWRhdGEiLCJhIjoiY21tejgxMm1hMDVxajJ3cTU2Z3ZrNTBiZSJ9.t6vT60mOCmGpYrHfRSykrw"


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos GPS."""
    R = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalizar_endereco(endereco: str) -> str:
    """Remove acentos, lowercase, normaliza abreviações."""
    if not endereco:
        return ""
    nfkd = unicodedata.normalize("NFKD", endereco)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    norm = sem_acento.lower().strip()
    norm = norm.replace("av.", "avenida").replace("r.", "rua").replace("pç.", "praca")
    norm = norm.replace("pca.", "praca").replace("trav.", "travessa")
    return norm


def _geocodificar_sync(latitude: float, longitude: float) -> tuple[str | None, str | None]:
    """Converte coordenadas GPS em endereço legível via Mapbox Geocoding API.
    Retorna (endereco, bairro) ou (None, None) se falhar."""
    if not latitude or not longitude:
        return None, None
    url = (
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{longitude},{latitude}.json"
        f"?access_token={MAPBOX_TOKEN}&language=pt-BR&types=address,neighborhood,locality,place&limit=1"
    )
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("features"):
                feat = data["features"][0]
                endereco = feat.get("place_name", "")
                bairro = ""
                for ctx in feat.get("context", []):
                    if "neighborhood" in ctx.get("id", ""):
                        bairro = ctx.get("text", "")
                        break
                    elif "locality" in ctx.get("id", ""):
                        bairro = ctx.get("text", "")
                if not bairro:
                    for ctx in feat.get("context", []):
                        if "place" in ctx.get("id", ""):
                            bairro = ctx.get("text", "")
                            break
                return endereco, bairro
    except Exception as e:
        logger.error(f"Erro geocodificação: {e}")
    return None, None


def _calcular_severidade(total_relatos: int, severidade_categoria: str = "baixa") -> str:
    """Calcula severidade baseado no número de relatos + categoria.
    A severidade da categoria serve como piso mínimo."""
    ORDEM = {"baixa": 0, "media": 1, "alta": 2, "critica": 3}
    # Severidade por volume de relatos
    if total_relatos >= 10:
        sev_relatos = "critica"
    elif total_relatos >= 5:
        sev_relatos = "alta"
    elif total_relatos >= 3:
        sev_relatos = "media"
    else:
        sev_relatos = "baixa"
    # Retorna a maior entre relatos e categoria
    if ORDEM.get(sev_relatos, 0) >= ORDEM.get(severidade_categoria, 0):
        return sev_relatos
    return severidade_categoria


# Categorias relacionadas — se não achar a exata, busca também nestas
_CATEGORIAS_RELACIONADAS = {
    "incendio": ["incendio", "outros_urbanos"],
    "queda_arvore": ["queda_arvore", "outros_urbanos"],
    "enchente_alagamento": ["enchente_alagamento", "drenagem", "outros_urbanos"],
    "buraco_via": ["buraco_via", "outros_urbanos"],
    "iluminacao_publica": ["iluminacao_publica", "outros_urbanos"],
    "vendaval": ["vendaval", "outros_urbanos"],
    "acidente": ["acidente", "outros_urbanos"],
    "drenagem": ["drenagem", "enchente_alagamento", "outros_urbanos"],
    "outros_urbanos": ["outros_urbanos", "incendio", "enchente_alagamento", "buraco_via", "iluminacao_publica", "vendaval", "acidente", "drenagem", "queda_arvore"],
}


def _buscar_ocorrencia_similar(sb: Client, categoria: str,
                                latitude: float | None = None,
                                longitude: float | None = None,
                                endereco: str | None = None) -> dict | None:
    """Busca ocorrência ATIVA nas últimas 12h que esteja próxima.
    Busca na categoria exata + categorias relacionadas.
    Retorna match exato (GPS <500m) ou match parcial (mesma rua, pode ser outro número)."""
    limite = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()

    # Buscar na categoria exata + relacionadas
    cats = _CATEGORIAS_RELACIONADAS.get(categoria, [categoria, "outros_urbanos"])
    cats_uniq = list(set(cats))

    result = sb.table("ocorrencias").select(
        "id, protocolo, latitude, longitude, endereco_normalizado, endereco, total_relatos, titulo, bairro, severidade, categoria"
    ).in_("categoria", cats_uniq).neq(
        "status", "resolvido"
    ).gte("created_at", limite).execute()

    if not result.data:
        return None

    end_norm = _normalizar_endereco(endereco) if endereco else ""

    for oc in result.data:
        # Critério 1: GPS próximo (< 500 metros) — match direto
        if latitude and longitude and oc.get("latitude") and oc.get("longitude"):
            dist = _haversine(latitude, longitude, oc["latitude"], oc["longitude"])
            if dist < 500:
                logger.info(f"Agrupamento GPS: {dist:.0f}m de {oc['protocolo']}")
                return oc

        # Critério 2: Endereço normalizado similar
        if end_norm and len(end_norm) > 4 and oc.get("endereco_normalizado"):
            oc_norm = oc["endereco_normalizado"]
            # Substring match (ex: "rua jose bonifacio" in "rua jose bonifacio 354, maringa...")
            if end_norm in oc_norm or oc_norm in end_norm:
                logger.info(f"Agrupamento endereço substring: '{end_norm}' ~ '{oc_norm}' → {oc['protocolo']}")
                return oc
            # Palavras-chave em comum (≥2 palavras significativas > 2 chars)
            palavras_end = set(end_norm.split())
            palavras_oc = set(oc_norm.split())
            palavras_sig = {p for p in (palavras_end & palavras_oc) if len(p) > 2}
            if len(palavras_sig) >= 2:
                logger.info(f"Agrupamento palavras-chave: {palavras_sig} → {oc['protocolo']}")
                return oc

    return None


def _buscar_ocorrencia_mesma_rua(sb: Client, categoria: str,
                                  endereco: str | None = None) -> dict | None:
    """Busca ocorrência na MESMA RUA (nome da rua) mas possivelmente em número diferente.
    Retorna match parcial para perguntar ao cidadão se é o mesmo caso."""
    if not endereco:
        return None
    limite = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    cats = _CATEGORIAS_RELACIONADAS.get(categoria, [categoria])

    result = sb.table("ocorrencias").select(
        "id, protocolo, latitude, longitude, endereco_normalizado, endereco, total_relatos, titulo, bairro, severidade, categoria"
    ).in_("categoria", list(set(cats))).neq(
        "status", "resolvido"
    ).gte("created_at", limite).execute()

    if not result.data:
        return None

    end_norm = _normalizar_endereco(endereco)
    if not end_norm or len(end_norm) < 5:
        return None

    # Extrair nome da rua (sem números)
    import re
    rua_nova = re.sub(r'\d+', '', end_norm).strip()
    rua_nova = re.sub(r'\s+', ' ', rua_nova).strip()
    if len(rua_nova) < 5:
        return None

    for oc in result.data:
        oc_norm = oc.get("endereco_normalizado", "")
        if not oc_norm:
            continue
        rua_oc = re.sub(r'\d+', '', oc_norm).strip()
        rua_oc = re.sub(r'\s+', ' ', rua_oc).strip()

        # Mesma rua (substring sem números)
        if rua_nova in rua_oc or rua_oc in rua_nova:
            logger.info(f"Match parcial mesma rua: '{rua_nova}' ~ '{rua_oc}' → {oc['protocolo']}")
            return oc

    return None


def _agrupar_relato(event: dict, sb: Client, ocorrencia_existente: dict) -> None:
    """Agrupa novo relato em ocorrência já existente."""
    telefone = event.get("telefone", "")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    protocolo = ocorrencia_existente["protocolo"]
    oc_id = ocorrencia_existente["id"]
    novo_total = (ocorrencia_existente.get("total_relatos") or 1) + 1
    severidade_cat = _severidade_por_categoria(ocorrencia_existente.get("categoria", ""))

    # Adiciona relato
    sb.table("ocorrencias_relatos").insert({
        "ocorrencia_id": oc_id,
        "telefone": telefone,
        "nome": push_name or None,
        "mensagem": texto,
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
    }).execute()

    # Atualiza total de relatos + severidade
    nova_severidade = _calcular_severidade(novo_total, severidade_cat)
    update_data = {
        "total_relatos": novo_total,
        "severidade": nova_severidade,
    }

    # Se esse relato tem GPS e a ocorrência ainda não tem, atualizar
    if event.get("latitude") and not ocorrencia_existente.get("latitude"):
        lat, lng = event["latitude"], event["longitude"]
        update_data["latitude"] = lat
        update_data["longitude"] = lng
        endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
        if endereco_geo:
            update_data["endereco"] = endereco_geo
            update_data["endereco_normalizado"] = _normalizar_endereco(endereco_geo)
        if bairro_geo:
            update_data["bairro"] = bairro_geo

    sb.table("ocorrencias").update(update_data).eq("id", oc_id).execute()

    # Processa mídia se tem
    if event.get("tem_midia"):
        processar_midia(event, sb, oc_id, "ocorrencias_relatos")

    # Monta resposta com indicação de severidade
    sev_anterior = ocorrencia_existente.get("severidade", "baixa")
    aviso_sev = ""
    if nova_severidade != sev_anterior:
        aviso_sev = f"\n⚠️ Severidade atualizada para *{nova_severidade.upper()}*."

    resposta = (
        f"Já recebemos outros relatos sobre esta ocorrência!\n\n"
        f"👥 {novo_total} cidadãos já reportaram.{aviso_sev}\n"
        f"📋 Protocolo: {protocolo}\n"
        f"Equipe já está ciente. Obrigado por reportar!"
    )

    enviar_whatsapp(telefone, resposta)
    logger.info(f"Relato agrupado: {protocolo} (total: {novo_total}, severidade: {nova_severidade})")


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — OCORRENCIA
# ══════════════════════════════════════════════════════════════

def _severidade_por_categoria(categoria: str) -> str:
    """Define severidade automática baseada na categoria da ocorrência."""
    SEVERAS = {
        "arvore_caida": "alta", "queda_arvore": "alta", "arvore": "alta",
        "deslizamento": "critica", "desmoronamento": "critica", "enchente": "critica",
        "alagamento": "alta", "inundacao": "critica",
        "incendio": "critica", "fogo": "critica",
        "desabamento": "critica", "colapso": "critica",
        "vazamento_gas": "alta", "explosao": "critica",
        "acidente": "alta", "acidente_transito": "alta",
        "fio_partido": "alta", "poste_caido": "alta",
    }
    return SEVERAS.get(categoria, "baixa")


def processar_ocorrencia(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    classificacao = event.get("classificacao", {})

    if is_continuacao:
        _continuar_ocorrencia(event, sb)
        return

    # ── CLASSIFICAÇÃO POR IMAGEM — confirmar ou pedir detalhes ──
    if classificacao.get("classificacao_por_imagem"):
        confianca = classificacao.get("confianca", 0)
        categoria_img = classificacao.get("categoria", "outros_urbanos")
        categoria_display = classificacao.get("categoria_display", categoria_img.replace("_", " "))
        icone_img = _ICONE_CATEGORIA.get(categoria_img, "⚠️")

        # Upload da imagem pra storage antecipadamente
        midia_url_temp = None
        if event.get("tem_midia") and (event.get("media_base64") or event.get("message_id")):
            temp_id = str(uuid.uuid4())
            file_bytes = download_media(event.get("message_id", ""), event.get("media_base64", ""))
            if file_bytes:
                midia_url_temp = upload_to_storage(sb, file_bytes, temp_id,
                                                   event.get("tipo_midia", "imagem"),
                                                   event.get("mimetype"))

        if confianca >= 70:
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_confirmacao_imagem", placeholder_id, {
                "push_name": push_name,
                "categoria": categoria_img,
                "categoria_display": categoria_display,
                "mensagem_original": texto,
                "midia_url_temp": midia_url_temp,
                "resumo": classificacao.get("resumo", ""),
                "confianca": confianca,
                "_placeholder": True,
            })
            resposta = (f"📸 Analisei a imagem!\n\n"
                        f"Identifiquei como: {icone_img} *{categoria_display}*\n\n"
                        f"Tá certo?\n"
                        f"1️⃣ Sim, é isso\n"
                        f"2️⃣ Não, é outra coisa")
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            logger.info(f"📸 Confirmação imagem (ocorrência): {categoria_img} ({confianca}%)")
            return
        else:
            # Confiança baixa — prosseguir como ocorrência genérica, pedir localização
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_endereco", placeholder_id, {
                "push_name": push_name,
                "categoria": categoria_img,
                "mensagem_original": texto,
                "midia_url_temp": midia_url_temp,
                "resumo": classificacao.get("resumo", ""),
                "_placeholder": True,
            })
            resposta = ("Recebi sua foto! Não consegui identificar com certeza.\n\n"
                        "📍 Pode me dizer o endereço ou enviar a localização?\n"
                        "Clique em: 📎 > Localização")
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            logger.info(f"📸 Imagem ocorrência confiança baixa ({confianca}%) — pedindo localização")
            return

    categoria = classificacao.get("categoria", "outros_urbanos")
    resumo = classificacao.get("resumo", texto[:200] if texto else "Ocorrência")
    severidade = _severidade_por_categoria(categoria)
    tem_loc = event.get("tem_localizacao", False)
    tem_midia = event.get("tem_midia", False)
    lat = event.get("latitude")
    lng = event.get("longitude")

    icone = "🚨" if severidade in ("alta", "critica") else "⚠️"
    aviso_urgente = "\n🚨 *URGENTE* — Equipe de emergência sendo acionada." if severidade in ("alta", "critica") else ""

    # ── COM GPS: pode agrupar ou criar direto ──
    if tem_loc and lat and lng:
        endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)

        # Buscar ocorrência similar (GPS + endereço geocodificado)
        similar = _buscar_ocorrencia_similar(
            sb, categoria, latitude=lat, longitude=lng, endereco=endereco_geo
        )
        if similar:
            _agrupar_relato(event, sb, similar)
            return

        # Buscar na mesma rua (pode ser outro número) → perguntar ao cidadão
        mesma_rua = _buscar_ocorrencia_mesma_rua(sb, categoria, endereco=endereco_geo)
        if mesma_rua:
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_confirmacao_dedup", placeholder_id, {
                "categoria": categoria, "resumo": resumo, "severidade": severidade,
                "texto_original": texto, "push_name": push_name or "",
                "latitude": lat, "longitude": lng,
                "endereco_geo": endereco_geo, "bairro_geo": bairro_geo,
                "oc_similar_id": mesma_rua["id"], "oc_similar_protocolo": mesma_rua["protocolo"],
                "oc_similar_endereco": mesma_rua.get("endereco", ""),
                "oc_similar_total": mesma_rua.get("total_relatos", 1),
            })
            cat_display = categoria.replace("_", " ").title()
            resposta = (
                f"⚠️ Já temos *{mesma_rua.get('total_relatos', 1)} relato(s)* de *{cat_display}* perto de você:\n\n"
                f"📍 {mesma_rua.get('endereco', mesma_rua.get('endereco_normalizado', ''))}\n"
                f"📋 Protocolo: {mesma_rua['protocolo']}\n\n"
                f"É o *mesmo caso*?\n"
                f"1️⃣ Sim, é o mesmo\n"
                f"2️⃣ Não, é outro problema diferente"
            )
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            return

        # Nova ocorrência COM endereço
        protocolo = gerar_protocolo(sb)
        endereco_inicial = endereco_geo or f"GPS: {lat:.4f}, {lng:.4f}"

        res = sb.table("ocorrencias").insert({
            "protocolo": protocolo,
            "categoria": categoria,
            "titulo": resumo,
            "descricao": texto or None,
            "endereco": endereco_inicial,
            "endereco_normalizado": _normalizar_endereco(endereco_geo or ""),
            "bairro": bairro_geo,
            "status": "aberto",
            "severidade": severidade,
            "total_relatos": 1,
            "latitude": lat,
            "longitude": lng,
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
            "latitude": lat,
            "longitude": lng,
        }).execute()

        if tem_midia:
            erro_midia = processar_midia(event, sb, registro_id, "ocorrencias_relatos")
            if erro_midia:
                enviar_whatsapp(telefone, erro_midia)

        if not tem_midia:
            etapa = "aguardando_midia_opcional"
            resposta = (f"{icone} Ocorrência registrada com localização!{aviso_urgente}\n"
                        f"📍 {endereco_inicial}\n\n"
                        f"📸 Se for seguro, envie uma foto ou vídeo do local. "
                        f"Isso ajuda muito as equipes!\n\n"
                        f"Se não puder, envie *pular* que seguimos sem foto.\n\n"
                        f"📋 Protocolo: {protocolo}")
        else:
            etapa = "finalizado"
            resposta = (f"{icone} Ocorrência completa registrada!{aviso_urgente}\n\n"
                        f"A equipe responsável já foi notificada.\n\n"
                        f"📋 Protocolo: {protocolo}")

        criar_sessao(sb, telefone, "ocorrencia", etapa, registro_id,
                     {"protocolo": protocolo, "categoria": categoria})
        if etapa == "finalizado":
            finalizar_sessao(sb, telefone)

        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
        logger.info(f"Nova ocorrência: {protocolo} cat={categoria} sev={severidade} loc=True")
        return

    # ── SEM GPS: NÃO cria protocolo, pede endereço primeiro ──
    # O protocolo só será criado quando soubermos o endereço (para poder agrupar)
    placeholder_id = str(uuid.uuid4())
    criar_sessao(sb, telefone, "ocorrencia", "aguardando_endereco", placeholder_id, {
        "categoria": categoria,
        "resumo": resumo,
        "texto_original": texto,
        "push_name": push_name or "",
        "severidade": severidade,
        "_placeholder": True,
    })

    resposta = (f"{icone} Ocorrência de *{categoria.replace('_', ' ')}* identificada!{aviso_urgente}\n\n"
                f"📍 Pode enviar a localização? Clique em: 📎 > Localização\n"
                f"Ou me diga a rua e o bairro.")

    enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
    logger.info(f"Ocorrência aguardando endereço: cat={categoria} sev={severidade}")


def _continuar_ocorrencia(event: dict, sb: Client) -> None:
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    registro_id = sessao.get("registro_id") if sessao else None
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    protocolo = contexto.get("protocolo", "")
    is_placeholder = contexto.get("_placeholder", False)
    categoria = contexto.get("categoria", "outros_urbanos")

    tem_loc = event.get("tem_localizacao", False)
    tem_midia = event.get("tem_midia", False)
    texto = event.get("texto", "")
    push_name = event.get("push_name", "") or contexto.get("push_name", "")

    logger.info(f"Continuação ocorrência: protocolo={protocolo}, placeholder={is_placeholder}, "
                f"tem_loc={tem_loc}, etapa={etapa_atual}, texto='{texto[:50]}'")

    # ══════════════════════════════════════════════════════════
    # CONFIRMAÇÃO DEDUP — cidadão diz se é o mesmo caso ou não
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_confirmacao_dedup":
        resp = texto.strip().lower()
        if resp in ("1", "sim", "mesmo", "é o mesmo", "é sim"):
            oc_id = contexto.get("oc_similar_id")
            if oc_id:
                oc_existente = sb.table("ocorrencias").select(
                    "id, protocolo, latitude, longitude, endereco_normalizado, total_relatos, titulo, bairro, severidade, categoria"
                ).eq("id", oc_id).single().execute()
                if oc_existente.data:
                    event_completo = {**event, "push_name": push_name}
                    if not event_completo.get("texto"):
                        event_completo["texto"] = contexto.get("texto_original", "")
                    if contexto.get("latitude"):
                        event_completo["latitude"] = contexto["latitude"]
                        event_completo["longitude"] = contexto["longitude"]
                    _agrupar_relato(event_completo, sb, oc_existente.data)
                    finalizar_sessao(sb, telefone)
                    return
            enviar_whatsapp(telefone, f"Agrupado ao protocolo *{contexto.get('oc_similar_protocolo', '')}*. Obrigado!")
            finalizar_sessao(sb, telefone)
            return
        elif resp in ("2", "nao", "não", "outro", "diferente", "é outro"):
            lat = contexto.get("latitude")
            lng = contexto.get("longitude")
            endereco_geo = contexto.get("endereco_geo", "")
            bairro_geo = contexto.get("bairro_geo", "")
            resumo = contexto.get("resumo", "")
            severidade = contexto.get("severidade", "baixa")
            novo_protocolo = gerar_protocolo(sb)
            res = sb.table("ocorrencias").insert({
                "protocolo": novo_protocolo, "categoria": categoria,
                "titulo": resumo, "descricao": contexto.get("texto_original", ""),
                "endereco": endereco_geo or "Endereço informado",
                "endereco_normalizado": _normalizar_endereco(endereco_geo or ""),
                "bairro": bairro_geo or "", "status": "aberto",
                "severidade": severidade, "total_relatos": 1,
                "latitude": lat, "longitude": lng,
            }).execute()
            novo_id = res.data[0]["id"]
            icone = {"incendio": "🔥", "enchente_alagamento": "🌊", "buraco_via": "🕳️", "iluminacao_publica": "💡"}.get(categoria, "⚠️")
            resposta = (f"{icone} *Nova ocorrência registrada!*\n\n"
                        f"📋 Protocolo: *{novo_protocolo}*\n"
                        f"📍 {endereco_geo or 'Localização registrada'}\nEquipe notificada!")
            criar_sessao(sb, telefone, "ocorrencia", "finalizado", novo_id, {"protocolo": novo_protocolo, "categoria": categoria})
            finalizar_sessao(sb, telefone)
            enviar_whatsapp(telefone, resposta)
            return
        else:
            enviar_whatsapp(telefone, "Responda:\n1️⃣ Sim, é o mesmo caso\n2️⃣ Não, é outro problema")
            return

    # ══════════════════════════════════════════════════════════
    # CONFIRMAÇÃO IMAGEM — cidadão confirma classificação da foto
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_confirmacao_imagem":
        if _resposta_sim(texto):
            # Cidadão confirmou — prosseguir pedindo localização
            midia_url_temp = contexto.get("midia_url_temp")
            contexto.pop("_placeholder", None)
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_endereco", placeholder_id, {
                **contexto,
                "midia_url_temp": midia_url_temp,
                "_placeholder": True,
            })
            resposta = ("✅ Entendido!\n\n"
                        "📍 Agora preciso da localização.\n"
                        "Envie pelo 📎 > Localização\n"
                        "Ou digite a rua e bairro.")
            enviar_whatsapp(telefone, resposta)
            return

        elif _resposta_nao(texto):
            # Cidadão negou — pedir descrição por texto
            midia_url_temp = contexto.get("midia_url_temp")
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_endereco", placeholder_id, {
                "push_name": push_name,
                "categoria": "outros_urbanos",
                "mensagem_original": "",
                "midia_url_temp": midia_url_temp,
                "resumo": "",
                "_placeholder": True,
            })
            resposta = ("Tudo bem! Me descreve o que aconteceu e envie a localização.\n\n"
                        "📍 Envie pelo 📎 > Localização ou digite o endereço.")
            enviar_whatsapp(telefone, resposta)
            return

        else:
            cat_display = contexto.get("categoria_display", "")
            icone = _ICONE_CATEGORIA.get(contexto.get("categoria", ""), "⚠️")
            criar_sessao(sb, telefone, "ocorrencia", etapa_atual, registro_id, contexto)
            resposta = (f"Não entendi. A foto parece ser: {icone} *{cat_display}*\n\n"
                        f"Responda:\n1️⃣ *Sim*, é isso\n2️⃣ *Não*, é outra coisa")
            enviar_whatsapp(telefone, resposta)
            return

    # ══════════════════════════════════════════════════════════
    # PLACEHOLDER: ainda NÃO existe registro no banco.
    # O cidadão mandou a mensagem inicial sem GPS, agora manda o endereço.
    # Só agora podemos buscar similar e decidir: agrupar ou criar nova.
    # ══════════════════════════════════════════════════════════
    if is_placeholder and etapa_atual == "aguardando_endereco":
        endereco = None
        bairro = None
        latitude = None
        longitude = None

        # Cidadão mandou localização GPS
        if tem_loc and event.get("latitude"):
            latitude = event["latitude"]
            longitude = event["longitude"]
            endereco_geo, bairro_geo = _geocodificar_sync(latitude, longitude)
            endereco = endereco_geo
            bairro = bairro_geo

        # Cidadão mandou endereço por texto
        elif texto and len(texto.strip()) >= 5:
            endereco = texto.strip()
            # Heurística simples: última parte após vírgula pode ser bairro
            parts = [p.strip() for p in texto.split(",")]
            if len(parts) >= 2:
                bairro = parts[-1]

        else:
            enviar_whatsapp(telefone,
                "📍 Preciso da localização para registrar.\n"
                "Envie pelo 📎 > Localização\n"
                "Ou digite a rua e bairro (ex: Av Brasil 1200, Centro).")
            return

        # ── PONTO CHAVE: buscar ocorrência similar ──
        similar = _buscar_ocorrencia_similar(
            sb, categoria,
            latitude=latitude, longitude=longitude,
            endereco=endereco
        )

        if similar:
            # AGRUPAR — não cria protocolo novo
            event_completo = {**event, "push_name": push_name}
            if not event_completo.get("texto"):
                event_completo["texto"] = contexto.get("texto_original", "")
            _agrupar_relato(event_completo, sb, similar)
            finalizar_sessao(sb, telefone)
            return

        # Buscar na mesma rua → perguntar se é o mesmo caso
        mesma_rua = _buscar_ocorrencia_mesma_rua(sb, categoria, endereco=endereco)
        if mesma_rua:
            ctx_dedup = {**contexto,
                "latitude": latitude, "longitude": longitude,
                "endereco_geo": endereco, "bairro_geo": bairro if 'bairro' in dir() else "",
                "oc_similar_id": mesma_rua["id"], "oc_similar_protocolo": mesma_rua["protocolo"],
                "oc_similar_endereco": mesma_rua.get("endereco", ""),
                "oc_similar_total": mesma_rua.get("total_relatos", 1),
            }
            atualizar_sessao(sb, telefone, "aguardando_confirmacao_dedup", ctx_dedup)
            cat_display = categoria.replace("_", " ").title()
            resposta = (
                f"⚠️ Já temos *{mesma_rua.get('total_relatos', 1)} relato(s)* de *{cat_display}* nessa região:\n\n"
                f"📍 {mesma_rua.get('endereco', '')}\n"
                f"📋 Protocolo: {mesma_rua['protocolo']}\n\n"
                f"É o *mesmo caso*?\n"
                f"1️⃣ Sim, é o mesmo\n"
                f"2️⃣ Não, é outro problema diferente"
            )
            enviar_whatsapp(telefone, resposta)
            return

        # NÃO encontrou similar — CRIAR NOVA OCORRÊNCIA agora
        novo_protocolo = gerar_protocolo(sb)
        resumo = contexto.get("resumo", contexto.get("texto_original", "Ocorrência"))
        texto_original = contexto.get("texto_original", "")
        severidade = contexto.get("severidade", "baixa")
        endereco_final = endereco or (f"GPS: {latitude:.4f}, {longitude:.4f}" if latitude else "")

        res = sb.table("ocorrencias").insert({
            "protocolo": novo_protocolo,
            "categoria": categoria,
            "titulo": resumo[:200],
            "descricao": texto_original,
            "endereco": endereco_final,
            "endereco_normalizado": _normalizar_endereco(endereco_final),
            "bairro": bairro or "",
            "status": "aberto",
            "severidade": severidade,
            "total_relatos": 1,
            "latitude": latitude,
            "longitude": longitude,
        }).execute()

        if not res.data:
            logger.error("Falha ao criar ocorrência após endereço")
            enviar_whatsapp(telefone, "Desculpe, ocorreu um erro. Tente novamente.")
            return

        novo_registro_id = res.data[0]["id"]

        # Criar relato
        sb.table("ocorrencias_relatos").insert({
            "ocorrencia_id": novo_registro_id,
            "telefone": telefone,
            "nome": push_name or None,
            "mensagem": texto_original,
            "latitude": latitude,
            "longitude": longitude,
        }).execute()

        # Processar mídia se tem (da mensagem atual)
        if tem_midia:
            processar_midia(event, sb, novo_registro_id, "ocorrencias_relatos")

        # Vincular mídia pré-uploadada de classificação por imagem (se existe)
        midia_url_temp = contexto.get("midia_url_temp")
        if midia_url_temp:
            try:
                sb.table("ocorrencias").update({
                    "midia_urls": [midia_url_temp],
                    "tem_foto": True,
                }).eq("id", novo_registro_id).execute()
                logger.info(f"📸 Mídia pré-uploadada vinculada à ocorrência {novo_protocolo}")
            except Exception as exc:
                logger.error(f"Erro ao vincular mídia pré-uploadada: {exc}")

        local_texto = endereco or bairro or "Localização registrada"
        icone = "🚨" if severidade in ("alta", "critica") else "⚠️"

        if tem_midia or midia_url_temp:
            # Já tem mídia (atual ou pré-uploadada de classificação por imagem) — finalizar
            criar_sessao(sb, telefone, "ocorrencia", "finalizado", novo_registro_id,
                         {"protocolo": novo_protocolo, "categoria": categoria})
            finalizar_sessao(sb, telefone)
            resposta = (f"📍 Endereço registrado: {local_texto}\n\n"
                        f"{icone} Ocorrência completa! Equipe notificada.\n"
                        f"📋 Protocolo: {novo_protocolo}")
        else:
            # Pedir foto opcional
            criar_sessao(sb, telefone, "ocorrencia", "aguardando_midia_opcional", novo_registro_id,
                         {"protocolo": novo_protocolo, "categoria": categoria})
            resposta = (f"📍 Endereço registrado: {local_texto}\n\n"
                        f"📸 Se for seguro, envie uma foto ou vídeo do local. "
                        f"Isso ajuda muito as equipes!\n\n"
                        f"Se não puder, envie *pular* que seguimos sem foto.\n\n"
                        f"📋 Protocolo: {novo_protocolo}")

        enviar_whatsapp(telefone, resposta)
        logger.info(f"Nova ocorrência (pós-endereço): {novo_protocolo} cat={categoria}")
        return

    # ══════════════════════════════════════════════════════════
    # JÁ TEM REGISTRO no banco — fluxo normal de continuação
    # (atualizar endereço, receber mídia, etc)
    # ══════════════════════════════════════════════════════════
    if not registro_id:
        logger.error(f"Continuacao ocorrencia sem registro_id para {telefone}")
        enviar_whatsapp(telefone, "⚠️ Ocorreu um erro. Por favor, envie sua mensagem novamente.")
        return

    if tem_loc:
        lat = event.get("latitude")
        lng = event.get("longitude")
        update_data = {"latitude": lat, "longitude": lng}
        endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
        if endereco_geo:
            update_data["endereco"] = endereco_geo
            update_data["endereco_normalizado"] = _normalizar_endereco(endereco_geo)
            endereco_display = endereco_geo
        else:
            update_data["endereco"] = f"GPS: {lat:.4f}, {lng:.4f}"
            update_data["endereco_normalizado"] = ""
            endereco_display = f"GPS: {lat:.4f}, {lng:.4f}"
        if bairro_geo:
            update_data["bairro"] = bairro_geo

        sb.table("ocorrencias").update(update_data).eq("id", registro_id).execute()
        nova_etapa = "finalizado"
        resposta = (f"📍 Localização registrada: {endereco_display}\n\n"
                    f"✅ Equipe notificada. Obrigado por reportar!\n"
                    f"📋 Protocolo: {protocolo}")

    elif texto and etapa_atual == "aguardando_endereco":
        sb.table("ocorrencias").update({
            "endereco": texto,
            "endereco_normalizado": _normalizar_endereco(texto),
        }).eq("id", registro_id).execute()
        nova_etapa = "finalizado"
        resposta = (f"📍 Endereço registrado: {texto}\n\n"
                    f"✅ Equipe notificada. Obrigado!\n"
                    f"📋 Protocolo: {protocolo}")

    elif etapa_atual == "aguardando_midia_opcional":
        _PULAR = {"pular", "nao", "não", "n", "nope", "skip", "sem foto", "sem video"}
        if tem_midia:
            # Recebeu foto/vídeo — salvar e finalizar
            erro_midia = processar_midia(event, sb, registro_id, "ocorrencias_relatos")
            if erro_midia:
                enviar_whatsapp(telefone, erro_midia)
                return
            nova_etapa = "finalizado"
            resposta = (f"📸 Evidência recebida! Obrigado.\n\n"
                        f"✅ Ocorrência completa. Equipe notificada!\n"
                        f"📋 Protocolo: {protocolo}")
        elif texto and texto.strip().lower().rstrip("!.") in _PULAR:
            # Cidadão pulou — finalizar sem foto
            nova_etapa = "finalizado"
            resposta = (f"✅ Tudo certo! Ocorrência registrada sem foto.\n\n"
                        f"Equipe já foi notificada.\n"
                        f"📋 Protocolo: {protocolo}")
        else:
            # Mandou texto que não é "pular" — lembrar que pode enviar foto ou pular
            nova_etapa = "aguardando_midia_opcional"
            resposta = (f"📸 Envie uma foto/vídeo do local, ou digite *pular* pra seguir sem foto.")

    elif tem_midia:
        erro_midia = processar_midia(event, sb, registro_id, "ocorrencias_relatos")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        nova_etapa = "finalizado"
        resposta = (f"📸 Evidência recebida! Obrigado.\n\n"
                    f"✅ Equipe notificada.\n"
                    f"📋 Protocolo: {protocolo}")

    else:
        nova_etapa = etapa_atual
        resposta = f"✅ Informação registrada no protocolo {protocolo}."

    criar_sessao(sb, telefone, "ocorrencia", nova_etapa, registro_id, contexto)
    if nova_etapa == "finalizado":
        finalizar_sessao(sb, telefone)

    enviar_whatsapp(telefone, resposta)
    logger.info(f"Continuação {protocolo} finalizada: etapa={nova_etapa}")


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — FEEDBACK
# ══════════════════════════════════════════════════════════════

def _salvar_msg_feedback(sb: Client, feedback_id: str, telefone: str, nome: str | None,
                         mensagem: str, remetente: str = "cidadao") -> None:
    """Salva uma mensagem no histórico do chat de feedback."""
    if not feedback_id or not mensagem:
        return
    try:
        sb.table("feedbacks_mensagens").insert({
            "feedback_id": feedback_id,
            "telefone": telefone,
            "nome": nome,
            "mensagem": mensagem,
            "remetente": remetente,
        }).execute()
    except Exception as exc:
        logger.error(f"Erro ao salvar msg feedback: {exc}")


def processar_feedback(event: dict, sb: Client) -> None:
    classificacao = event.get("classificacao", {})
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    is_continuacao = event.get("is_continuacao", False)

    # ── CONTINUAÇÃO: cidadão respondeu os detalhes que a Clara pediu ──
    if is_continuacao:
        _continuar_feedback(event, sb)
        return

    # ── CLASSIFICAÇÃO POR IMAGEM — confirmar ou pedir detalhes ──
    if classificacao.get("classificacao_por_imagem"):
        confianca = classificacao.get("confianca", 0)
        categoria_img = classificacao.get("categoria", "outros")
        categoria_display = classificacao.get("categoria_display", categoria_img.replace("_", " "))
        icone_img = _ICONE_CATEGORIA.get(categoria_img, "📝")

        if confianca >= 70:
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "feedback", "aguardando_confirmacao_imagem", placeholder_id, {
                "push_name": push_name,
                "categoria": categoria_img,
                "categoria_display": categoria_display,
                "sentimento": classificacao.get("sentimento", "negativo"),
                "urgencia": classificacao.get("urgencia", "normal"),
                "resumo": classificacao.get("resumo", ""),
                "mensagem_original": texto,
                "_placeholder": True,
            })
            resposta = (f"📸 Analisei a imagem!\n\n"
                        f"Identifiquei como: {icone_img} *{categoria_display}*\n\n"
                        f"Tá certo?\n"
                        f"1️⃣ Sim, é isso\n"
                        f"2️⃣ Não, é outra coisa")
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            logger.info(f"📸 Confirmação imagem (feedback): {categoria_img} ({confianca}%)")
            return
        else:
            # Confiança baixa — pedir descrição por texto
            resposta = ("Recebi sua foto! Não consegui identificar com certeza o problema.\n\n"
                        "💬 Pode me descrever o que está acontecendo?")
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "feedback", "aguardando_detalhes", placeholder_id, {
                "categoria": categoria_img,
                "sentimento": classificacao.get("sentimento", "neutro"),
                "urgencia": classificacao.get("urgencia", "normal"),
                "resumo": classificacao.get("resumo"),
                "texto_original": texto,
                "push_name": push_name or "",
            })
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            logger.info(f"📸 Imagem feedback confiança baixa ({confianca}%) — pedindo detalhes")
            return

    sentimento = classificacao.get("sentimento", "neutro")
    categoria = classificacao.get("categoria", "outros")
    resposta_ia = classificacao.get("resposta_whatsapp", "")
    pedir_detalhes = classificacao.get("pedir_localizacao", False)

    # ── A IA pediu mais detalhes → cria sessão, NÃO gera protocolo ainda ──
    if pedir_detalhes and resposta_ia:
        placeholder_id = str(uuid.uuid4())
        criar_sessao(sb, telefone, "feedback", "aguardando_detalhes", placeholder_id, {
            "categoria": categoria,
            "sentimento": sentimento,
            "urgencia": classificacao.get("urgencia", "normal"),
            "resumo": classificacao.get("resumo"),
            "texto_original": texto,
            "push_name": push_name or "",
        })
        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta_ia))
        logger.info(f"Feedback aguardando detalhes: cat={categoria} sent={sentimento}")
        return

    # ── Feedback completo (sem necessidade de perguntas) → salva direto ──
    protocolo = gerar_protocolo(sb)

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
        feedback_id = res.data[0]["id"]
        logger.info(f"Feedback: {protocolo} ({sentimento})")

        # Salvar mensagem do cidadão
        _salvar_msg_feedback(sb, feedback_id, telefone, push_name, texto)

        if resposta_ia:
            resposta = (f"{resposta_ia}\n\n"
                        f"📋 Protocolo: *{protocolo}*\n\n"
                        f"Seu feedback é muito importante para Maringá! 💙")
        else:
            emoji = {"positivo": "😊", "negativo": "😔", "neutro": "📝"}.get(sentimento, "📝")
            resposta = (f"{emoji} Obrigado pelo seu feedback, {push_name or 'cidadão'}!\n\n"
                        f"Vamos encaminhar para o setor de *{categoria.replace('_', ' ')}*.\n\n"
                        f"📋 Protocolo: *{protocolo}*\n\n"
                        f"Maringá agradece sua participação! 💙🌳")

        # Salvar resposta do bot
        _salvar_msg_feedback(sb, feedback_id, "bot", "Clara IA", resposta, "bot")

        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))


def _continuar_feedback(event: dict, sb: Client) -> None:
    """Continuação de feedback — cidadão respondeu com detalhes que a Clara pediu."""
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    texto = event.get("texto", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    push_name = event.get("push_name", "") or contexto.get("push_name", "")
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    registro_id = sessao.get("registro_id") if sessao else None

    # ══════════════════════════════════════════════════════════
    # CONFIRMAÇÃO IMAGEM — cidadão confirma classificação da foto
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_confirmacao_imagem":
        if _resposta_sim(texto):
            # Cidadão confirmou — criar feedback
            cat = contexto.get("categoria", "outros")
            sentimento = contexto.get("sentimento", "negativo")
            resumo = contexto.get("resumo", "")
            msg_original = contexto.get("mensagem_original", "")

            protocolo = gerar_protocolo(sb)
            res = sb.table("feedbacks").insert({
                "protocolo": protocolo,
                "telefone": telefone,
                "nome": push_name or None,
                "categoria": cat,
                "sentimento": sentimento,
                "urgencia": contexto.get("urgencia", "normal"),
                "mensagem": resumo or msg_original or "Feedback por imagem",
                "resumo": resumo,
                "status": "novo",
            }).execute()

            if res.data:
                feedback_id = res.data[0]["id"]
                _salvar_msg_feedback(sb, feedback_id, telefone, push_name,
                                     resumo or msg_original or "Feedback por imagem")
                cat_label = cat.replace("_", " ")
                resposta = (f"✅ Feedback registrado como *{cat_label}*!\n\n"
                            f"📋 Protocolo: *{protocolo}*\n\n"
                            f"Seu feedback é muito importante para Maringá! 💙")
                _salvar_msg_feedback(sb, feedback_id, "bot", "Clara IA", resposta, "bot")
                enviar_whatsapp(telefone, resposta)
            finalizar_sessao(sb, telefone)
            logger.info(f"📸 Feedback confirmado por imagem: {protocolo} ({cat})")
            return

        elif _resposta_nao(texto):
            # Cidadão negou — pedir descrição por texto
            placeholder_id = str(uuid.uuid4())
            criar_sessao(sb, telefone, "feedback", "aguardando_detalhes", placeholder_id, {
                "categoria": "outros",
                "sentimento": "neutro",
                "urgencia": "normal",
                "resumo": "",
                "texto_original": "",
                "push_name": push_name,
            })
            resposta = ("Tudo bem! Me conta o que está acontecendo.\n\n"
                        "💬 Descreva o problema que você quer reportar.")
            enviar_whatsapp(telefone, resposta)
            return

        else:
            cat_display = contexto.get("categoria_display", "")
            icone = _ICONE_CATEGORIA.get(contexto.get("categoria", ""), "📝")
            criar_sessao(sb, telefone, "feedback", etapa_atual, registro_id, contexto)
            resposta = (f"Não entendi. A foto parece ser: {icone} *{cat_display}*\n\n"
                        f"Responda:\n1️⃣ *Sim*, é isso\n2️⃣ *Não*, é outra coisa")
            enviar_whatsapp(telefone, resposta)
            return

    categoria = contexto.get("categoria", "outros")
    sentimento = contexto.get("sentimento", "neutro")
    texto_original = contexto.get("texto_original", "")

    # Gera protocolo agora que temos os detalhes
    protocolo = gerar_protocolo(sb)

    # Combina mensagem original + detalhes novos
    mensagem_completa = texto_original
    if texto:
        mensagem_completa = f"{texto_original}\n[Detalhe adicional: {texto}]"

    # O detalhe adicional geralmente é o endereço/local que a Clara pediu
    # Salvar como endereco do feedback
    endereco = texto.strip() if texto else None
    bairro = None

    # Se recebeu localização GPS, geocodificar
    lat = event.get("latitude")
    lng = event.get("longitude")
    if lat and lng:
        try:
            endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
            if endereco_geo:
                endereco = endereco_geo
            if bairro_geo:
                bairro = bairro_geo
        except Exception:
            pass

    res = sb.table("feedbacks").insert({
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "sentimento": sentimento,
        "urgencia": contexto.get("urgencia", "normal"),
        "mensagem": mensagem_completa,
        "resumo": contexto.get("resumo"),
        "endereco": endereco,
        "bairro": bairro,
        "latitude": lat,
        "longitude": lng,
        "status": "novo",
    }).execute()

    if not res.data:
        logger.error("Falha ao criar feedback na continuação")
        return

    feedback_id = res.data[0]["id"]
    logger.info(f"Feedback completo: {protocolo} ({sentimento}) — detalhes recebidos")

    # Salvar mensagens no histórico
    _salvar_msg_feedback(sb, feedback_id, telefone, push_name, texto_original)
    if texto and texto != texto_original:
        _salvar_msg_feedback(sb, feedback_id, telefone, push_name, texto)

    # Usa a IA pra gerar resposta de encerramento humanizada
    resposta_ia = event.get("classificacao", {}).get("resposta_whatsapp", "")

    if resposta_ia:
        resposta = (f"{resposta_ia}\n\n"
                    f"📋 Protocolo: *{protocolo}*\n\n"
                    f"Seu feedback é muito importante para Maringá! 💙🌳")
    else:
        emoji = {"positivo": "😊", "negativo": "😔", "neutro": "📝"}.get(sentimento, "📝")
        setor = categoria.replace("_", " ")
        resposta = (f"{emoji} Anotado, {push_name or 'cidadão'}! "
                    f"Já encaminhei sua mensagem para a equipe de *{setor}* da Prefeitura.\n\n"
                    f"📋 Protocolo: *{protocolo}*\n\n"
                    f"Maringá agradece sua participação! 💙🌳")

    _salvar_msg_feedback(sb, feedback_id, "bot", "Clara IA", resposta, "bot")

    finalizar_sessao(sb, telefone)
    enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))


# ══════════════════════════════════════════════════════════════
# ── HELPERS: Privacidade de protocolo ──────────────────────────

def _verificar_dono_protocolo(sb: Client, protocolo: str, telefone: str) -> bool:
    """
    Verifica se o protocolo pertence ao telefone solicitante.
    Checa denuncias, ocorrencias_relatos, feedbacks e sos_alertas.

    Retorna True se o telefone é dono, False caso contrário.
    Em caso de erro, retorna False (fail-safe: nega acesso).
    """
    # Checa denúncias
    try:
        r = sb.table("denuncias").select("telefone").eq("protocolo", protocolo).limit(1).execute()
        if r.data and r.data[0].get("telefone") == telefone:
            return True
    except Exception:
        pass

    # Checa relatos de ocorrência (ocorrencia não tem telefone direto)
    try:
        # Primeiro pega o ID da ocorrência pelo protocolo
        oc = sb.table("ocorrencias").select("id").eq("protocolo", protocolo).limit(1).execute()
        if oc.data:
            oc_id = oc.data[0]["id"]
            rel = sb.table("ocorrencias_relatos").select("telefone").eq(
                "ocorrencia_id", oc_id
            ).eq("telefone", telefone).limit(1).execute()
            if rel.data:
                return True
    except Exception:
        pass

    # Checa feedbacks
    try:
        r = sb.table("feedbacks").select("telefone").eq("protocolo", protocolo).limit(1).execute()
        if r.data and r.data[0].get("telefone") == telefone:
            return True
    except Exception:
        pass

    # Checa SOS
    try:
        r = sb.table("sos_alertas").select("telefone").eq("protocolo", protocolo).limit(1).execute()
        if r.data and r.data[0].get("telefone") == telefone:
            return True
    except Exception:
        pass

    return False


def _msg_protocolo_privado(protocolo: str) -> str:
    """Mensagem padrão quando cidadão tenta consultar protocolo de outro número."""
    return (
        f"🔒 O protocolo *{protocolo}* não está vinculado a este número.\n\n"
        f"Por segurança, você só pode consultar protocolos abertos por este telefone.\n\n"
        f"Se acredita que isso é um erro, envie sua mensagem normalmente e vamos te ajudar."
    )


# PROCESSADOR — CONSULTA DE PROTOCOLO (via WhatsApp)
# ══════════════════════════════════════════════════════════════

def processar_consulta_protocolo(event: dict, sb: Client) -> None:
    """
    Processa consultas de protocolo — dois fluxos:
    1. INTENÇÃO: cidadão quer consultar mas não mandou o protocolo → cria sessão
    2. PROTOCOLO DIRETO: cidadão mandou MGA-XXXX-XXXXX → busca e responde
    3. CONTINUAÇÃO: cidadão está na sessão e mandou o protocolo → busca e responde

    PROTEÇÕES:
    - Rate limit: se rate_limited=True, só avisa que excedeu o limite
    - Privacidade: só mostra detalhes de protocolos do próprio número
    """
    telefone = event.get("telefone", "desconhecido")
    classificacao = event.get("classificacao", {})
    is_continuacao = event.get("is_continuacao", False)

    # ── FLUXO 1: Intenção de consulta (sem protocolo) ──
    if classificacao.get("categoria") == "intencao_consulta" and not is_continuacao:
        logger.info(f"🔍 Intenção de consulta: criando sessão para {telefone}")
        criar_sessao(sb, telefone, "consulta_protocolo", "aguardando_protocolo",
                     "", {"tipo": "consulta_protocolo"})
        enviar_whatsapp(telefone,
            "🔍 Para consultar, me envie o número do protocolo.\n\n"
            "Exemplo: *MGA-2026-00607* ou *ARB-2026-00051*\n\n"
            "O protocolo foi informado quando você fez o registro.")
        return

    # ── FLUXO 3: Continuação — cidadão mandou o protocolo na sessão ──
    if is_continuacao:
        sessao = event.get("sessao", {})
        etapa = sessao.get("etapa", "")
        texto = (event.get("texto") or "").strip()

        if etapa == "aguardando_protocolo":
            # Tenta extrair protocolo do texto (MGA ou ARB, números ou hex)
            protocolo_match = re.search(r"(MGA|ARB)-\d{4}-[A-Z0-9]{4,8}", texto.upper())
            if protocolo_match:
                protocolo = protocolo_match.group(0)
                logger.info(f"🔍 Protocolo recebido na sessão: {protocolo} de {telefone}")
                finalizar_sessao(sb, telefone)
                _buscar_e_responder_protocolo(sb, telefone, protocolo)
                return
            else:
                enviar_whatsapp(telefone,
                    "❌ Não consegui identificar o protocolo.\n\n"
                    "Formato: *MGA-2026-XXXXX* ou *ARB-2026-XXXXX*\n\n"
                    "Tente novamente ou envie sua mensagem normalmente.")
                return
        # Sessão em etapa desconhecida — finaliza
        finalizar_sessao(sb, telefone)
        return

    # ── FLUXO 2: Protocolo direto (MGA-XXXX-XXXXX detectado no webhook) ──
    protocolo = classificacao.get("protocolo_consulta", "").strip().upper()

    if not protocolo:
        enviar_whatsapp(telefone, "❌ Não consegui identificar o número do protocolo. "
                        "O formato correto é MGA-2026-XXXXX.")
        return

    # ── PROTEÇÃO 3: Consulta bloqueada por rate limit ──
    if classificacao.get("rate_limited"):
        minutos = classificacao.get("retry_after_minutos", 60)
        enviar_whatsapp(telefone,
            f"⏳ Você já fez várias consultas de protocolo recentemente.\n\n"
            f"Por segurança, aguarde aproximadamente {minutos} minutos antes de consultar novamente.\n\n"
            f"Se precisar de ajuda urgente, envie sua mensagem normalmente."
        )
        return

    _buscar_e_responder_protocolo(sb, telefone, protocolo)


def _buscar_e_responder_protocolo(sb: Client, telefone: str, protocolo: str) -> None:
    """
    Busca protocolo em todas as tabelas e responde ao cidadão via WhatsApp.
    Usado tanto pela consulta direta quanto pela continuação de sessão.
    """
    logger.info(f"🔍 Consulta protocolo: {protocolo} de {telefone}")

    # ── PROTEÇÃO 4: Privacidade — só consulta protocolos do próprio número ──
    protocolo_pertence_ao_telefone = _verificar_dono_protocolo(sb, protocolo, telefone)

    # ── Busca em denúncias ──
    try:
        result = sb.table("denuncias").select(
            "protocolo, categoria, status, cidadania_ativa, created_at, telefone"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            d = result.data[0]

            dono_telefone = d.get("telefone", "")
            if not protocolo_pertence_ao_telefone and dono_telefone != telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return

            msg = f"📋 *Denúncia {d['protocolo']}*\n"
            msg += f"Categoria: {(d.get('categoria') or 'não classificada').replace('_', ' ').title()}\n\n"

            status_map = {
                "novo": "📋 *Recebida* — Sua denúncia foi registrada e aguarda análise.",
                "em_analise": "🔍 *Em análise* — A equipe está verificando sua denúncia.",
                "em_campo": "🚔 *Em campo* — Agentes foram ao local verificar.",
                "procedente": "✅ *Procedente* — Sua denúncia foi considerada procedente!",
                "resolvido": "✅ *Resolvida* — Sua denúncia foi tratada. Obrigado!",
                "rejeitada": "❌ *Rejeitada* — Infelizmente sua denúncia foi rejeitada após análise.",
                "improcedente": "⚠️ *Improcedente* — Após verificação, a denúncia não foi confirmada no local informado.",
                "arquivado": "📁 *Arquivada* — Denúncia arquivada após análise.",
            }
            msg += status_map.get(d["status"], f"Status: {d['status']}")

            if d.get("cidadania_ativa"):
                try:
                    rec = sb.table("recompensas").select(
                        "status, valor"
                    ).eq("protocolo", protocolo).limit(1).execute()
                    if rec.data:
                        r = rec.data[0]
                        rec_status_map = {
                            "pendente_validacao": "⏳ Aguardando validação pela equipe",
                            "validada": "✅ Validada! Pagamento sendo processado",
                            "aguardando_pagamento": "💳 Aprovada! Aguardando liberação do pagamento",
                            "paga": f"💰 *PAGA!* R$ {r['valor']:.2f} enviado via PIX",
                            "rejeitada": "❌ Não aprovada para recompensa",
                        }
                        msg += f"\n\n💰 *Cidadão Ativo:*\n{rec_status_map.get(r['status'], r['status'])}"
                except Exception:
                    pass

            enviar_whatsapp(telefone, msg)
            return
    except Exception as exc:
        logger.error(f"Erro busca denúncia: {exc}")

    # ── Busca em ocorrências ──
    try:
        result = sb.table("ocorrencias").select(
            "protocolo, id, categoria, status, severidade, total_relatos, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            o = result.data[0]

            if not protocolo_pertence_ao_telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return

            msg = f"🚨 *Ocorrência {o['protocolo']}*\n"
            msg += f"Categoria: {(o.get('categoria') or '').replace('_', ' ').title()}\n"
            msg += f"Severidade: {'⚠️' * min(o.get('severidade', 1), 5)}\n"
            msg += f"Relatos: {o.get('total_relatos', 1)} pessoa(s)\n\n"

            status_map = {
                "ativo": "🟡 *Ativa* — Em monitoramento.",
                "encaminhada": "📤 *Encaminhada* — Sua ocorrência foi encaminhada para a equipe responsável.",
                "em_atendimento": "🚔 *Em atendimento* — Equipe no local.",
                "no_local": "📍 *No local* — A equipe já está no local atendendo sua ocorrência!",
                "resolvido": "✅ *Resolvida* — Situação normalizada.",
            }
            msg += status_map.get(o["status"], f"Status: {o['status']}")
            enviar_whatsapp(telefone, msg)
            return
    except Exception as exc:
        logger.error(f"Erro busca ocorrência: {exc}")

    # ── Busca em feedbacks ──
    try:
        result = sb.table("feedbacks").select(
            "protocolo, categoria, status, departamento, telefone, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            f = result.data[0]

            if not protocolo_pertence_ao_telefone and f.get("telefone") != telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return

            msg = f"💬 *Feedback {f['protocolo']}*\n"
            if f.get("departamento"):
                msg += f"Departamento: {f['departamento']}\n"
            msg += "\n"

            status_map = {
                "novo": "📬 *Recebido* — Seu feedback foi registrado.",
                "lido": "👁️ *Lido* — Mensagem visualizada pela equipe.",
                "respondido": "💬 *Respondido* — Encaminhado ao departamento.",
                "encerrado": "✅ *Encerrado* — Obrigado pelo feedback!",
            }
            msg += status_map.get(f["status"], f"Status: {f['status']}")
            enviar_whatsapp(telefone, msg)
            return
    except Exception as exc:
        logger.error(f"Erro busca feedback: {exc}")

    # ── Busca em arborização ──
    try:
        result = sb.table("arborizacao").select(
            "protocolo, categoria, status, severidade, resumo, empresa_atribuida, telefone, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            a = result.data[0]
            if not protocolo_pertence_ao_telefone and a.get("telefone") != telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return
            msg = f"🌳 *Arborização {a['protocolo']}*\n"
            msg += f"Tipo: {(a.get('categoria') or '').replace('_', ' ').title()}\n"
            if a.get("empresa_atribuida"):
                msg += f"Empresa: {a['empresa_atribuida']}\n"
            msg += "\n"
            status_map = {
                "recebido": "📥 *Recebida* — Solicitação registrada, aguardando triagem.",
                "triado": "📋 *Triada* — Classificada, aguardando atribuição à empresa.",
                "atribuido": "🏢 *Atribuída* — Encaminhada para a empresa contratada.",
                "em_execucao": "⚙️ *Em execução* — Equipe da empresa trabalhando no local.",
                "concluido": "✅ *Concluído* — Serviço realizado, aguardando fiscalização.",
                "fiscalizado": "🔍 *Fiscalizado e aprovado* — Serviço concluído com sucesso!",
            }
            msg += status_map.get(a["status"], f"Status: {a['status']}")
            enviar_whatsapp(telefone, msg)
            return
    except Exception as exc:
        logger.error(f"Erro busca arborização: {exc}")

    # ── Busca em SOS ──
    try:
        result = sb.table("sos_alertas").select(
            "protocolo, status, telefone, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            s = result.data[0]

            if not protocolo_pertence_ao_telefone and s.get("telefone") != telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return
            status_map = {
                "active": "🔴 *ATIVO* — Equipe acionada.",
                "accepted": "🚔 *Aceito* — Viatura designada.",
                "resolved": "✅ *Atendido* — Finalizado.",
            }
            msg = f"🆘 *Alerta SOS {s['protocolo']}*\n\n"
            msg += status_map.get(s["status"], f"Status: {s['status']}")
            msg += "\n\nSe está em perigo, ligue 190."
            enviar_whatsapp(telefone, msg)
            return
    except Exception as exc:
        logger.error(f"Erro busca SOS: {exc}")

    # ── Não encontrou ──
    msg = (f"😕 Não encontrei nenhum registro com o protocolo *{protocolo}*.\n\n"
           f"Verifique se digitou corretamente.\nFormato: MGA-2026-XXXXX ou ARB-2026-XXXXX\n\n"
           f"Se precisar de ajuda, envie sua mensagem normalmente!")
    enviar_whatsapp(telefone, msg)


# ══════════════════════════════════════════════════════════════
# PROCESSADORES — SAUDAÇÃO (sem criar protocolo)
# ══════════════════════════════════════════════════════════════

def processar_saudacao(event: dict, sb: Client) -> None:
    """Responde saudações/agradecimentos sem criar nenhum registro."""
    telefone = event.get("telefone", "")
    push_name = event.get("push_name", "")
    classificacao = event.get("classificacao", {})

    resposta = classificacao.get("resposta_whatsapp", "")
    if not resposta:
        resposta = (f"Olá{', ' + push_name if push_name else ''}! 👋\n"
                    f"Sou a Clara, assistente da Prefeitura de Maringá.\n\n"
                    f"Como posso ajudar?\n"
                    f"📢 Fazer uma denúncia\n"
                    f"📍 Reportar ocorrência urbana\n"
                    f"💬 Enviar feedback\n"
                    f"🔍 Consultar protocolo\n"
                    f"🆘 SOS Mulher")

    enviar_whatsapp(telefone, resposta)
    logger.info(f"Saudação respondida para {telefone}")


# ══════════════════════════════════════════════════════════════
# ARBORIZAÇÃO — Pipeline agentic
# ══════════════════════════════════════════════════════════════

SLA_ARBORIZACAO = {
    "emergencia": 4,
    "urgencia": 24,
    "prioridade": 72,
    "rotina": 168,
}

_ICONE_ARB = {
    "poda_geral": "✂️", "poda_complexa": "🏗️", "poda_desbarra": "🌿",
    "remocao": "🪓", "arvore_caida": "🌳", "retirada_toco": "🪵", "risco_queda": "⚠️",
}


def gerar_protocolo_arb(sb: Client) -> str:
    """Gera protocolo ARB-YYYY-XXXXX."""
    ano = date.today().year
    try:
        result = sb.table("arborizacao").select("protocolo").like(
            "protocolo", f"ARB-{ano}-%"
        ).order("protocolo", desc=True).limit(1).execute()
        if result.data and result.data[0].get("protocolo"):
            try:
                max_num = int(result.data[0]["protocolo"].split("-")[-1])
            except (ValueError, IndexError):
                max_num = 0
        else:
            max_num = 0
        protocolo = f"ARB-{ano}-{str(max_num + 1).zfill(5)}"
        logger.info(f"Protocolo arborização gerado: {protocolo}")
        return protocolo
    except Exception as exc:
        logger.error(f"Falha protocolo ARB: {exc}")
        return f"ARB-{ano}-{secrets.token_hex(4).upper()}"


def _calcular_sla_arb(severidade: str) -> tuple[int, str]:
    """Retorna (sla_horas, sla_vencimento_iso)."""
    horas = SLA_ARBORIZACAO.get(severidade, 168)
    vencimento = (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat()
    return horas, vencimento


def _processar_midia_arb(event: dict, sb: Client, registro_id: str, momento: str) -> str | None:
    """Upload foto e armazena em foto_antes_urls ou foto_depois_urls."""
    campo = "foto_antes_urls" if momento == "antes" else "foto_depois_urls"
    flag = "tem_foto_antes" if momento == "antes" else "tem_foto_depois"
    try:
        media_b64 = event.get("media_base64", "")
        message_id = event.get("message_id", "")
        file_bytes = download_media(message_id, media_b64)
        if not file_bytes:
            logger.warning(f"Não conseguiu baixar mídia arborização {registro_id}")
            return None
        mimetype = event.get("mimetype", "image/jpeg")
        public_url = upload_to_storage(sb, file_bytes, f"arb-{registro_id}", "imagem", mimetype)
        if not public_url:
            return None
        # Append URL ao array existente
        arb = sb.table("arborizacao").select(campo).eq("id", registro_id).single().execute()
        urls = (arb.data or {}).get(campo, []) or []
        urls.append(public_url)
        sb.table("arborizacao").update({campo: urls, flag: True}).eq("id", registro_id).execute()
        logger.info(f"Foto {momento} arborização salva: {public_url}")
        return public_url
    except Exception as exc:
        logger.error(f"Erro mídia arborização: {exc}")
        return None


def _buscar_arborizacao_similar(sb: Client, categoria: str,
                                latitude: float | None = None,
                                longitude: float | None = None,
                                endereco: str | None = None) -> dict | None:
    """Busca solicitação de arborização ATIVA com mesma categoria nas últimas 48h
    que esteja próxima (< 300m por GPS ou mesmo endereço normalizado)."""
    limite = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    try:
        result = sb.table("arborizacao").select(
            "id, protocolo, latitude, longitude, endereco_normalizado, categoria, bairro, status"
        ).eq("categoria", categoria).not_.in_(
            "status", ["fiscalizado"]
        ).gte("created_at", limite).execute()

        if not result.data:
            return None

        for arb in result.data:
            # GPS próximo (< 300m)
            if latitude and longitude and arb.get("latitude") and arb.get("longitude"):
                dist = _haversine(latitude, longitude, arb["latitude"], arb["longitude"])
                if dist < 300:
                    logger.info(f"Arborização agrupamento GPS: {dist:.0f}m de {arb['protocolo']}")
                    return arb
            # Endereço normalizado similar
            if endereco and arb.get("endereco_normalizado"):
                end_norm = _normalizar_endereco(endereco)
                if end_norm and len(end_norm) > 5:
                    oc_norm = arb["endereco_normalizado"]
                    if end_norm in oc_norm or oc_norm in end_norm:
                        logger.info(f"Arborização agrupamento endereço: '{end_norm}' → {arb['protocolo']}")
                        return arb
    except Exception as exc:
        logger.error(f"Erro busca arborização similar: {exc}")
    return None


def _despachar_para_empresa(sb: Client, arb_id: str) -> None:
    """Envia OS via WhatsApp para empresa contratada."""
    try:
        arb = sb.table("arborizacao").select("*").eq("id", arb_id).single().execute().data
        if not arb or not arb.get("empresa_telefone"):
            return
        cat = arb["categoria"].replace("_", " ").title()
        sev = arb["severidade"].upper()
        icone = _ICONE_ARB.get(arb["categoria"], "🌳")
        gmaps = f"https://www.google.com/maps?q={arb.get('latitude',0)},{arb.get('longitude',0)}"
        os_msg = (
            f"📋 *ORDEM DE SERVIÇO — ARBORIZAÇÃO MARINGÁ*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{icone} Tipo: *{cat}*\n"
            f"🚨 Severidade: *{sev}*\n"
            f"📋 Protocolo: {arb['protocolo']}\n"
            f"📍 {arb.get('endereco', 'Endereço não informado')}\n"
            f"🏘️ {arb.get('bairro', '—')}\n"
            f"🗺️ Maps: {gmaps}\n"
            f"⏱️ SLA: {arb.get('sla_horas', '—')}h\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Responda:\n"
            f"1️⃣ Aceitar OS\n"
            f"2️⃣ Equipe a caminho\n"
            f"3️⃣ Concluído (envie foto)\n"
            f"0️⃣ Não posso atender"
        )
        enviar_whatsapp(arb["empresa_telefone"], os_msg)
        # Enviar foto do cidadão para a empresa (se disponível)
        foto_antes = arb.get("foto_antes_urls") or []
        if foto_antes:
            enviar_whatsapp_imagem(arb["empresa_telefone"], foto_antes[0],
                f"📷 Foto enviada pelo cidadão — {arb['protocolo']}")
        # Sessão para empresa com TTL longo (24h)
        # Normalizar telefone com + (webhook salva com +55)
        tel_empresa = arb["empresa_telefone"]
        if not tel_empresa.startswith("+"):
            tel_empresa = "+" + tel_empresa
        expira_24h = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        sb.table("sessoes_conversa").upsert({
            "telefone": tel_empresa,
            "canal": "arborizacao_empresa",
            "etapa": "aguardando_aceite",
            "registro_id": arb_id,
            "contexto": {"protocolo": arb["protocolo"], "arb_id": arb_id, "empresa_nome": arb.get("empresa_atribuida", "")},
            "expira_em": expira_24h,
            "handoff_ativo": False,
            "handoff_operador": "",
        }, on_conflict="telefone").execute()
        logger.info(f"OS arborização despachada: {arb['protocolo']} → {arb.get('empresa_atribuida')}")
    except Exception as exc:
        logger.error(f"Erro despacho empresa arborização: {exc}")


def _auto_despachar(sb: Client, arb_id: str, protocolo: str) -> None:
    """AUTOMAÇÃO: auto-triagem + auto-atribuição + despacho para empresa.
    Chamado automaticamente quando cidadão registra solicitação."""
    try:
        # Buscar empresa padrão (Corpus = zona "todas")
        cfg = sb.table("arborizacao_config").select("valor").eq("tipo", "empresa").execute()
        empresa = None
        for e in (cfg.data or []):
            if e["valor"].get("zona") == "todas":
                empresa = e["valor"]
                break
        if not empresa and cfg.data:
            empresa = cfg.data[0]["valor"]
        if not empresa:
            logger.warning(f"Nenhuma empresa cadastrada para auto-despacho: {protocolo}")
            return

        # Auto-triagem + auto-atribuição
        tel_empresa = empresa["telefone"]
        if not tel_empresa.startswith("+"):
            tel_empresa = "+" + tel_empresa

        # Buscar SLA
        arb = sb.table("arborizacao").select("severidade").eq("id", arb_id).single().execute().data
        severidade = (arb or {}).get("severidade", "rotina")
        sla_horas, sla_vencimento = _calcular_sla_arb(severidade)

        sb.table("arborizacao").update({
            "status": "atribuido",
            "triado_em": datetime.now(timezone.utc).isoformat(),
            "empresa_atribuida": empresa["nome"],
            "empresa_telefone": tel_empresa.lstrip("+"),
            "atribuida_em": datetime.now(timezone.utc).isoformat(),
            "sla_horas": sla_horas,
            "sla_vencimento": sla_vencimento,
        }).eq("id", arb_id).execute()

        # Despachar OS
        _despachar_para_empresa(sb, arb_id)
        logger.info(f"🤖 AUTO-DESPACHO: {protocolo} → {empresa['nome']}")

    except Exception as exc:
        logger.error(f"Erro auto-despacho {protocolo}: {exc}")


def _auto_fiscalizar_e_notificar(sb: Client, arb_id: str) -> None:
    """AUTOMAÇÃO: fiscal IA compara antes/depois + notifica cidadão.
    Chamado quando empresa envia foto de conclusão."""
    try:
        arb = sb.table("arborizacao").select(
            "id, protocolo, telefone, nome, categoria, endereco, bairro, "
            "foto_antes_urls, foto_depois_urls, severidade"
        ).eq("id", arb_id).single().execute().data
        if not arb:
            return

        foto_antes = (arb.get("foto_antes_urls") or [])
        foto_depois = (arb.get("foto_depois_urls") or [])

        # Se tem fotos antes E depois → fiscal IA
        if foto_antes and foto_depois:
            import asyncio
            from app.services.classificador import comparar_antes_depois
            try:
                loop = asyncio.new_event_loop()
                resultado = loop.run_until_complete(
                    comparar_antes_depois(foto_antes[0], foto_depois[0], arb["categoria"])
                )
                loop.close()
            except Exception as e:
                logger.error(f"Erro fiscal IA: {e}")
                resultado = {"aprovado": False, "confianca": 0, "observacao": f"Erro: {e}"}

            confianca = resultado.get("confianca", 0)
            aprovado = resultado.get("aprovado", False) and confianca >= 80

            if aprovado:
                sb.table("arborizacao").update({
                    "status": "fiscalizado",
                    "fiscal_aprovado": True,
                    "fiscal_confianca": confianca,
                    "fiscal_obs": resultado.get("observacao", "Auto-aprovado por IA"),
                    "fiscal_operador": "IA",
                    "fiscal_data": datetime.now(timezone.utc).isoformat(),
                    "fiscalizado_em": datetime.now(timezone.utc).isoformat(),
                }).eq("id", arb_id).execute()
                logger.info(f"🤖 AUTO-FISCAL APROVADO: {arb['protocolo']} (conf={confianca}%)")
            else:
                sb.table("arborizacao").update({
                    "fiscal_confianca": confianca,
                    "fiscal_obs": f"IA inconclusiva ({confianca}%): {resultado.get('observacao', '')}",
                }).eq("id", arb_id).execute()
                logger.info(f"🤖 AUTO-FISCAL PENDENTE: {arb['protocolo']} (conf={confianca}%) → requer humano")
                # Não notifica cidadão — aguarda fiscal humano
                return
        else:
            # Sem fotos antes → auto-aprovar (confiança N/A)
            sb.table("arborizacao").update({
                "status": "fiscalizado",
                "fiscal_aprovado": True,
                "fiscal_confianca": 100,
                "fiscal_obs": "Aprovado automaticamente (sem foto antes para comparação)",
                "fiscal_operador": "IA",
                "fiscal_data": datetime.now(timezone.utc).isoformat(),
                "fiscalizado_em": datetime.now(timezone.utc).isoformat(),
            }).eq("id", arb_id).execute()
            logger.info(f"🤖 AUTO-FISCAL (sem antes): {arb['protocolo']}")

        # ── Notificar cidadão com foto do depois ──
        cat_display = arb["categoria"].replace("_", " ").title()

        # Enviar foto do serviço concluído (se disponível)
        foto_depois = (arb.get("foto_depois_urls") or [])
        if foto_depois:
            enviar_whatsapp_imagem(arb["telefone"], foto_depois[0],
                f"✅ Serviço concluído!\n📋 {arb['protocolo']} — {cat_display}\n📍 {arb.get('endereco', '')}")

        resposta_cidadao = (
            f"✅ Ótima notícia! O serviço de arborização foi concluído!\n\n"
            f"📋 Protocolo: *{arb['protocolo']}*\n"
            f"🌳 Tipo: *{cat_display}*\n"
            f"📍 {arb.get('endereco', '')}\n"
            f"🏢 Empresa: {arb.get('empresa_atribuida', '—')}\n\n"
            f"A equipe realizou o serviço e foi aprovado pela fiscalização. ✅\n\n"
            f"⭐ *Avalie o atendimento de 1 a 5:*\n"
            f"1️⃣ Péssimo  2️⃣ Ruim  3️⃣ Regular  4️⃣ Bom  5️⃣ Excelente"
        )
        enviar_whatsapp(arb["telefone"], resposta_cidadao)

        # Criar sessão para avaliação do cidadão
        criar_sessao(sb, arb["telefone"], "arborizacao", "aguardando_avaliacao", arb_id,
                     {"protocolo": arb["protocolo"]})
        logger.info(f"📲 Cidadão notificado: {arb['protocolo']} → {arb['telefone']}")

    except Exception as exc:
        logger.error(f"Erro auto-fiscalizar {arb_id}: {exc}")


def _processar_resposta_empresa(event: dict, sb: Client) -> None:
    """Processa resposta da empresa via WhatsApp.

    Fluxo correto:
    ┌─ OS chega → etapa: aguardando_aceite
    │
    ├─ "1" (Aceitar) → status: em_execucao, etapa: em_execucao
    ├─ "2" (A caminho) → status: em_execucao, etapa: em_execucao
    │   (aceita implicitamente se ainda estava em aguardando_aceite)
    │
    ├─ "3" ou FOTO (Concluído) → status: concluido, etapa: finalizado
    │   (aceita em qualquer etapa: aguardando_aceite, em_execucao)
    │
    └─ "0" (Recusar) → status: triado, etapa: finalizado
    """
    sessao = event.get("sessao", {})
    contexto = sessao.get("contexto", {})
    arb_id = contexto.get("arb_id") or sessao.get("registro_id", "")
    telefone = event.get("telefone", "")
    texto = (event.get("texto", "") or "").strip()
    etapa = sessao.get("etapa", "")
    tem_foto = event.get("tem_midia") and event.get("tipo_midia") == "imagem"

    if not arb_id:
        logger.warning(f"Resposta empresa sem arb_id: {telefone}")
        return

    # ── "1" = Aceitar OS ──
    _TTL_EMPRESA = 10080  # 7 dias em minutos

    if texto == "1":
        sb.table("arborizacao").update({"status": "em_execucao"}).eq("id", arb_id).execute()
        atualizar_sessao(sb, telefone, "em_execucao", contexto, ttl_minutos=_TTL_EMPRESA)
        enviar_whatsapp(telefone, "✅ OS aceita! Quando concluir, envie *3* + foto do serviço realizado.")
        logger.info(f"Empresa aceitou OS: {contexto.get('protocolo')}")

    # ── "2" = Equipe a caminho (aceita implicitamente) ──
    elif texto == "2":
        sb.table("arborizacao").update({"status": "em_execucao"}).eq("id", arb_id).execute()
        atualizar_sessao(sb, telefone, "em_execucao", contexto, ttl_minutos=_TTL_EMPRESA)
        enviar_whatsapp(telefone, "📍 Registrado: equipe a caminho. Quando concluir, envie *3* + foto.")
        logger.info(f"Empresa a caminho: {contexto.get('protocolo')}")

    # ── "3" ou FOTO = Serviço concluído ──
    elif texto == "3" or tem_foto:
        sb.table("arborizacao").update({
            "status": "concluido",
            "concluido_em": datetime.now(timezone.utc).isoformat(),
        }).eq("id", arb_id).execute()
        if tem_foto:
            _processar_midia_arb(event, sb, arb_id, "depois")
        finalizar_sessao(sb, telefone)
        enviar_whatsapp(telefone, "✅ Serviço registrado como concluído! Foto recebida para fiscalização.")
        logger.info(f"Arborização concluída pela empresa: {contexto.get('protocolo')}")

        # 🤖 AUTOMAÇÃO: fiscal IA + notificar cidadão
        _auto_fiscalizar_e_notificar(sb, arb_id)

    # ── "0" = Recusar ──
    elif texto == "0":
        sb.table("arborizacao").update({"status": "triado", "empresa_atribuida": None, "empresa_telefone": None}).eq("id", arb_id).execute()
        finalizar_sessao(sb, telefone)
        enviar_whatsapp(telefone, "Entendido. OS devolvida para reatribuição.")
        logger.info(f"Empresa recusou OS: {contexto.get('protocolo')}")

    # ── Mensagem não reconhecida ──
    else:
        enviar_whatsapp(telefone, "Responda com:\n1️⃣ Aceitar\n2️⃣ A caminho\n3️⃣ Concluído + foto\n0️⃣ Recusar")


def processar_arborizacao(event: dict, sb: Client) -> None:
    """Processa mensagens do canal arborização."""
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "")
    classificacao = event.get("classificacao", {})

    # Se é resposta de empresa contratada
    sessao = event.get("sessao", {})
    if sessao and sessao.get("canal") == "arborizacao_empresa":
        _processar_resposta_empresa(event, sb)
        return

    # Continuação de sessão do cidadão
    if is_continuacao:
        _continuar_arborizacao(event, sb)
        return

    # ── Nova solicitação ──
    tem_foto = event.get("tem_midia") and event.get("tipo_midia") == "imagem"

    # Se cidadão mandou COM foto → já temos classificação visual precisa
    if tem_foto:
        categoria = classificacao.get("categoria", "poda_geral")
        severidade = classificacao.get("urgencia", "rotina")
        _MAP_SEV = {"alta": "emergencia", "critica": "emergencia", "normal": "prioridade", "baixa": "rotina",
                    "emergencia": "emergencia", "urgencia": "urgencia", "prioridade": "prioridade", "rotina": "rotina"}
        severidade = _MAP_SEV.get(severidade, "rotina")
        if categoria in ("arvore_caida", "risco_queda") and severidade == "rotina":
            severidade = "urgencia"
        resumo = classificacao.get("resumo", texto[:200] if texto else "Solicitação de arborização")

        tem_loc = event.get("tem_localizacao", False)
        lat = event.get("latitude")
        lng = event.get("longitude")

        if tem_loc and lat and lng:
            # Foto + GPS → registra completo e despacha
            endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
            protocolo = gerar_protocolo_arb(sb)
            sla_horas, sla_vencimento = _calcular_sla_arb(severidade)
            foto_info = classificar_foto_origem(event)

            similar = _buscar_arborizacao_similar(sb, categoria, lat, lng, endereco_geo)
            if similar:
                enviar_whatsapp(telefone, f"🌳 Obrigado! Já temos uma solicitação nessa região.\n📋 Protocolo: *{similar['protocolo']}*")
                finalizar_sessao(sb, telefone)
                return

            res = sb.table("arborizacao").insert({
                "protocolo": protocolo, "telefone": telefone, "nome": push_name or None,
                "mensagem": texto, "categoria": categoria, "severidade": severidade, "resumo": resumo,
                "endereco": endereco_geo or f"GPS: {lat:.4f}, {lng:.4f}",
                "endereco_normalizado": _normalizar_endereco(endereco_geo or ""),
                "bairro": bairro_geo, "latitude": lat, "longitude": lng,
                "status": "recebido", "sla_horas": sla_horas, "sla_vencimento": sla_vencimento,
                "foto_origem": foto_info.get("foto_origem"), "foto_flag": foto_info.get("foto_flag"),
                "foto_flag_motivo": foto_info.get("foto_flag_motivo"),
            }).execute()
            registro_id = res.data[0]["id"]
            _processar_midia_arb(event, sb, registro_id, "antes")

            icone = _ICONE_ARB.get(categoria, "🌳")
            sev_label = {"emergencia": "🚨 EMERGÊNCIA", "urgencia": "⚠️ URGÊNCIA", "prioridade": "📋 PRIORIDADE", "rotina": "🌿 ROTINA"}
            resposta = (
                f"🌳 Solicitação registrada!\n\n"
                f"{icone} *{categoria.replace('_',' ').title()}*\n"
                f"{sev_label.get(severidade, severidade)}\n"
                f"📍 {endereco_geo or 'Localização recebida'}\n"
                f"📷 Foto recebida!\n\n"
                f"📋 Protocolo: *{protocolo}*\n"
                f"Encaminhando para a equipe!"
            )
            criar_sessao(sb, telefone, "arborizacao", "finalizado", registro_id, {"protocolo": protocolo, "categoria": categoria})
            finalizar_sessao(sb, telefone)
            enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
            _auto_despachar(sb, registro_id, protocolo)
            return

        # Foto sem GPS → guardar foto no contexto, pedir localização
        placeholder_id = str(uuid.uuid4())
        criar_sessao(sb, telefone, "arborizacao", "aguardando_endereco", placeholder_id, {
            "categoria": categoria, "severidade": severidade, "resumo": resumo,
            "texto_original": texto, "push_name": push_name or "", "_placeholder": True,
            "tem_foto_pendente": True, "message_id_foto": event.get("message_id", ""),
            "media_base64_flag": True,
        })
        icone = _ICONE_ARB.get(categoria, "🌳")
        sev_label = {"emergencia": "🚨 EMERGÊNCIA", "urgencia": "⚠️ URGÊNCIA", "prioridade": "📋 PRIORIDADE", "rotina": "🌿 ROTINA"}
        resposta = (
            f"📷 Foto recebida! Classificação:\n\n"
            f"{icone} *{categoria.replace('_',' ').title()}*\n"
            f"{sev_label.get(severidade, severidade)}\n\n"
            f"📍 Agora envie sua localização:\n"
            f"Clique em: 📎 > Localização\n"
            f"Ou me diga a rua e o bairro."
        )
        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
        return

    # ── Cidadão mandou TEXTO sem foto → PEDIR FOTO PRIMEIRO ──
    resposta = (
        f"🌳 Entendi que você tem um problema com árvore!\n\n"
        f"📷 *Envie uma foto* para avaliarmos a gravidade da situação.\n"
        f"A foto ajuda a IA a classificar a urgência e encaminhar corretamente.\n\n"
        f"📎 > Câmera ou Galeria"
    )
    placeholder_id = str(uuid.uuid4())
    criar_sessao(sb, telefone, "arborizacao", "aguardando_foto_inicial", placeholder_id, {
        "texto_original": texto, "push_name": push_name or "", "_placeholder": True,
        "classificacao_texto": classificacao,
    })
    enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
    enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))


def _continuar_arborizacao(event: dict, sb: Client) -> None:
    """Continua sessão de arborização do cidadão."""
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    texto = event.get("texto", "")
    etapa = sessao.get("etapa", "")
    contexto = sessao.get("contexto", {})
    registro_id = sessao.get("registro_id", "")

    if etapa == "aguardando_foto_inicial":
        # Cidadão mandou texto antes, agora esperamos a foto pra classificar com Vision
        tem_foto = event.get("tem_midia") and event.get("tipo_midia") == "imagem"

        if tem_foto:
            # Classificar com Vision IA
            import asyncio
            from app.services.classificador import classificar_imagem_arborizacao
            _mime = event.get("mimetype", "image/jpeg") or "image/jpeg"
            _b64 = event.get("media_base64", "")
            if _b64 and not _b64.startswith("data:"):
                image_url = f"data:{_mime};base64,{_b64}"
            else:
                image_url = _b64

            try:
                loop = asyncio.new_event_loop()
                resultado_vision = loop.run_until_complete(
                    classificar_imagem_arborizacao(image_url, contexto.get("texto_original", ""), telefone)
                )
                loop.close()
            except Exception as e:
                logger.error(f"Erro Vision arborização: {e}")
                resultado_vision = {"categoria": "poda_geral", "urgencia": "prioridade", "resumo": contexto.get("texto_original", "")}

            categoria = resultado_vision.get("categoria", "poda_geral")
            severidade = resultado_vision.get("urgencia", "prioridade")
            _MAP_SEV = {"alta": "emergencia", "critica": "emergencia", "normal": "prioridade", "baixa": "rotina",
                        "emergencia": "emergencia", "urgencia": "urgencia", "prioridade": "prioridade", "rotina": "rotina"}
            severidade = _MAP_SEV.get(severidade, "prioridade")
            if categoria in ("arvore_caida", "risco_queda") and severidade == "rotina":
                severidade = "urgencia"
            resumo = resultado_vision.get("resumo", contexto.get("texto_original", ""))

            # Atualizar sessão com classificação real e pedir localização
            novo_ctx = {**contexto,
                "categoria": categoria, "severidade": severidade, "resumo": resumo,
                "tem_foto_pendente": True, "message_id_foto": event.get("message_id", ""),
                "media_base64_flag": True,
            }
            atualizar_sessao(sb, telefone, "aguardando_endereco", novo_ctx)

            icone = _ICONE_ARB.get(categoria, "🌳")
            sev_label = {"emergencia": "🚨 EMERGÊNCIA", "urgencia": "⚠️ URGÊNCIA", "prioridade": "📋 PRIORIDADE", "rotina": "🌿 ROTINA"}
            resposta = (
                f"📷 Foto analisada pela IA!\n\n"
                f"{icone} Tipo: *{categoria.replace('_',' ').title()}*\n"
                f"{sev_label.get(severidade, severidade)}\n"
                f"📝 {resumo}\n\n"
                f"📍 Agora envie sua *localização*:\n"
                f"Clique em: 📎 > Localização\n"
                f"Ou me diga a rua e o bairro."
            )
            enviar_whatsapp(telefone, resposta)
        elif texto and texto.strip().lower() in ("pular", "não", "nao", "sem foto", "n"):
            # Sem foto → usar classificação de texto (menos precisa)
            cls_texto = contexto.get("classificacao_texto", {})
            novo_ctx = {**contexto,
                "categoria": cls_texto.get("categoria", "poda_geral"),
                "severidade": "prioridade",
                "resumo": cls_texto.get("resumo", contexto.get("texto_original", "")),
            }
            atualizar_sessao(sb, telefone, "aguardando_endereco", novo_ctx)
            enviar_whatsapp(telefone, "Ok! 📍 Envie sua localização ou me diga a rua e o bairro.")
        else:
            enviar_whatsapp(telefone, "📷 Envie uma *foto* do problema para avaliarmos a gravidade.\nOu digite *pular* para continuar sem foto.")
        return

    if etapa == "aguardando_endereco":
        lat = event.get("latitude")
        lng = event.get("longitude")

        if lat and lng:
            endereco_geo, bairro_geo = _geocodificar_sync(lat, lng)
        elif texto:
            # Tentar geocodificar texto como endereço
            try:
                geo_url = (
                    f"https://api.mapbox.com/geocoding/v5/mapbox.places/"
                    f"{urllib.parse.quote(texto + ', Maringá, Paraná, Brasil')}.json"
                    f"?access_token={MAPBOX_TOKEN}&limit=1"
                )
                geo_resp = httpx.get(geo_url, timeout=5.0)
                if geo_resp.status_code == 200:
                    feats = geo_resp.json().get("features", [])
                    if feats:
                        coords = feats[0]["geometry"]["coordinates"]
                        lng, lat = coords[0], coords[1]
                        endereco_geo = feats[0].get("place_name", texto)
                        bairro_geo = ""
                        for ctx_item in feats[0].get("context", []):
                            if "neighborhood" in ctx_item.get("id", "") or "locality" in ctx_item.get("id", ""):
                                bairro_geo = ctx_item.get("text", "")
                                break
                    else:
                        endereco_geo, bairro_geo = texto, ""
                        lat, lng = None, None
                else:
                    endereco_geo, bairro_geo = texto, ""
                    lat, lng = None, None
            except Exception:
                endereco_geo, bairro_geo = texto, ""
                lat, lng = None, None
        else:
            enviar_whatsapp(telefone, "📍 Preciso do endereço para registrar. Envie sua localização ou digite a rua e bairro.")
            return

        categoria = contexto.get("categoria", "poda_geral")
        severidade = contexto.get("severidade", "rotina")
        resumo = contexto.get("resumo", contexto.get("texto_original", ""))
        push_name = contexto.get("push_name", "")
        protocolo = gerar_protocolo_arb(sb)
        sla_horas, sla_vencimento = _calcular_sla_arb(severidade)

        res = sb.table("arborizacao").insert({
            "protocolo": protocolo,
            "telefone": telefone,
            "nome": push_name or None,
            "mensagem": contexto.get("texto_original", ""),
            "categoria": categoria,
            "severidade": severidade,
            "resumo": resumo,
            "endereco": endereco_geo or f"GPS: {lat:.4f}, {lng:.4f}" if lat else "Endereço informado via texto",
            "endereco_normalizado": _normalizar_endereco(endereco_geo or texto or ""),
            "bairro": bairro_geo or "",
            "latitude": lat,
            "longitude": lng,
            "status": "recebido",
            "sla_horas": sla_horas,
            "sla_vencimento": sla_vencimento,
        }).execute()

        novo_id = res.data[0]["id"]

        # Upload foto pendente se existir
        if contexto.get("tem_foto_pendente") and contexto.get("message_id_foto"):
            _processar_midia_arb({
                "message_id": contexto["message_id_foto"],
                "media_base64": event.get("media_base64", ""),
                "mimetype": "image/jpeg",
            }, sb, novo_id, "antes")

        icone = _ICONE_ARB.get(categoria, "🌳")
        sev_label = {"emergencia": "🚨 EMERGÊNCIA", "urgencia": "⚠️ URGÊNCIA", "prioridade": "📋 PRIORIDADE", "rotina": "🌿 ROTINA"}
        resposta = (
            f"🌳 Solicitação registrada com sucesso!\n\n"
            f"{icone} *{categoria.replace('_', ' ').title()}*\n"
            f"{sev_label.get(severidade, severidade)}\n"
            f"📍 {endereco_geo or texto}\n\n"
            f"📋 Protocolo: *{protocolo}*\n"
            f"Vamos encaminhar para a equipe responsável!"
        )
        criar_sessao(sb, telefone, "arborizacao", "finalizado", novo_id,
                     {"protocolo": protocolo, "categoria": categoria})
        finalizar_sessao(sb, telefone)
        enviar_whatsapp(telefone, resposta)
        logger.info(f"Arborização registrada (continuação): {protocolo}")

        # 🤖 AUTOMAÇÃO: auto-triagem + auto-atribuição + despacho
        _auto_despachar(sb, novo_id, protocolo)

    elif etapa == "aguardando_avaliacao":
        # Cidadão enviou avaliação (1-5)
        try:
            nota = int(texto.strip())
            if 1 <= nota <= 5:
                sb.table("arborizacao").update({
                    "cidadao_avaliacao": nota,
                }).eq("id", registro_id).execute()
                estrelas = "⭐" * nota
                enviar_whatsapp(telefone, f"{estrelas}\nObrigado pela sua avaliação! Maringá agradece sua participação! 🌳💙")
                finalizar_sessao(sb, telefone)
            else:
                enviar_whatsapp(telefone, "Por favor, avalie de 1 a 5 estrelas.")
        except ValueError:
            enviar_whatsapp(telefone, "Por favor, envie um número de 1 a 5 para avaliar o serviço.")

    else:
        finalizar_sessao(sb, telefone)


def _verificar_sla_arborizacao(sb: Client) -> None:
    """Verifica SLAs estourados e notifica empresas."""
    try:
        agora = datetime.now(timezone.utc).isoformat()
        result = sb.table("arborizacao").select(
            "id, protocolo, empresa_telefone, empresa_atribuida, sla_vencimento, status"
        ).lt("sla_vencimento", agora).eq(
            "sla_estourado", False
        ).not_.in_("status", ["concluido", "fiscalizado", "recebido"]).execute()

        for arb in (result.data or []):
            sb.table("arborizacao").update({"sla_estourado": True}).eq("id", arb["id"]).execute()
            if arb.get("empresa_telefone"):
                enviar_whatsapp(arb["empresa_telefone"],
                    f"⚠️ *SLA ESTOURADO* — {arb['protocolo']}\n"
                    f"O prazo para esta OS venceu. Atualize o status urgentemente.")
            logger.warning(f"SLA arborização estourado: {arb['protocolo']}")
    except Exception as exc:
        logger.error(f"Erro verificação SLA arborização: {exc}")


PROCESSADORES = {
    "queue:sos": processar_sos,
    "queue:denuncias": processar_denuncia,
    "queue:ocorrencias": processar_ocorrencia,
    "queue:arborizacao": processar_arborizacao,
    "queue:feedbacks": processar_feedback,
    "queue:consultas": processar_consulta_protocolo,
    "queue:saudacoes": processar_saudacao,
}


def conectar():
    while True:
        try:
            r = redis_lib.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=30,        # Precisa ser MAIOR que o timeout do blpop (5s)
                retry_on_timeout=True,    # Reconecta automaticamente em vez de crashar
                health_check_interval=15, # Ping periódico pra manter conexão viva
            )
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

    _sla_counter = 0
    while True:
        try:
            resultado = r.blpop(QUEUES, timeout=5)
            if resultado is None:
                _sla_counter += 1
                if _sla_counter >= 60:  # ~5 minutos (60 * 5s timeout)
                    _sla_counter = 0
                    try:
                        _verificar_sla_arborizacao(sb)
                    except Exception as sla_exc:
                        logger.error(f"Erro SLA check: {sla_exc}")
                continue

            fila, raw = resultado
            logger.info(f"Fila '{fila}' → processando...")
            event = json.loads(raw)
            proc = PROCESSADORES.get(fila)
            if proc:
                proc(event, sb)
            else:
                logger.warning(f"Sem processador: {fila}")

        except (redis_lib.exceptions.ConnectionError, redis_lib.exceptions.TimeoutError) as exc:
            logger.error(f"Redis conexão/timeout: {exc}. Reconectando...")
            time.sleep(2)
            r, sb = conectar()
        except json.JSONDecodeError as exc:
            logger.error(f"JSON invalido: {exc}")
        except Exception as exc:
            logger.exception(f"Erro: {exc}")


if __name__ == "__main__":
    main()
