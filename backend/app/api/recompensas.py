"""
recompensas.py — Endpoints REST para a aba Recompensas (Camada Financeira)
==========================================================================
Esses endpoints são EXCLUSIVOS do painel financeiro.
Eles NUNCA expõem conteúdo da denúncia (fotos, vídeos, mensagem).
Eles SÓ mostram: protocolo, status do pagamento, valor, dados do beneficiário.

Segurança:
- CPF e PIX vêm mascarados por padrão (ex: ***.456.***-XX)
- Dados completos só via endpoint específico + registro no audit_log
- Cada acesso a dados sensíveis é logado (LGPD)
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from app.services.supabase_client import get_supabase
from app.services.gerar_termo_pdf import gerar_termo_recompensa

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _mascarar_cpf(cpf_enc: str | None) -> str:
    """
    Mascara o CPF pra exibição segura.
    Na demo, os dados são 'ENC_AES256_demo_cpf_carlos' — mostra como 'ENC...los'
    Em produção com AES real, descriptografa e mascara: 123.456.789-00 → ***.456.***-00
    """
    if not cpf_enc:
        return "—"
    # Demo: mostra parcial do texto encriptado
    if cpf_enc.startswith("ENC_"):
        return f"{cpf_enc[:7]}...{cpf_enc[-4:]}"
    # Produção: seria decrypt + mascara (implementar na Fase 2)
    return "***.***.***-**"


def _registrar_audit(tabela: str, registro_id: str, acao: str,
                     operador: str, request: Request, dados_extra: dict = None):
    """
    Registra no audit_log toda ação sensível.
    Isso é exigência da LGPD e essencial pro Tribunal de Contas.
    """
    try:
        sb = get_supabase()
        sb.table("audit_log").insert({
            "tabela": tabela,
            "registro_id": registro_id,
            "acao": acao,
            "operador": operador,
            "dados_depois": dados_extra,
            "ip": request.client.host if request.client else None,
        }).execute()
    except Exception:
        pass  # Não bloquear o fluxo principal se o audit falhar


# ══════════════════════════════════════════════════════════════
# GET /api/recompensas — Lista recompensas (visão financeira)
# ══════════════════════════════════════════════════════════════

@router.get("/")
async def listar_recompensas(
    status: str = Query(None, description="Filtrar por status: pendente_validacao, validada, aguardando_pagamento, paga, rejeitada"),
):
    """
    Lista todas as recompensas com CPF MASCARADO.
    O financeiro vê o resumo, mas NÃO os dados completos do beneficiário.
    Também NÃO vê conteúdo da denúncia (fotos, mensagem, etc).
    """
    sb = get_supabase()
    query = sb.table("recompensas").select(
        "id, denuncia_id, protocolo, status, valor, tipo_chave_pix, "
        "cpf_encrypted, chave_pix_encrypted, "
        "validado_por, validado_em, pago_por, pago_em, "
        "motivo_rejeicao, numero_empenho, dotacao_orcamentaria, "
        "comprovante_pix_url, termo_url, created_at, updated_at"
    ).order("created_at", desc=True)

    if status:
        query = query.eq("status", status)

    result = query.limit(100).execute()
    recompensas = result.data or []

    # Mascarar dados sensíveis antes de retornar
    for r in recompensas:
        r["cpf_mascarado"] = _mascarar_cpf(r.pop("cpf_encrypted", None))
        r.pop("chave_pix_encrypted", None)  # Remove PIX da listagem

    return recompensas


# ══════════════════════════════════════════════════════════════
# GET /api/recompensas/kpis — KPIs do painel financeiro
# ══════════════════════════════════════════════════════════════

@router.get("/kpis")
async def get_recompensas_kpis():
    """
    KPIs específicos da aba Recompensas:
    - Total pendente de validação
    - Total aguardando pagamento
    - Total já pago (R$)
    - Quantidade de recompensas pagas
    """
    sb = get_supabase()

    # Pendentes de validação (com valor em R$)
    pendentes = sb.table("recompensas").select("id, valor").eq(
        "status", "pendente_validacao").execute()

    # Aguardando pagamento (com valor em R$)
    aguardando = sb.table("recompensas").select("id, valor").eq(
        "status", "aguardando_pagamento").execute()

    # Pagas
    pagas = sb.table("recompensas").select("id, valor").eq(
        "status", "paga").execute()

    # Rejeitadas
    rejeitadas = sb.table("recompensas").select("id", count="exact").eq(
        "status", "rejeitada").execute()

    # Todas
    todas = sb.table("recompensas").select("id", count="exact").execute()

    total_pago = sum(float(r["valor"] or 0) for r in (pagas.data or []))
    total_aguardando = sum(float(r["valor"] or 0) for r in (aguardando.data or []))
    total_pendente = sum(float(r["valor"] or 0) for r in (pendentes.data or []))

    return {
        "pendentes_validacao": len(pendentes.data or []),
        "aguardando_pagamento": len(aguardando.data or []),
        "total_pago": total_pago,
        "total_aguardando": total_aguardando,
        "total_pendente": total_pendente,
        "total_recompensas": todas.count or 0,
        "quantidade_pagas": len(pagas.data or []),
        "rejeitadas": rejeitadas.count or 0,
    }


# ══════════════════════════════════════════════════════════════
# GET /api/recompensas/{id}/dados-pagamento — Dados completos
# ⚠️ AÇÃO SENSÍVEL — Registrada no audit_log
# ══════════════════════════════════════════════════════════════

@router.get("/{recompensa_id}/dados-pagamento")
async def get_dados_pagamento(recompensa_id: str, request: Request, operador: str = Query(...)):
    """
    Retorna CPF e chave PIX COMPLETOS para efetuar o pagamento.

    ⚠️ AÇÃO AUDITADA: Cada chamada é registrada no audit_log com:
    - Quem acessou (operador)
    - Quando acessou
    - IP de origem

    Isso garante conformidade com LGPD e rastreabilidade pro Tribunal de Contas.
    """
    sb = get_supabase()
    result = sb.table("recompensas").select(
        "id, protocolo, status, valor, cpf_encrypted, chave_pix_encrypted, tipo_chave_pix"
    ).eq("id", recompensa_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Recompensa não encontrada")

    recompensa = result.data[0]

    # Permite ver dados em qualquer status exceto rejeitada
    # (o operador pode precisar conferir dados antes de validar)
    if recompensa["status"] == "rejeitada":
        raise HTTPException(
            status_code=403,
            detail="Dados de pagamento não disponíveis para recompensas rejeitadas."
        )

    # ⚠️ REGISTRAR NO AUDIT LOG — isso é obrigatório!
    _registrar_audit(
        tabela="recompensas",
        registro_id=recompensa_id,
        acao="view_sensitive",
        operador=operador,
        request=request,
        dados_extra={"campos_acessados": ["cpf_encrypted", "chave_pix_encrypted"]},
    )

    # Decriptar dados para o operador financeiro
    import base64
    def _decrypt(val):
        if not val: return "—"
        if val.startswith("ENC_") and not val.startswith("ENC_AES256_"):
            try: return base64.b64decode(val[4:].encode('utf-8')).decode('utf-8')
            except: pass
        if val.startswith("ENC_AES256_"): return f"***{val[-4:]}"
        return val

    return {
        "id": recompensa["id"],
        "protocolo": recompensa["protocolo"],
        "valor": recompensa["valor"],
        "cpf": _decrypt(recompensa["cpf_encrypted"]),
        "chave_pix": _decrypt(recompensa["chave_pix_encrypted"]),
        "tipo_chave_pix": recompensa["tipo_chave_pix"],
        "aviso": "⚠️ Acesso registrado no log de auditoria (LGPD)",
    }


# ══════════════════════════════════════════════════════════════
# PATCH /api/recompensas/{id}/validar — Operacional valida
# ══════════════════════════════════════════════════════════════

@router.patch("/{recompensa_id}/validar")
async def validar_recompensa(recompensa_id: str, body: dict, request: Request):
    """
    O operacional marca a denúncia como procedente.
    Automaticamente atualiza o status da recompensa pra 'aguardando_pagamento'.

    Body esperado:
    {
        "procedente": true/false,
        "operador": "Op. Silva",
        "motivo_rejeicao": "..." (só se procedente=false)
    }
    """
    sb = get_supabase()
    procedente = body.get("procedente", False)
    operador = body.get("operador", "sistema")

    # Buscar recompensa atual
    result = sb.table("recompensas").select("id, status, denuncia_id").eq(
        "id", recompensa_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Recompensa não encontrada")

    recompensa = result.data[0]

    if recompensa["status"] != "pendente_validacao":
        raise HTTPException(
            status_code=400,
            detail=f"Só é possível validar recompensas com status 'pendente_validacao'. Status atual: {recompensa['status']}"
        )

    agora = datetime.now(timezone.utc).isoformat()

    if procedente:
        # Atualizar recompensa → aguardando_pagamento
        sb.table("recompensas").update({
            "status": "aguardando_pagamento",
            "validado_por": operador,
            "validado_em": agora,
            "updated_at": agora,
        }).eq("id", recompensa_id).execute()

        # Atualizar denúncia → procedente
        sb.table("denuncias").update({
            "status": "procedente",
            "operador": operador,
            "updated_at": agora,
        }).eq("id", recompensa["denuncia_id"]).execute()

        _registrar_audit("recompensas", recompensa_id, "update",
                         operador, request, {"status": "aguardando_pagamento"})

        return {"status": "aguardando_pagamento", "mensagem": "Denúncia validada! Recompensa liberada para pagamento."}

    else:
        # Rejeitar
        motivo = body.get("motivo_rejeicao", "Sem motivo informado")
        sb.table("recompensas").update({
            "status": "rejeitada",
            "validado_por": operador,
            "validado_em": agora,
            "motivo_rejeicao": motivo,
            "updated_at": agora,
        }).eq("id", recompensa_id).execute()

        # Atualizar denúncia → improcedente
        sb.table("denuncias").update({
            "status": "improcedente",
            "operador": operador,
            "notas": motivo,
            "updated_at": agora,
        }).eq("id", recompensa["denuncia_id"]).execute()

        _registrar_audit("recompensas", recompensa_id, "update",
                         operador, request, {"status": "rejeitada", "motivo": motivo})

        return {"status": "rejeitada", "mensagem": f"Recompensa rejeitada. Motivo: {motivo}"}


# ══════════════════════════════════════════════════════════════
# PATCH /api/recompensas/{id}/pagar — Financeiro registra pagamento
# ══════════════════════════════════════════════════════════════

@router.patch("/{recompensa_id}/pagar")
async def registrar_pagamento(recompensa_id: str, body: dict, request: Request):
    """
    O financeiro registra que o PIX foi feito.

    Body esperado:
    {
        "operador": "Fin. Santos",
        "comprovante_pix_url": "https://...",
        "numero_empenho": "EMP-2026-00XXX",
        "dotacao_orcamentaria": "DOT-15.452.0045.2.048"
    }
    """
    sb = get_supabase()
    operador = body.get("operador", "sistema")

    # Buscar recompensa
    result = sb.table("recompensas").select("id, status, denuncia_id, protocolo, valor").eq(
        "id", recompensa_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Recompensa não encontrada")

    recompensa = result.data[0]

    if recompensa["status"] != "aguardando_pagamento":
        raise HTTPException(
            status_code=400,
            detail=f"Só é possível pagar recompensas com status 'aguardando_pagamento'. Status atual: {recompensa['status']}"
        )

    agora = datetime.now(timezone.utc).isoformat()

    # Atualizar recompensa → paga
    update_data = {
        "status": "paga",
        "pago_por": operador,
        "pago_em": agora,
        "updated_at": agora,
    }

    # Campos opcionais de prestação de contas
    if body.get("comprovante_pix_url"):
        update_data["comprovante_pix_url"] = body["comprovante_pix_url"]
    if body.get("numero_empenho"):
        update_data["numero_empenho"] = body["numero_empenho"]
    if body.get("dotacao_orcamentaria"):
        update_data["dotacao_orcamentaria"] = body["dotacao_orcamentaria"]

    sb.table("recompensas").update(update_data).eq("id", recompensa_id).execute()

    # Atualizar denúncia → recompensa_paga
    sb.table("denuncias").update({
        "status": "recompensa_paga",
        "valor_recompensa": recompensa["valor"],
        "updated_at": agora,
    }).eq("id", recompensa["denuncia_id"]).execute()

    # Audit log
    _registrar_audit("recompensas", recompensa_id, "update",
                     operador, request, {
                         "status": "paga",
                         "valor": str(recompensa["valor"]),
                         "numero_empenho": body.get("numero_empenho"),
                     })

    return {
        "status": "paga",
        "mensagem": f"Pagamento de R$ {recompensa['valor']} registrado com sucesso!",
        "protocolo": recompensa["protocolo"],
    }


# ══════════════════════════════════════════════════════════════
# GET /api/recompensas/{id}/termo — Gerar PDF do Termo de Recompensa
# ══════════════════════════════════════════════════════════════

@router.get("/{recompensa_id}/termo")
async def gerar_termo_pdf(recompensa_id: str, request: Request, operador: str = Query("sistema")):
    """
    Gera e retorna o PDF do Termo de Recompensa.
    Usado pra prestação de contas e auditoria.
    O PDF contém dados mascarados — versão segura pra circulação.
    """
    sb = get_supabase()
    result = sb.table("recompensas").select("*").eq("id", recompensa_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Recompensa não encontrada")

    recompensa = result.data[0]

    # Buscar categoria da denúncia vinculada
    den_result = sb.table("denuncias").select("categoria").eq(
        "id", recompensa["denuncia_id"]).execute()
    categoria = den_result.data[0]["categoria"] if den_result.data else "—"

    # Montar dados pro PDF
    dados_pdf = {
        "protocolo": recompensa["protocolo"],
        "valor": float(recompensa["valor"]) if recompensa.get("valor") else 0,
        "categoria": categoria,
        "cpf_mascarado": _mascarar_cpf(recompensa.get("cpf_encrypted")),
        "tipo_chave_pix": recompensa.get("tipo_chave_pix", "—"),
        "status": recompensa.get("status", "—"),
        "validado_por": recompensa.get("validado_por"),
        "validado_em": recompensa.get("validado_em"),
        "pago_por": recompensa.get("pago_por"),
        "pago_em": recompensa.get("pago_em"),
        "numero_empenho": recompensa.get("numero_empenho"),
        "dotacao_orcamentaria": recompensa.get("dotacao_orcamentaria"),
        "created_at": recompensa.get("created_at"),
    }

    # Gerar PDF
    pdf_bytes = gerar_termo_recompensa(dados_pdf)

    # Registrar no audit log
    _registrar_audit("recompensas", recompensa_id, "gerar_termo",
                     operador, request, {"protocolo": recompensa["protocolo"]})

    filename = f"Termo_Recompensa_{recompensa['protocolo']}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ══════════════════════════════════════════════════════════════
# GET /api/recompensas/config — Valores por categoria
# ══════════════════════════════════════════════════════════════

@router.get("/config")
async def listar_config_recompensas():
    """
    Retorna os valores de recompensa configurados por categoria.
    A prefeitura pode ajustar esses valores pelo painel.
    """
    sb = get_supabase()
    result = sb.table("recompensas_config").select("*").order("valor_padrao", desc=True).execute()
    return result.data or []


# ══════════════════════════════════════════════════════════════
# PATCH /api/recompensas/config/{categoria} — Atualizar valor
# ══════════════════════════════════════════════════════════════

@router.patch("/config/{categoria}")
async def atualizar_config(categoria: str, body: dict, request: Request):
    """
    Atualiza o valor da recompensa para uma categoria.
    Ex: mudar tráfico de R$300 pra R$500.

    Body: { "valor_padrao": 500.00, "operador": "Secretário" }
    """
    sb = get_supabase()
    operador = body.get("operador", "sistema")

    update_data = {}
    if "valor_padrao" in body:
        update_data["valor_padrao"] = body["valor_padrao"]
    if "ativo" in body:
        update_data["ativo"] = body["ativo"]

    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = sb.table("recompensas_config").update(update_data).eq(
        "categoria", categoria).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Categoria '{categoria}' não encontrada")

    _registrar_audit("recompensas_config", result.data[0]["id"], "update",
                     operador, request, update_data)

    return result.data[0]
