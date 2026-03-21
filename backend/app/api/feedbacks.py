"""
feedbacks.py — Endpoints REST para a aba Feedbacks do Dashboard
"""
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

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
