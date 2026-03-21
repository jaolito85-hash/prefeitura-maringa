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

    if not tem_midia:
        etapa = "aguardando_midia"
        resposta = (f"✅ Recebido, {push_name or 'cidadão'}! Sua denúncia de *{categoria.replace('_', ' ')}* "
                    f"foi registrada.\n\n"
                    f"📸 Consegue enviar uma foto ou vídeo como evidência? "
                    f"Isso fortalece muito a investigação.\n\n"
                    f"📋 Protocolo: {protocolo}")
    elif not tem_loc:
        etapa = "aguardando_endereco"
        resposta = (f"✅ Foto recebida! Agora preciso da localização.\n\n"
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
        # Midia em qualquer etapa — aceita
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
        nova_etapa = etapa_atual
        resposta = f"📸 Foto recebida! Obrigado pela evidência adicional."

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
