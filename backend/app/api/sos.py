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
        "*, sos_cadastros(nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone)"
    ).order("created_at", desc=True).limit(50).execute()
    return result.data or []


@router.get("/alertas/ativos")
async def alertas_sos_ativos():
    """Retorna apenas os alertas SOS com status 'active' ou 'attending' — para o painel."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone)"
    ).in_("status", ["active", "attending"]).order("created_at", desc=True).execute()
    return result.data or []


@router.get("/alertas/historico")
async def historico_sos():
    """Retorna alertas resolvidos — para o histórico na sidebar."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone, telefone)"
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


@router.post("/alertas/{alerta_id}/send-message")
async def send_sos_message(alerta_id: str, body: dict):
    """Envia mensagem do operador para a vítima via WhatsApp."""
    telefone = body.get("telefone", "")
    mensagem = body.get("mensagem", "")
    operador = body.get("operador", "Atendente SOS")

    if not telefone or not mensagem:
        return {"error": "telefone e mensagem obrigatórios"}

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
