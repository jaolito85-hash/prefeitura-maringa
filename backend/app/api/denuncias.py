"""
denuncias.py — Endpoints REST para a aba Denúncias
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.denuncias")

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


@router.post("/{denuncia_id}/validar-recompensa")
async def validar_recompensa(denuncia_id: str, body: dict):
    """Valida denúncia como procedente e CRIA recompensa na aba Recompensas.
    Só deve ser chamado quando o operador confirma que a denúncia é legítima."""
    sb = get_supabase()

    # Buscar denúncia com dados sensíveis
    den = sb.table("denuncias").select(
        "id, protocolo, categoria, valor_recompensa, cidadania_ativa, "
        "cpf_encrypted, dados_bancarios_encrypted, status"
    ).eq("id", denuncia_id).single().execute()

    if not den.data:
        return {"error": "Denúncia não encontrada"}

    d = den.data
    if not d.get("cidadania_ativa"):
        return {"error": "Denúncia não é elegível ao Programa Cidadão Ativo"}

    if not d.get("cpf_encrypted") or not d.get("dados_bancarios_encrypted"):
        return {"error": "Cidadão não cadastrou CPF/PIX"}

    # Verificar se já existe recompensa para essa denúncia
    existing = sb.table("recompensas").select("id").eq("denuncia_id", denuncia_id).execute()
    if existing.data:
        return {"error": "Recompensa já criada para esta denúncia", "recompensa_id": existing.data[0]["id"]}

    # Criar recompensa
    valor = d.get("valor_recompensa", 0)
    try:
        res = sb.table("recompensas").insert({
            "denuncia_id": denuncia_id,
            "protocolo": d["protocolo"],
            "status": "pendente_validacao",
            "valor": valor,
            "cpf_encrypted": d["cpf_encrypted"],
            "chave_pix_encrypted": d["dados_bancarios_encrypted"],
            "tipo_chave_pix": "cpf",
        }).execute()

        # Atualizar status da denúncia para procedente
        sb.table("denuncias").update({
            "status": "procedente",
        }).eq("id", denuncia_id).execute()

        logger.info(f"Recompensa criada via validação: {d['protocolo']} (R$ {valor})")
        return {"ok": True, "protocolo": d["protocolo"], "valor": valor}
    except Exception as exc:
        logger.error(f"Erro criar recompensa: {exc}")
        return {"error": str(exc)}
