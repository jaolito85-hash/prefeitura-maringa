"""
ocorrencias.py — Endpoints REST para a aba Ocorrências
"""
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

router = APIRouter()


@router.get("/")
async def listar_ocorrencias(
    status: str = Query(None, description="Filtrar por status"),
    categoria: str = Query(None, description="Filtrar por categoria"),
):
    sb = get_supabase()
    query = sb.table("ocorrencias").select("*").order("created_at", desc=True)

    if status:
        query = query.eq("status", status)
    if categoria:
        query = query.eq("categoria", categoria)

    result = query.limit(100).execute()
    return result.data or []


@router.get("/mapa")
async def ocorrencias_para_mapa():
    """
    Retorna apenas os campos necessários para os marcadores do mapa.
    Mais leve — carrega rápido.
    """
    sb = get_supabase()
    result = sb.table("ocorrencias").select(
        "id, protocolo, categoria, severidade, status, titulo, bairro, latitude, longitude, total_relatos"
    ).neq("status", "resolvido").execute()
    return result.data or []


@router.get("/{ocorrencia_id}/relatos")
async def relatos_da_ocorrencia(ocorrencia_id: str):
    """Retorna todos os relatos (mensagens de cidadãos) de uma ocorrência."""
    sb = get_supabase()
    result = sb.table("ocorrencias_relatos").select("*").eq(
        "ocorrencia_id", ocorrencia_id
    ).order("created_at", desc=False).execute()
    return result.data or []
