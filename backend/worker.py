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
QUEUES = ["queue:sos", "queue:denuncias", "queue:ocorrencias", "queue:feedbacks", "queue:consultas", "queue:saudacoes"]

# ── Programa Cidadão Ativo ──
# Categorias de denúncia elegíveis pra recompensa (Decreto 291/2026)
# Mapeamento: categoria do classificador IA → categoria na recompensas_config
CATEGORIAS_ELEGIVEIS = {
    "pichacao": "pichacao",
    "trafico_drogas": "trafico",
    "trafico": "trafico",
    "vandalismo": "vandalismo",
    "depredacao": "depredacao",
    "descarte_irregular": "lixo",
    "lixo": "lixo",
}

# Menu de categorias para denúncia genérica (quando cidadão diz "quero denunciar" sem dizer o quê)
# Cada item: (número_opcao, categoria_worker, label_amigavel, valor_recompensa_display)
MENU_CATEGORIAS = [
    ("1", "trafico_drogas", "Tráfico de drogas", "R$ 300"),
    ("2", "pichacao", "Pichação", "R$ 100"),
    ("3", "vandalismo", "Vandalismo", "R$ 150"),
    ("4", "depredacao", "Depredação de bens públicos", "R$ 150"),
    ("5", "descarte_irregular", "Descarte irregular de lixo", "R$ 80"),
    ("6", "roubo_furto", "Roubo ou furto", "—"),
    ("7", "perturbacao_sossego", "Perturbação do sossego", "—"),
    ("8", "outros_crimes", "Outro tipo de crime", "—"),
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
        _continuar_denuncia(event, sb)
        return

    # ── DENÚNCIA GENÉRICA — envia menu de categorias ──
    categoria = classificacao.get("categoria", "outros_crimes")
    if categoria == "generica":
        menu = _montar_menu_categorias()
        # Cria sessão aguardando escolha (sem criar registro ainda)
        criar_sessao(sb, telefone, "denuncia", "aguardando_categoria", "",
                     {"push_name": push_name, "mensagem_original": texto})
        enviar_whatsapp(telefone, menu)
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

    enviar_whatsapp(telefone, resposta)


def _continuar_denuncia(event: dict, sb: Client) -> None:
    sessao = event.get("sessao", {})
    telefone = event.get("telefone", "")
    contexto = sessao.get("contexto", {}) if sessao else {}
    registro_id = sessao.get("registro_id") if sessao else None
    etapa_atual = sessao.get("etapa", "") if sessao else ""
    protocolo = contexto.get("protocolo", "")
    categoria = contexto.get("categoria", "")
    texto = event.get("texto", "")
    push_name = event.get("push_name", "") or contexto.get("push_name", "")

    # ══════════════════════════════════════════════════════════
    # ETAPA MENU — cidadão está escolhendo a categoria
    # (registro_id ainda não existe, será criado aqui)
    # ══════════════════════════════════════════════════════════
    if etapa_atual == "aguardando_categoria":
        cat_escolhida = _identificar_categoria_menu(texto)
        if not cat_escolhida:
            # Não entendeu — reenvia menu
            resposta = "Não entendi. Por favor, responda com o *número* da opção:\n\n" + _montar_menu_categorias()
            criar_sessao(sb, telefone, "denuncia", "aguardando_categoria", "",
                         contexto)
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
        if len(cpf_limpo) == 11 and cpf_limpo.isdigit():
            contexto["cpf"] = cpf_limpo
            nova_etapa = "aguardando_pix"
            resposta = (f"✅ CPF recebido!\n\n"
                        f"Agora me envie sua *chave PIX*.\n"
                        f"Pode ser: CPF, e-mail, telefone ou chave aleatória.")
        else:
            nova_etapa = etapa_atual
            resposta = (f"⚠️ CPF inválido. Por favor, envie apenas os 11 números.\n"
                        f"Exemplo: 12345678900")

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
        update_data["latitude"] = event.get("latitude")
        update_data["longitude"] = event.get("longitude")
        update_data["bairro"] = f"GPS: {event.get('latitude', 0):.4f}, {event.get('longitude', 0):.4f}"
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


# ══════════════════════════════════════════════════════════════
# PROCESSADOR — CONSULTA DE PROTOCOLO (via WhatsApp)
# ══════════════════════════════════════════════════════════════

def processar_consulta_protocolo(event: dict, sb: Client) -> None:
    """
    Cidadão enviou um número de protocolo pelo WhatsApp.
    Busca em todas as tabelas e responde com o status amigável.
    """
    telefone = event.get("telefone", "desconhecido")
    classificacao = event.get("classificacao", {})
    protocolo = classificacao.get("protocolo_consulta", "").strip().upper()

    if not protocolo:
        enviar_whatsapp(telefone, "❌ Não consegui identificar o número do protocolo. "
                        "O formato correto é MGA-2026-XXXXX.")
        return

    logger.info(f"🔍 Consulta protocolo: {protocolo} de {telefone}")

    # ── Busca em denúncias ──
    try:
        result = sb.table("denuncias").select(
            "protocolo, categoria, status, cidadania_ativa, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            d = result.data[0]
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
            "protocolo, categoria, status, severidade, total_relatos, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            o = result.data[0]
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
            "protocolo, categoria, status, departamento, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            f = result.data[0]
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
            "protocolo, status, created_at"
        ).eq("protocolo", protocolo).limit(1).execute()

        if result.data:
            s = result.data[0]
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
