"""
sos.py — Endpoints REST para a aba SOS Mulher
"""
import logging
import os

import httpx
from fastapi import APIRouter
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.sos")

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

router = APIRouter()


@router.get("/alertas")
async def listar_alertas_sos():
    """Retorna todos os alertas SOS com dados da vítima (quando cadastrada)."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, agressor_foto_url, contato_confianca_nome, contato_confianca_telefone, medida_protetiva)"
    ).order("created_at", desc=True).limit(50).execute()
    return result.data or []


@router.get("/alertas/ativos")
async def alertas_sos_ativos():
    """Retorna apenas os alertas SOS com status 'active' ou 'attending' — para o painel."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, agressor_foto_url, contato_confianca_nome, contato_confianca_telefone, medida_protetiva)"
    ).in_("status", ["active", "attending"]).order("created_at", desc=True).execute()
    return result.data or []


@router.get("/alertas/historico")
async def historico_sos():
    """Retorna alertas resolvidos — para o histórico na sidebar."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, agressor_foto_url, contato_confianca_nome, contato_confianca_telefone, telefone, medida_protetiva)"
    ).eq("status", "resolved").order("resolvido_em", desc=True).limit(20).execute()
    return result.data or []


@router.patch("/alertas/{alerta_id}/aceitar")
async def aceitar_atendimento(alerta_id: str, body: dict):
    """
    Operador clica em 'Aceitar Atendimento' no painel.
    Para o som de sirene e muda status para 'attending'.
    """
    sb = get_supabase()
    result = sb.table("sos_alertas").update({
        "status": "attending",
        "atendido_por": body.get("operador"),
    }).eq("id", alerta_id).execute()
    return result.data[0] if result.data else {}


@router.patch("/alertas/{alerta_id}/resolver")
async def resolver_alerta(alerta_id: str, body: dict):
    """Marca o alerta como resolvido."""
    from datetime import datetime, timezone
    sb = get_supabase()
    result = sb.table("sos_alertas").update({
        "status": "resolved",
        "notas": body.get("notas"),
        "resolvido_em": datetime.now(timezone.utc).isoformat(),
    }).eq("id", alerta_id).execute()
    return result.data[0] if result.data else {}


@router.patch("/alertas/{alerta_id}/notas")
async def salvar_notas(alerta_id: str, body: dict):
    """Salva notas do operador no alerta."""
    sb = get_supabase()
    result = sb.table("sos_alertas").update({
        "notas": body.get("notas", ""),
    }).eq("id", alerta_id).execute()
    return result.data[0] if result.data else {}


@router.get("/alertas/{alerta_id}/mensagens")
async def listar_mensagens_sos(alerta_id: str):
    """Retorna todas as mensagens do chat SOS (vítima + operador)."""
    sb = get_supabase()
    result = sb.table("sos_mensagens").select("*").eq(
        "alerta_id", alerta_id
    ).order("created_at", desc=False).execute()
    return result.data or []


@router.post("/alertas/{alerta_id}/handoff")
async def sos_handoff_toggle(alerta_id: str, body: dict):
    """Ativa/desativa handoff (atendimento humano) para a vítima SOS."""
    from datetime import datetime, timezone, timedelta

    sb = get_supabase()
    telefone = body.get("telefone", "")
    ativo = body.get("ativo", False)
    operador = body.get("operador", "admin")

    # Upsert sessão — garante que a sessão existe e não está expirada/finalizada
    # Isso é crítico: se a sessão foi finalizada, o handoff não funciona
    try:
        if ativo:
            expira_em = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            sb.table("sessoes_conversa").upsert({
                "telefone": telefone,
                "canal": "sos_mulher",
                "etapa": "handoff",
                "registro_id": alerta_id,
                "contexto": {"tipo": "emergencia", "handoff": True},
                "expira_em": expira_em,
                "handoff_ativo": True,
                "handoff_operador": operador,
            }, on_conflict="telefone").execute()
        else:
            sb.table("sessoes_conversa").update({
                "handoff_ativo": False,
                "handoff_operador": "",
                "etapa": "finalizado",
            }).eq("telefone", telefone).execute()
    except Exception as exc:
        logger.error(f"Erro ao atualizar sessão handoff SOS: {exc}")

    # Avisar a vítima
    if EVOLUTION_API_URL and EVOLUTION_API_KEY:
        numero = telefone.lstrip("+")
        if ativo:
            msg = "Um atendente está entrando na conversa para te ajudar."
        else:
            msg = "O atendimento voltou ao nosso assistente virtual."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}",
                    headers={"apikey": EVOLUTION_API_KEY},
                    json={"number": numero, "text": msg},
                )
        except Exception as exc:
            logger.error(f"Erro ao enviar msg handoff SOS: {exc}")

    return {"status": "ok", "handoff_ativo": ativo}


@router.post("/alertas/{alerta_id}/send-message")
async def send_sos_message(alerta_id: str, body: dict):
    """Envia mensagem do operador para a vítima via WhatsApp e salva no histórico."""
    telefone = body.get("telefone", "")
    mensagem = body.get("mensagem", "")
    operador = body.get("operador", "Atendente SOS")

    if not telefone or not mensagem:
        return {"error": "telefone e mensagem obrigatórios"}

    # Salvar no histórico de mensagens
    sb = get_supabase()
    try:
        sb.table("sos_mensagens").insert({
            "alerta_id": alerta_id,
            "telefone": "operador",
            "nome": operador,
            "mensagem": f"[ATENDENTE] {mensagem}",
            "remetente": "operador",
        }).execute()
    except Exception as exc:
        logger.error(f"Erro ao salvar msg operador SOS: {exc}")

    if EVOLUTION_API_URL and EVOLUTION_API_KEY:
        numero = telefone.lstrip("+")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}",
                    headers={"apikey": EVOLUTION_API_KEY},
                    json={"number": numero, "text": f"*{operador}:*\n{mensagem}"},
                )
        except Exception as exc:
            logger.error(f"Erro ao enviar msg SOS: {exc}")
            return {"error": str(exc)}

    return {"status": "sent"}
