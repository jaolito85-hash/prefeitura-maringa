"""
sos.py — Endpoints REST para a aba SOS Mulher
"""
from fastapi import APIRouter
from app.services.supabase_client import get_supabase

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
    """Retorna apenas os alertas SOS com status 'active' — para o alerta vermelho."""
    sb = get_supabase()
    result = sb.table("sos_alertas").select(
        "*, sos_cadastros(nome, endereco, referencia, agressor, contato_confianca_nome, contato_confianca_telefone)"
    ).eq("status", "active").order("created_at", desc=True).execute()
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
