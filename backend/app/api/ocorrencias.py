"""
ocorrencias.py — Endpoints REST para a aba Ocorrências
"""
import logging
import os

import httpx
from fastapi import APIRouter, Query
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.ocorrencias")

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

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


@router.patch("/{ocorrencia_id}/status")
async def atualizar_status_ocorrencia(ocorrencia_id: str, body: dict):
    """Atualiza o status de uma ocorrência (usado pelos botões do dashboard)."""
    from datetime import datetime, timezone

    sb = get_supabase()
    update_data = {}

    if "status" in body:
        update_data["status"] = body["status"]
    if "operador" in body:
        update_data["operador"] = body["operador"]
    if "notas" in body:
        update_data["notas"] = body["notas"]
    if "equipe" in body:
        update_data["equipe"] = body["equipe"]
    if "equipe_designada" in body:
        update_data["equipe_designada"] = body["equipe_designada"]

    if body.get("status") == "encaminhada":
        update_data["encaminhada_em"] = datetime.now(timezone.utc).isoformat()

    if body.get("status") == "resolvido":
        update_data["resolvida_em"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("ocorrencias").update(update_data).eq("id", ocorrencia_id).execute()
    return result.data[0] if result.data else {}


@router.post("/{ocorrencia_id}/handoff")
async def handoff_toggle(ocorrencia_id: str, body: dict):
    """Ativa/desativa handoff (atendimento humano) para um cidadão."""
    sb = get_supabase()
    telefone = body.get("telefone", "")
    ativo = body.get("ativo", False)
    operador = body.get("operador", "admin")

    # Atualizar sessao_conversa se existir
    try:
        sb.table("sessoes_conversa").update({
            "handoff_ativo": ativo,
            "handoff_operador": operador if ativo else "",
        }).eq("telefone", telefone).execute()
    except Exception:
        pass  # Sessão pode ter expirado

    # Enviar mensagem ao cidadão via Evolution API
    if EVOLUTION_API_URL and EVOLUTION_API_KEY:
        numero = telefone.lstrip("+")
        if ativo:
            msg = "Um atendente humano está entrando na conversa para te ajudar."
        else:
            msg = "O atendimento voltou ao nosso assistente virtual. Se precisar de ajuda humana novamente, é só pedir."
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}",
                    headers={"apikey": EVOLUTION_API_KEY},
                    json={"number": numero, "text": msg},
                )
        except Exception as exc:
            logger.error(f"Erro ao enviar msg handoff: {exc}")

    return {"status": "ok", "handoff_ativo": ativo}


@router.post("/{ocorrencia_id}/send-message")
async def send_human_message(ocorrencia_id: str, body: dict):
    """Envia mensagem do operador humano para o cidadão via WhatsApp."""
    telefone = body.get("telefone", "")
    mensagem = body.get("mensagem", "")
    operador = body.get("operador", "Atendente")

    if not telefone or not mensagem:
        return {"error": "telefone e mensagem obrigatórios"}

    # Salvar no relato
    sb = get_supabase()
    try:
        sb.table("ocorrencias_relatos").insert({
            "ocorrencia_id": ocorrencia_id,
            "telefone": "operador",
            "nome": operador,
            "mensagem": f"[ATENDENTE] {mensagem}",
        }).execute()
    except Exception as exc:
        logger.error(f"Erro ao salvar msg do operador: {exc}")

    # Enviar via Evolution API
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
            logger.error(f"Erro ao enviar msg operador: {exc}")
            return {"error": str(exc)}

    return {"status": "sent"}
