"""
dashboard.py — Endpoints REST para o Dashboard
Esses endpoints alimentam os KPI cards e feeds da central de operações
"""
from fastapi import APIRouter
from app.services.supabase_client import get_supabase

router = APIRouter()


@router.get("/kpis")
async def get_kpis():
    """
    Retorna os 4 KPIs principais do dashboard:
    - SOS alertas ativos
    - Denúncias hoje
    - Ocorrências abertas
    - Tempo médio de resposta (simulado no MVP)
    """
    sb = get_supabase()

    # SOS alertas ativos
    sos_result = sb.table("sos_alertas").select("id", count="exact").eq("status", "active").execute()
    sos_ativos = sos_result.count or 0

    # Denúncias hoje
    from datetime import date
    hoje = date.today().isoformat()
    den_result = sb.table("denuncias").select("id", count="exact").gte("created_at", hoje).execute()
    denuncias_hoje = den_result.count or 0

    # Ocorrências abertas
    ocorr_result = sb.table("ocorrencias").select("id", count="exact").neq("status", "resolvido").execute()
    ocorrencias_abertas = ocorr_result.count or 0

    return {
        "sos_ativos": sos_ativos,
        "denuncias_hoje": denuncias_hoje,
        "ocorrencias_abertas": ocorrencias_abertas,
        "tempo_medio_resposta": "12min",  # TODO: calcular real
    }


@router.get("/feed")
async def get_feed():
    """
    Retorna os últimos 20 eventos para o feed ao vivo do dashboard.
    Mistura denúncias, ocorrências e alertas SOS ordenados por data.
    """
    sb = get_supabase()

    # Últimas denúncias
    den = sb.table("denuncias").select("id, protocolo, categoria, bairro, status, created_at").order("created_at", desc=True).limit(7).execute()

    # Últimas ocorrências
    ocorr = sb.table("ocorrencias").select("id, protocolo, categoria, titulo, bairro, severidade, status, created_at").order("created_at", desc=True).limit(7).execute()

    # Últimos alertas SOS
    sos = sb.table("sos_alertas").select("id, telefone, status, created_at").order("created_at", desc=True).limit(6).execute()

    # Combinar e ordenar
    feed = []

    for d in (den.data or []):
        feed.append({**d, "tipo": "denuncia"})

    for o in (ocorr.data or []):
        feed.append({**o, "tipo": "ocorrencia"})

    for s in (sos.data or []):
        feed.append({**s, "tipo": "sos", "categoria": "sos_mulher"})

    feed.sort(key=lambda x: x["created_at"], reverse=True)
    return feed[:20]
