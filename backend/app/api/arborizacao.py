"""
arborizacao.py — Endpoints REST para a aba Arborização Urbana
Pipeline agentic: cidadão → IA → empresa → fiscal → feedback
"""
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.arborizacao")

EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
WA_INSTANCE_NAME = os.environ.get("WA_INSTANCE_NAME", "maringa-demo")

router = APIRouter()


# ── Schemas ──

class StatusUpdate(BaseModel):
    status: str
    operador: str | None = None
    notas: str | None = None

class AtribuirEmpresa(BaseModel):
    empresa_chave: str
    operador: str | None = None

class Fiscalizar(BaseModel):
    aprovado: bool
    obs: str | None = None
    operador: str | None = None


# ── Endpoints ──

@router.get("/")
async def listar_arborizacao(
    status: str = Query(None, description="Filtrar por status"),
    categoria: str = Query(None, description="Filtrar por categoria"),
    severidade: str = Query(None, description="Filtrar por severidade"),
    bairro: str = Query(None, description="Filtrar por bairro"),
):
    sb = get_supabase()
    query = sb.table("arborizacao").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if categoria:
        query = query.eq("categoria", categoria)
    if severidade:
        query = query.eq("severidade", severidade)
    if bairro:
        query = query.eq("bairro", bairro)
    result = query.limit(200).execute()
    return result.data or []


@router.get("/mapa")
async def arborizacao_para_mapa():
    """Campos leves para marcadores do mapa."""
    sb = get_supabase()
    result = sb.table("arborizacao").select(
        "id, protocolo, categoria, severidade, status, resumo, bairro, latitude, longitude, endereco"
    ).not_.in_("status", ["fiscalizado"]).execute()
    return result.data or []


@router.get("/kpis")
async def arborizacao_kpis():
    """KPIs agregados para o dashboard."""
    sb = get_supabase()
    todos = sb.table("arborizacao").select("id, status, severidade, sla_estourado, empresa_atribuida", count="exact").execute()
    data = todos.data or []
    total = len(data)
    emerg = sum(1 for d in data if d["severidade"] == "emergencia" and d["status"] not in ("concluido", "fiscalizado"))
    done = sum(1 for d in data if d["status"] in ("concluido", "fiscalizado"))
    sla_estourados = sum(1 for d in data if d.get("sla_estourado"))
    taxa = round(done / total * 100) if total else 0
    return {
        "total": total,
        "emerg": emerg,
        "done": done,
        "sla_estourados": sla_estourados,
        "taxa": taxa,
        "tempo_medio": "1d 14h",  # TODO: calcular de verdade
    }


@router.get("/config")
async def arborizacao_config():
    """Retorna config de SLA e empresas."""
    sb = get_supabase()
    result = sb.table("arborizacao_config").select("*").eq("ativo", True).execute()
    config = {"sla": {}, "empresas": []}
    for item in (result.data or []):
        if item["tipo"] == "sla":
            config["sla"][item["chave"]] = item["valor"]
        elif item["tipo"] == "empresa":
            config["empresas"].append({"chave": item["chave"], **item["valor"]})
    return config


@router.get("/{arb_id}")
async def detalhe_arborizacao(arb_id: str):
    """Detalhe completo de uma solicitação."""
    sb = get_supabase()
    result = sb.table("arborizacao").select("*").eq("id", arb_id).single().execute()
    return result.data


@router.patch("/{arb_id}/status")
async def atualizar_status(arb_id: str, body: StatusUpdate):
    """Atualiza status de uma solicitação."""
    sb = get_supabase()
    update = {"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if body.operador:
        update["operador"] = body.operador
    if body.notas:
        update["notas"] = body.notas
    # Timestamps automáticos
    if body.status == "triado":
        update["triado_em"] = datetime.now(timezone.utc).isoformat()
    elif body.status == "concluido":
        update["concluido_em"] = datetime.now(timezone.utc).isoformat()
    elif body.status == "fiscalizado":
        update["fiscalizado_em"] = datetime.now(timezone.utc).isoformat()
    sb.table("arborizacao").update(update).eq("id", arb_id).execute()
    return {"ok": True}


@router.post("/{arb_id}/atribuir")
async def atribuir_empresa(arb_id: str, body: AtribuirEmpresa):
    """Atribui solicitação a uma empresa e despacha OS via WhatsApp."""
    sb = get_supabase()
    # Buscar empresa na config
    cfg = sb.table("arborizacao_config").select("valor").eq("chave", body.empresa_chave).single().execute()
    if not cfg.data:
        return {"error": "Empresa não encontrada"}
    empresa = cfg.data["valor"]

    # Buscar SLA da severidade
    arb = sb.table("arborizacao").select("severidade").eq("id", arb_id).single().execute()
    severidade = (arb.data or {}).get("severidade", "rotina")
    sla_cfg = sb.table("arborizacao_config").select("valor").eq("chave", severidade).single().execute()
    sla_horas = (sla_cfg.data or {}).get("valor", {}).get("horas", 168)
    from datetime import timedelta
    sla_vencimento = (datetime.now(timezone.utc) + timedelta(hours=sla_horas)).isoformat()

    # Atualizar registro
    sb.table("arborizacao").update({
        "status": "atribuido",
        "empresa_atribuida": empresa["nome"],
        "empresa_telefone": empresa["telefone"],
        "atribuida_em": datetime.now(timezone.utc).isoformat(),
        "sla_horas": sla_horas,
        "sla_vencimento": sla_vencimento,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", arb_id).execute()

    # Despachar OS via worker (importar função do worker seria circular,
    # então fazemos inline aqui usando a mesma lógica)
    try:
        arb_full = sb.table("arborizacao").select("*").eq("id", arb_id).single().execute().data
        if arb_full and arb_full.get("empresa_telefone"):
            import httpx as _httpx
            cat = arb_full["categoria"].replace("_", " ").title()
            sev = arb_full["severidade"].upper()
            gmaps = f"https://www.google.com/maps?q={arb_full.get('latitude',0)},{arb_full.get('longitude',0)}"
            os_msg = (
                f"📋 *ORDEM DE SERVIÇO — ARBORIZAÇÃO MARINGÁ*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌳 Tipo: *{cat}*\n"
                f"🚨 Severidade: *{sev}*\n"
                f"📋 Protocolo: {arb_full['protocolo']}\n"
                f"📍 {arb_full.get('endereco', '—')}\n"
                f"🏘️ {arb_full.get('bairro', '—')}\n"
                f"🗺️ Maps: {gmaps}\n"
                f"⏱️ SLA: {sla_horas}h\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Responda:\n1️⃣ Aceitar\n2️⃣ A caminho\n3️⃣ Concluído + foto\n0️⃣ Recusar"
            )
            numero = arb_full["empresa_telefone"].lstrip("+")
            url = f"{EVOLUTION_API_URL}/message/sendText/{WA_INSTANCE_NAME}"
            _httpx.post(url, json={"number": numero, "text": os_msg},
                       headers={"Content-Type": "application/json", "apikey": EVOLUTION_API_KEY}, timeout=10.0)

            # Criar sessão para empresa
            from datetime import timedelta as _td
            expira = (datetime.now(timezone.utc) + _td(hours=24)).isoformat()
            sb.table("sessoes_conversa").upsert({
                "telefone": arb_full["empresa_telefone"],
                "canal": "arborizacao_empresa",
                "etapa": "aguardando_aceite",
                "registro_id": arb_id,
                "contexto": {"protocolo": arb_full["protocolo"], "arb_id": arb_id, "empresa_nome": empresa["nome"]},
                "expira_em": expira,
                "handoff_ativo": False, "handoff_operador": "",
            }, on_conflict="telefone").execute()
            logger.info(f"OS despachada via API: {arb_full['protocolo']} → {empresa['nome']}")
    except Exception as exc:
        logger.error(f"Erro despacho empresa via API: {exc}")

    return {"ok": True, "empresa": empresa["nome"]}


@router.post("/{arb_id}/fiscalizar")
async def fiscalizar(arb_id: str, body: Fiscalizar):
    """Fiscal aprova ou rejeita serviço."""
    sb = get_supabase()
    update = {
        "fiscal_aprovado": body.aprovado,
        "fiscal_obs": body.obs or ("Aprovado pelo fiscal" if body.aprovado else "Rejeitado pelo fiscal"),
        "fiscal_data": datetime.now(timezone.utc).isoformat(),
        "fiscal_operador": body.operador or "admin",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.aprovado:
        update["status"] = "fiscalizado"
        update["fiscalizado_em"] = datetime.now(timezone.utc).isoformat()
    else:
        # Rejeitar → volta para em_execucao
        update["status"] = "em_execucao"
    sb.table("arborizacao").update(update).eq("id", arb_id).execute()
    return {"ok": True, "aprovado": body.aprovado}
