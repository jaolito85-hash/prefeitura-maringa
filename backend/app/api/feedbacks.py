"""
feedbacks.py — Endpoints REST para a aba Feedbacks do Dashboard
"""
import logging
import os

import httpx
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.feedbacks")

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

router = APIRouter()


@router.get("/")
async def listar_feedbacks(
    status: str = Query(None),
    categoria: str = Query(None),
    sentimento: str = Query(None),
    bairro: str = Query(None),
):
    """Lista feedbacks com filtros opcionais."""
    sb = get_supabase()
    query = sb.table("feedbacks").select(
        "id, protocolo, telefone, nome, categoria, sentimento, urgencia, "
        "mensagem, resumo, bairro, status, departamento, created_at"
    ).order("created_at", desc=True)

    if status:
        query = query.eq("status", status)
    if categoria:
        query = query.eq("categoria", categoria)
    if sentimento:
        query = query.eq("sentimento", sentimento)
    if bairro:
        query = query.eq("bairro", bairro)

    result = query.limit(100).execute()
    return result.data or []


@router.patch("/{feedback_id}/status")
async def atualizar_status_feedback(feedback_id: str, body: dict):
    """Atualiza o status de um feedback (ex: novo → em_analise)."""
    sb = get_supabase()
    update_data = {}
    if "status" in body:
        update_data["status"] = body["status"]
    if "operador" in body:
        update_data["operador"] = body["operador"]
    if "departamento" in body:
        update_data["departamento"] = body["departamento"]
    if "notas" in body:
        update_data["notas"] = body["notas"]
    if "resposta_prefeitura" in body:
        update_data["resposta_prefeitura"] = body["resposta_prefeitura"]

    result = sb.table("feedbacks").update(update_data).eq("id", feedback_id).execute()
    return result.data[0] if result.data else {}


@router.get("/{feedback_id}/mensagens")
async def listar_mensagens_feedback(feedback_id: str):
    """Retorna todas as mensagens do chat do feedback (cidadão + bot + operador)."""
    sb = get_supabase()
    result = sb.table("feedbacks_mensagens").select("*").eq(
        "feedback_id", feedback_id
    ).order("created_at", desc=False).execute()
    return result.data or []


@router.post("/{feedback_id}/handoff")
async def feedback_handoff_toggle(feedback_id: str, body: dict):
    """Ativa/desativa handoff para um feedback."""
    from datetime import datetime, timezone, timedelta

    sb = get_supabase()
    telefone = body.get("telefone", "")
    ativo = body.get("ativo", False)
    operador = body.get("operador", "admin")

    try:
        if ativo:
            expira_em = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            sb.table("sessoes_conversa").upsert({
                "telefone": telefone,
                "canal": "feedback",
                "etapa": "handoff",
                "registro_id": feedback_id,
                "contexto": {"handoff": True},
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
        logger.error(f"Erro ao atualizar sessão handoff feedback: {exc}")

    if EVOLUTION_API_URL and EVOLUTION_API_KEY:
        numero = telefone.lstrip("+")
        msg = ("Um atendente está entrando na conversa para te ajudar. 😊" if ativo
               else "O atendimento voltou ao nosso assistente virtual.")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}",
                    headers={"apikey": EVOLUTION_API_KEY},
                    json={"number": numero, "text": msg},
                )
        except Exception as exc:
            logger.error(f"Erro ao enviar msg handoff feedback: {exc}")

    return {"status": "ok", "handoff_ativo": ativo}


@router.post("/{feedback_id}/send-message")
async def send_feedback_message(feedback_id: str, body: dict):
    """Envia mensagem do operador para o cidadão e salva no histórico."""
    telefone = body.get("telefone", "")
    mensagem = body.get("mensagem", "")
    operador = body.get("operador", "Atendente")

    if not telefone or not mensagem:
        return {"error": "telefone e mensagem obrigatórios"}

    sb = get_supabase()
    try:
        sb.table("feedbacks_mensagens").insert({
            "feedback_id": feedback_id,
            "telefone": "operador",
            "nome": operador,
            "mensagem": f"[ATENDENTE] {mensagem}",
            "remetente": "operador",
        }).execute()
    except Exception as exc:
        logger.error(f"Erro ao salvar msg operador feedback: {exc}")

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
            logger.error(f"Erro ao enviar msg feedback: {exc}")
            return {"error": str(exc)}

    return {"status": "sent"}


@router.get("/estatisticas")
async def estatisticas_feedbacks():
    """
    Retorna estatisticas dos feedbacks pra cards do dashboard.
    Sentimento positivo vs negativo, top categorias, etc.
    """
    sb = get_supabase()

    # Total por sentimento
    positivos = sb.table("feedbacks").select("id", count="exact").eq("sentimento", "positivo").execute()
    negativos = sb.table("feedbacks").select("id", count="exact").eq("sentimento", "negativo").execute()
    neutros = sb.table("feedbacks").select("id", count="exact").eq("sentimento", "neutro").execute()

    # Total hoje
    from datetime import date
    hoje = date.today().isoformat()
    hoje_result = sb.table("feedbacks").select("id", count="exact").gte("created_at", hoje).execute()

    return {
        "positivos": positivos.count or 0,
        "negativos": negativos.count or 0,
        "neutros": neutros.count or 0,
        "hoje": hoje_result.count or 0,
    }
