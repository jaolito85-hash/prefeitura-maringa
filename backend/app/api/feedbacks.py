"""
feedbacks.py — Endpoints REST para a aba Feedbacks
Gerencia mensagens de cidadãos via WhatsApp categorizadas pela IA.
"""
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

router = APIRouter()


@router.get("/")
async def listar_feedbacks(
    categoria: str = Query(None),
    prioridade: str = Query(None),
    status: str = Query(None),
    limit: int = Query(50),
):
    sb = get_supabase()
    query = sb.table("feedbacks").select("*").order("created_at", desc=True)

    if categoria:
        query = query.eq("categoria", categoria)
    if prioridade:
        query = query.eq("prioridade", prioridade)
    if status:
        query = query.eq("status", status)

    result = query.limit(limit).execute()
    return result.data or []


@router.get("/{feedback_id}/mensagens")
async def mensagens_do_feedback(feedback_id: str):
    """Retorna o histórico de mensagens (conversa WhatsApp) de um feedback."""
    sb = get_supabase()
    result = (
        sb.table("feedbacks_mensagens")
        .select("*")
        .eq("feedback_id", feedback_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


@router.patch("/{feedback_id}/status")
async def atualizar_status(feedback_id: str, body: dict):
    """Atualiza o status de um feedback (aberto, em_atendimento, resolvido)."""
    sb = get_supabase()
    novo_status = body.get("status")
    if not novo_status:
        return {"error": "status é obrigatório"}

    result = (
        sb.table("feedbacks")
        .update({"status": novo_status})
        .eq("id", feedback_id)
        .execute()
    )
    return result.data[0] if result.data else {"error": "não encontrado"}
