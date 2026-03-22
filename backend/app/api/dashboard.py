"""
dashboard.py — Endpoints REST para o Dashboard
Esses endpoints alimentam os KPI cards e feeds da central de operações
"""
from fastapi import APIRouter
from app.services.supabase_client import get_supabase
from collections import Counter

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

    # Feedbacks hoje
    fb_result = sb.table("feedbacks").select("id", count="exact").gte("created_at", hoje).execute()
    feedbacks_hoje = fb_result.count or 0

    # Recompensas aguardando pagamento
    recomp_result = sb.table("recompensas").select("id", count="exact").eq(
        "status", "aguardando_pagamento").execute()
    recompensas_pendentes = recomp_result.count or 0

    return {
        "sos_ativos": sos_ativos,
        "denuncias_hoje": denuncias_hoje,
        "ocorrencias_abertas": ocorrencias_abertas,
        "feedbacks_hoje": feedbacks_hoje,
        "recompensas_pendentes": recompensas_pendentes,
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

    # Últimos feedbacks
    fb = sb.table("feedbacks").select("id, protocolo, categoria, sentimento, urgencia, resumo, bairro, status, created_at").order("created_at", desc=True).limit(5).execute()

    # Combinar e ordenar
    feed = []

    for d in (den.data or []):
        feed.append({**d, "tipo": "denuncia"})

    for o in (ocorr.data or []):
        feed.append({**o, "tipo": "ocorrencia"})

    for s in (sos.data or []):
        feed.append({**s, "tipo": "sos", "categoria": "sos_mulher"})

    for f in (fb.data or []):
        feed.append({**f, "tipo": "feedback"})

    feed.sort(key=lambda x: x["created_at"], reverse=True)
    return feed[:20]


@router.get("/relatorio")
async def get_relatorio():
    """
    Estatísticas consolidadas para a aba Relatórios.
    Retorna tudo que a aba precisa em uma única chamada.
    """
    sb = get_supabase()

    # ── Denúncias ──
    den_all = sb.table("denuncias").select(
        "id, categoria, bairro, status, created_at"
    ).execute()
    denuncias = den_all.data or []
    total_denuncias = len(denuncias)

    den_por_categoria = dict(Counter(d["categoria"] for d in denuncias if d.get("categoria")))
    den_por_bairro = dict(Counter(d["bairro"] for d in denuncias if d.get("bairro")))
    den_por_status = dict(Counter(d["status"] for d in denuncias if d.get("status")))

    # ── Ocorrências ──
    oc_all = sb.table("ocorrencias").select(
        "id, categoria, bairro, severidade, status, total_relatos, created_at"
    ).execute()
    ocorrencias = oc_all.data or []
    total_ocorrencias = len(ocorrencias)
    total_relatos = sum(o.get("total_relatos", 0) for o in ocorrencias)

    oc_por_categoria = dict(Counter(o["categoria"] for o in ocorrencias if o.get("categoria")))
    oc_por_bairro = dict(Counter(o["bairro"] for o in ocorrencias if o.get("bairro")))
    oc_por_severidade = dict(Counter(o["severidade"] for o in ocorrencias if o.get("severidade")))
    oc_por_status = dict(Counter(o["status"] for o in ocorrencias if o.get("status")))

    # ── SOS Mulher ──
    sos_all = sb.table("sos_alertas").select(
        "id, status, created_at, resolvido_em"
    ).execute()
    sos_alertas = sos_all.data or []
    total_sos = len(sos_alertas)
    sos_resolvidos = sum(1 for s in sos_alertas if s.get("status") == "resolved")
    sos_ativos = sum(1 for s in sos_alertas if s.get("status") in ("active", "attending"))

    # Cadastros SOS
    sos_cad = sb.table("sos_cadastros").select("id", count="exact").execute()
    sos_cadastros = sos_cad.count or 0

    # ── Feedbacks ──
    fb_all = sb.table("feedbacks").select(
        "id, categoria, sentimento, urgencia, bairro, status, created_at"
    ).execute()
    feedbacks = fb_all.data or []
    total_feedbacks = len(feedbacks)

    fb_por_sentimento = dict(Counter(f["sentimento"] for f in feedbacks if f.get("sentimento")))
    fb_por_categoria = dict(Counter(f["categoria"] for f in feedbacks if f.get("categoria")))

    # ── Recompensas ──
    rec_all = sb.table("recompensas").select(
        "id, valor, status, created_at"
    ).execute()
    recompensas = rec_all.data or []
    total_recompensas = len(recompensas)

    rec_por_status = dict(Counter(r["status"] for r in recompensas if r.get("status")))
    valor_pago = sum(r.get("valor", 0) for r in recompensas if r.get("status") == "paga")
    valor_aguardando = sum(r.get("valor", 0) for r in recompensas if r.get("status") == "aguardando_pagamento")
    valor_pendente = sum(r.get("valor", 0) for r in recompensas if r.get("status") == "pendente_validacao")
    valor_rejeitado = sum(r.get("valor", 0) for r in recompensas if r.get("status") == "rejeitada")

    # ── Top 5 bairros (denúncias + ocorrências) ──
    bairros_combined = Counter()
    for d in denuncias:
        if d.get("bairro"):
            bairros_combined[d["bairro"]] += 1
    for o in ocorrencias:
        if o.get("bairro"):
            bairros_combined[o["bairro"]] += 1
    top_bairros = [{"bairro": b, "total": t} for b, t in bairros_combined.most_common(8)]

    return {
        "denuncias": {
            "total": total_denuncias,
            "por_categoria": den_por_categoria,
            "por_bairro": den_por_bairro,
            "por_status": den_por_status,
        },
        "ocorrencias": {
            "total": total_ocorrencias,
            "total_relatos": total_relatos,
            "por_categoria": oc_por_categoria,
            "por_bairro": oc_por_bairro,
            "por_severidade": oc_por_severidade,
            "por_status": oc_por_status,
        },
        "sos": {
            "total": total_sos,
            "resolvidos": sos_resolvidos,
            "ativos": sos_ativos,
            "cadastros": sos_cadastros,
        },
        "feedbacks": {
            "total": total_feedbacks,
            "por_sentimento": fb_por_sentimento,
            "por_categoria": fb_por_categoria,
        },
        "recompensas": {
            "total": total_recompensas,
            "por_status": rec_por_status,
            "valor_pago": valor_pago,
            "valor_aguardando": valor_aguardando,
            "valor_pendente": valor_pendente,
            "valor_rejeitado": valor_rejeitado,
        },
        "top_bairros": top_bairros,
    }
