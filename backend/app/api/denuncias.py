"""
denuncias.py — Endpoints REST para a aba Denúncias
"""
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

router = APIRouter()


@router.get("/")
async def listar_denuncias(
    status: str = Query(None),
    categoria: str = Query(None),
    bairro: str = Query(None),
):
    sb = get_supabase()
    query = sb.table("denuncias").select(
        "id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, "
        "latitude, longitude, cidadania_ativa, valor_recompensa, status, midia_urls, "
        "foto_origem, foto_flag, foto_flag_motivo, "
        "encaminhada_para, encaminhada_em, created_at"
        # Nota: cpf_encrypted e dados_bancarios_encrypted NÃO são retornados aqui!
    ).order("created_at", desc=True)

    if status:
        query = query.eq("status", status)
    if categoria:
        query = query.eq("categoria", categoria)
    if bairro:
        query = query.eq("bairro", bairro)

    result = query.limit(100).execute()
    return result.data or []


@router.patch("/{denuncia_id}/status")
async def atualizar_status(denuncia_id: str, body: dict):
    """Atualiza o status de uma denúncia (ex: novo → em_analise)."""
    from datetime import datetime, timezone

    sb = get_supabase()
    update_data = {
        "status": body.get("status"),
        "operador": body.get("operador"),
        "notas": body.get("notas"),
    }

    if body.get("encaminhada_para"):
        update_data["encaminhada_para"] = body["encaminhada_para"]
        update_data["encaminhada_em"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("denuncias").update(update_data).eq("id", denuncia_id).execute()
    return result.data[0] if result.data else {}
