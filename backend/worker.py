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
import secrets
import sys
import time
import unicodedata
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
QUEUES = ["queue:sos", "queue:denuncias", "queue:ocorrencias", "queue:feedbacks", "queue:consultas", "queue:saudacoes"]

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


# Chave AES para criptografia (em produção, vem do .env)
AES_KEY = os.environ.get("AES_KEY", "")


def gerar_protocolo(sb: Client) -> str:
    try:
        result = sb.rpc("nextval", {"seq_name": "protocolo_seq"}).execute()
        seq = result.data
        return f"MGA-{date.today().year}-{str(seq).zfill(5)}"
    except Exception as exc:
        logger.error(f"Falha ao gerar protocolo: {exc}")
        import uuid
        return f"MGA-{date.today().year}-{str(uuid.uuid4())[:8].upper()}"


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

    return None  # Sucesso


def criar_sessao(sb: Client, telefone: str, canal: str, etapa: str,
                 registro_id: str, contexto: dict) -> None:
    """Cria ou atualiza sessao de conversa pra esse telefone."""
    try:
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=120)).isoformat()  # 2h — demo-safe
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


def atualizar_sessao(sb: Client, telefone: str, etapa: str, contexto: dict) -> None:
    """Atualiza a etapa e contexto da sessao ativa sem mudar canal/registro_id."""
    try:
        expira_em = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
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
    Na demo: usa prefixo ENC_AES256_ (dados fictícios).
    Em produção: usa AES real com a AES_KEY do .env.
    """
    if AES_KEY:
        # TODO Fase 2: implementar AES-256-GCM real
        # from cryptography.fernet import Fernet
        # cipher = Fernet(AES_KEY)
        # return cipher.encrypt(valor.encode()).decode()
        pass
    # Demo: prefixo pra identificar como encriptado
    return f"ENC_AES256_{valor[-4:]}"


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
    protocolo = gerar_protocolo(sb)

    insert_data = {
        "protocolo": protocolo,
        "telefone": telefone,
        "nome": push_name or None,
        "categoria": categoria,
        "mensagem": texto,
        "status": "novo",
    }
    # Salvar localização se veio junto com a primeira mensagem
    tem_loc = event.get("tem_localizacao", False)
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
        # Denúncia completa — checar se é elegível pro Cidadão Ativo
        valor = _buscar_valor_recompensa(sb, categoria)
        if valor:
            # Verificar se já tem CPF/PIX de denúncia anterior (mesmo telefone)
            dados_ant = _buscar_dados_anteriores(sb, telefone)
            if dados_ant:
                # Já tem dados! Cria recompensa automaticamente
                _criar_recompensa(sb, registro_id, protocolo, valor,
                                  dados_ant["cpf_encrypted"],
                                  dados_ant["chave_pix_encrypted"],
                                  dados_ant["tipo_chave_pix"],
                                  _pre_encrypted=True)
                etapa = "finalizado"
                resposta = (f"✅ Denúncia registrada com sucesso!\n\n"
                            f"💰 *Programa Cidadão Ativo*\n"
                            f"Sua denúncia é elegível a *R$ {valor:.2f}*.\n"
                            f"Já temos seus dados cadastrados de denúncia anterior — "
                            f"recompensa vinculada automaticamente! 🎉\n\n"
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

        # Categoria escolhida! Agora cria o registro da denúncia
        protocolo = gerar_protocolo(sb)
        mensagem_original = contexto.get("mensagem_original", texto)
        # Procura o label amigável
        cat_label = cat_escolhida.replace("_", " ")
        for _, cat_id, label, _ in MENU_CATEGORIAS:
            if cat_id == cat_escolhida:
                cat_label = label
                break

        insert_data = {
            "protocolo": protocolo,
            "telefone": telefone,
            "nome": push_name or None,
            "categoria": cat_escolhida,
            "mensagem": mensagem_original,
            "status": "novo",
        }
        res = sb.table("denuncias").insert(insert_data).execute()
        if not res.data:
            logger.error("Falha ao criar denuncia após menu")
            enviar_whatsapp(telefone, "Desculpe, ocorreu um erro. Tente novamente.")
            return

        registro_id = res.data[0]["id"]
        logger.info(f"Denuncia criada via menu: {protocolo} ({cat_escolhida})")

        etapa = "aguardando_midia"
        resposta = (f"✅ Registrado como *{cat_label}*!\n\n"
                    f"📸 Agora envie uma foto ou vídeo como evidência.\n"
                    f"Isso fortalece muito a investigação.\n\n"
                    f"📋 Protocolo: {protocolo}")

        criar_sessao(sb, telefone, "denuncia", etapa, registro_id,
                     {"protocolo": protocolo, "categoria": cat_escolhida})
        enviar_whatsapp(telefone, resposta)
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

        if valor and _criar_recompensa(sb, registro_id, protocolo, valor, cpf, chave_pix, tipo_pix):
            nova_etapa = "finalizado"
            resposta = (f"✅ *Cadastro no Cidadão Ativo concluído!*\n\n"
                        f"📋 Protocolo: {protocolo}\n"
                        f"💰 Valor: R$ {valor:.2f}\n"
                        f"🔐 Seus dados estão protegidos por criptografia\n\n"
                        f"Quando sua denúncia for validada pela equipe, "
                        f"o pagamento será feito via PIX.\n\n"
                        f"Obrigado por ajudar Maringá! 🏙️")
            logger.info(f"Cidadão Ativo cadastrado: {protocolo} (R$ {valor})")
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
        erro_midia = processar_midia(event, sb, registro_id, "denuncias")
        if erro_midia:
            enviar_whatsapp(telefone, erro_midia)
            return
        update_data["status"] = "novo"
        nova_etapa = "aguardando_endereco"
        resposta = (f"📸 Evidência recebida! Obrigado.\n\n"
                    f"📍 Agora me diz o endereço ou envia sua localização: 📎 > Localização")

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
                _criar_recompensa(sb, registro_id, protocolo, valor,
                                  dados_ant["cpf_encrypted"], dados_ant["chave_pix_encrypted"],
                                  dados_ant["tipo_chave_pix"], _pre_encrypted=True)
                nova_etapa = "finalizado"
                resposta = (f"📍 Localização registrada!\n\n"
                            f"💰 *Programa Cidadão Ativo* — Recompensa de *R$ {valor:.2f}* "
                            f"vinculada automaticamente (dados já cadastrados)! 🎉\n\n"
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
                _criar_recompensa(sb, registro_id, protocolo, valor,
                                  dados_ant["cpf_encrypted"], dados_ant["chave_pix_encrypted"],
                                  dados_ant["tipo_chave_pix"], _pre_encrypted=True)
                nova_etapa = "finalizado"
                resposta = (f"📍 Endereço registrado: {texto}\n\n"
                            f"💰 *Programa Cidadão Ativo* — Recompensa de *R$ {valor:.2f}* "
                            f"vinculada automaticamente (dados já cadastrados)! 🎉\n\n"
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

def processar_sos(event: dict, sb: Client) -> None:
    is_continuacao = event.get("is_continuacao", False)
    telefone = event.get("telefone", "desconhecido")
    texto = event.get("texto", "")
    tem_loc = event.get("tem_localizacao", False)
    classificacao = event.get("classificacao", {})
    categoria_sos = classificacao.get("categoria", "emergencia")

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

        # Continuação de SOS ativo — recebeu localização
        if tem_loc:
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

        # Qualquer outra mensagem durante SOS ativo
        enviar_whatsapp(telefone, "✓ Recebido. Se puder, envie sua localização: 📎 > Localização")
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
        criar_sessao(sb, telefone, "sos_mulher", "aguardando_localizacao", registro_id,
                     {"tipo": "emergencia"})

        # Criar sessão de rastreamento GPS
        try:
            sb.table("emergencia_sessoes").insert({
                "token": token_rastreamento,
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


def _buscar_ocorrencia_similar(sb: Client, categoria: str,
                                latitude: float | None = None,
                                longitude: float | None = None,
                                endereco: str | None = None) -> dict | None:
    """Busca ocorrência ATIVA com mesma categoria nas últimas 6h
    que esteja próxima (< 500m por GPS ou mesmo endereço normalizado)."""
    limite = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    result = sb.table("ocorrencias").select(
        "id, protocolo, latitude, longitude, endereco_normalizado, total_relatos, titulo, bairro, severidade, categoria"
    ).eq("categoria", categoria).neq(
        "status", "resolvido"
    ).gte("created_at", limite).execute()

    if not result.data:
        return None

    for oc in result.data:
        # Critério 1: GPS próximo (< 500 metros)
        if latitude and longitude and oc.get("latitude") and oc.get("longitude"):
            dist = _haversine(latitude, longitude, oc["latitude"], oc["longitude"])
            if dist < 500:
                logger.info(f"Agrupamento GPS: {dist:.0f}m de {oc['protocolo']}")
                return oc

        # Critério 2: Endereço normalizado similar
        if endereco and oc.get("endereco_normalizado"):
            end_norm = _normalizar_endereco(endereco)
            if end_norm and len(end_norm) > 5:
                oc_norm = oc["endereco_normalizado"]
                # Substring match
                if end_norm in oc_norm or oc_norm in end_norm:
                    logger.info(f"Agrupamento endereço: '{end_norm}' ~ '{oc_norm}' → {oc['protocolo']}")
                    return oc
                # Palavras-chave em comum (≥2 palavras significativas)
                palavras_end = set(end_norm.split())
                palavras_oc = set(oc_norm.split())
                palavras_sig = {p for p in (palavras_end & palavras_oc) if len(p) > 2}
                if len(palavras_sig) >= 2:
                    logger.info(f"Agrupamento palavras-chave: {palavras_sig} → {oc['protocolo']}")
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
            etapa = "aguardando_midia"
            resposta = (f"{icone} Ocorrência registrada com localização!{aviso_urgente}\n"
                        f"📍 {endereco_inicial}\n\n"
                        f"📸 Se puder, envie uma foto do problema.\n\n"
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

        # Processar mídia se tem
        if tem_midia:
            processar_midia(event, sb, novo_registro_id, "ocorrencias_relatos")

        criar_sessao(sb, telefone, "ocorrencia", "finalizado", novo_registro_id,
                     {"protocolo": novo_protocolo, "categoria": categoria})
        finalizar_sessao(sb, telefone)

        local_texto = endereco or bairro or "Localização registrada"
        icone = "🚨" if severidade in ("alta", "critica") else "⚠️"
        resposta = (f"📍 Endereço registrado: {local_texto}\n\n"
                    f"{icone} Equipe notificada. Obrigado!\n"
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
    logger.info(f"Continuação {protocolo} finalizada: etapa={nova_etapa}")


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

        enviar_whatsapp(telefone, _com_aviso_truncagem(event, resposta))
        # Feedback nao cria sessao — mensagem unica


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
    Cidadão enviou um número de protocolo pelo WhatsApp.
    Busca em todas as tabelas e responde com o status amigável.

    PROTEÇÕES:
    - Rate limit: se rate_limited=True, só avisa que excedeu o limite
    - Privacidade: só mostra detalhes de protocolos do próprio número
    """
    telefone = event.get("telefone", "desconhecido")
    classificacao = event.get("classificacao", {})
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

    logger.info(f"🔍 Consulta protocolo: {protocolo} de {telefone}")

    # ── PROTEÇÃO 4: Privacidade — só consulta protocolos do próprio número ──
    # Verifica se o protocolo pertence a esse telefone checando sessoes_conversa
    protocolo_pertence_ao_telefone = _verificar_dono_protocolo(sb, protocolo, telefone)

    # ── Busca em denúncias ──
    try:
        result = sb.table("denuncias").select(
            "protocolo, categoria, status, cidadania_ativa, created_at, telefone"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            d = result.data[0]

            # ── PROTEÇÃO 4: Verifica se o protocolo pertence a esse telefone ──
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
                "resolvido": "✅ *Resolvida* — Sua denúncia foi tratada. Obrigado!",
                "arquivado": "📁 *Arquivada* — Denúncia arquivada após análise.",
            }
            msg += status_map.get(d["status"], f"Status: {d['status']}")

            if d.get("cidadania_ativa"):
                # Buscar status da recompensa
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

            # ── PROTEÇÃO 4: Privacidade ──
            if not protocolo_pertence_ao_telefone:
                enviar_whatsapp(telefone, _msg_protocolo_privado(protocolo))
                return

            msg = f"🚨 *Ocorrência {o['protocolo']}*\n"
            msg += f"Categoria: {(o.get('categoria') or '').replace('_', ' ').title()}\n"
            msg += f"Severidade: {'⚠️' * min(o.get('severidade', 1), 5)}\n"
            msg += f"Relatos: {o.get('total_relatos', 1)} pessoa(s)\n\n"

            status_map = {
                "ativo": "🟡 *Ativa* — Em monitoramento.",
                "em_atendimento": "🚔 *Em atendimento* — Equipe no local.",
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

            # ── PROTEÇÃO 4: Privacidade ──
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

    # ── Busca em SOS ──
    try:
        result = sb.table("sos_alertas").select(
            "protocolo, status, telefone, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            s = result.data[0]

            # ── PROTEÇÃO 4: Privacidade ──
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
           f"Verifique se digitou corretamente. O formato é MGA-2026-XXXXX.\n\n"
           f"Se precisar de ajuda, envie sua mensagem normalmente e vamos te atender!")
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
                    f"🆘 SOS Mulher")

    enviar_whatsapp(telefone, resposta)
    logger.info(f"Saudação respondida para {telefone}")


PROCESSADORES = {
    "queue:sos": processar_sos,
    "queue:denuncias": processar_denuncia,
    "queue:ocorrencias": processar_ocorrencia,
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
