"""
protocolo.py — Endpoint unificado de busca por número de protocolo

Busca em TODAS as tabelas do sistema (denúncias, ocorrências, feedbacks, SOS)
e retorna os dados do registro encontrado + canal de origem.

Usado por:
  - Dashboard (barra de busca do funcionário)
  - Worker WhatsApp (cidadão consulta status enviando o protocolo)
"""
from fastapi import APIRouter, HTTPException
from app.services.supabase_client import get_supabase

router = APIRouter()

# ---- Campos seguros por tabela (NUNCA expor cpf_encrypted / dados_bancarios_encrypted) ----

CAMPOS_DENUNCIA = (
    "id, protocolo, telefone, nome, categoria, mensagem, bairro, endereco, "
    "latitude, longitude, cidadania_ativa, status, midia_urls, created_at"
)

CAMPOS_OCORRENCIA = (
    "id, protocolo, categoria, severidade, status, titulo, descricao, bairro, "
    "endereco, latitude, longitude, total_relatos, created_at"
)

CAMPOS_FEEDBACK = (
    "id, protocolo, telefone, nome, categoria, sentimento, urgencia, "
    "mensagem, resumo, bairro, status, departamento, created_at"
)

CAMPOS_SOS = (
    "id, protocolo, telefone, status, latitude, longitude, created_at, "
    "sos_cadastros(nome, endereco, referencia)"
)

CAMPOS_ARBORIZACAO = (
    "id, protocolo, categoria, severidade, status, resumo, mensagem, bairro, "
    "endereco, latitude, longitude, empresa_atribuida, sla_horas, created_at"
)


def _buscar_em_tabela(sb, tabela: str, campos: str, protocolo: str):
    """Busca um protocolo em uma tabela específica. Retorna o registro ou None."""
    result = sb.table(tabela).select(campos).eq("protocolo", protocolo).limit(1).execute()
    if result.data:
        return result.data[0]
    return None


@router.get("/{numero}")
async def buscar_protocolo(numero: str):
    """
    Busca unificada por número de protocolo (ex: MGA-2026-00001).

    Percorre todas as tabelas na ordem: denúncias → ocorrências → feedbacks → SOS.
    Retorna o registro encontrado com o campo `canal` indicando a origem.

    Segurança: campos sensíveis (CPF, dados bancários) NUNCA são retornados.
    """
    numero = numero.strip().upper()

    # Validação básica do formato
    if not (numero.startswith("MGA-") or numero.startswith("ARB-")):
        raise HTTPException(
            status_code=400,
            detail="Formato de protocolo inválido. Use MGA-2026-XXXXX ou ARB-2026-XXXXX"
        )

    sb = get_supabase()

    # Busca na ordem de prioridade
    tabelas = [
        ("denuncias", CAMPOS_DENUNCIA, "denuncia"),
        ("ocorrencias", CAMPOS_OCORRENCIA, "ocorrencia"),
        ("arborizacao", CAMPOS_ARBORIZACAO, "arborizacao"),
        ("feedbacks", CAMPOS_FEEDBACK, "feedback"),
        ("sos_alertas", CAMPOS_SOS, "sos"),
    ]

    for tabela, campos, canal in tabelas:
        registro = _buscar_em_tabela(sb, tabela, campos, numero)
        if registro:
            return {
                "encontrado": True,
                "canal": canal,
                "protocolo": numero,
                "dados": registro,
            }

    # Não encontrou em nenhuma tabela
    raise HTTPException(
        status_code=404,
        detail=f"Protocolo {numero} não encontrado em nenhum canal."
    )


@router.get("/{numero}/status-cidadao")
async def status_para_cidadao(numero: str):
    """
    Versão simplificada para o cidadão consultar via WhatsApp.

    Retorna apenas: canal, status, categoria, data de criação e uma mensagem amigável.
    NÃO retorna dados sensíveis, endereço, telefone, etc.
    """
    numero = numero.strip().upper()

    if not numero.startswith("MGA-"):
        raise HTTPException(status_code=400, detail="Formato de protocolo inválido.")

    sb = get_supabase()

    # ---- Denúncia ----
    result = sb.table("denuncias").select(
        "protocolo, categoria, status, cidadania_ativa, created_at"
    ).eq("protocolo", numero).limit(1).execute()

    if result.data:
        d = result.data[0]
        return {
            "encontrado": True,
            "canal": "denuncia",
            "protocolo": d["protocolo"],
            "categoria": d.get("categoria", "não classificada"),
            "status": d["status"],
            "cidadania_ativa": d.get("cidadania_ativa", False),
            "created_at": d["created_at"],
            "mensagem": _mensagem_status_denuncia(d),
        }

    # ---- Ocorrência ----
    result = sb.table("ocorrencias").select(
        "protocolo, categoria, status, severidade, total_relatos, created_at"
    ).eq("protocolo", numero).limit(1).execute()

    if result.data:
        o = result.data[0]
        return {
            "encontrado": True,
            "canal": "ocorrencia",
            "protocolo": o["protocolo"],
            "categoria": o.get("categoria", "não classificada"),
            "status": o["status"],
            "severidade": o.get("severidade"),
            "created_at": o["created_at"],
            "mensagem": _mensagem_status_ocorrencia(o),
        }

    # ---- Feedback ----
    result = sb.table("feedbacks").select(
        "protocolo, categoria, status, departamento, created_at"
    ).eq("protocolo", numero).limit(1).execute()

    if result.data:
        f = result.data[0]
        return {
            "encontrado": True,
            "canal": "feedback",
            "protocolo": f["protocolo"],
            "categoria": f.get("categoria"),
            "status": f["status"],
            "created_at": f["created_at"],
            "mensagem": _mensagem_status_feedback(f),
        }

    # ---- SOS ----
    result = sb.table("sos_alertas").select(
        "protocolo, status, created_at"
    ).eq("protocolo", numero).limit(1).execute()

    if result.data:
        s = result.data[0]
        return {
            "encontrado": True,
            "canal": "sos",
            "protocolo": s["protocolo"],
            "status": s["status"],
            "created_at": s["created_at"],
            "mensagem": _mensagem_status_sos(s),
        }

    # Não encontrado
    return {
        "encontrado": False,
        "protocolo": numero,
        "mensagem": f"😕 Não encontramos nenhum registro com o protocolo *{numero}*.\n\nVerifique se digitou corretamente. O formato é MGA-2026-XXXXX.",
    }


# ---- Mensagens amigáveis para o cidadão (WhatsApp) ----

def _mensagem_status_denuncia(d: dict) -> str:
    """Monta mensagem de status para denúncia."""
    status_map = {
        "novo": "📋 *Recebida* — Sua denúncia foi registrada e está aguardando análise pela equipe.",
        "em_analise": "🔍 *Em análise* — Nossa equipe está verificando as informações da sua denúncia.",
        "em_campo": "🚔 *Em campo* — Agentes foram enviados para verificar a situação no local.",
        "resolvido": "✅ *Resolvida* — Sua denúncia foi tratada. Obrigado por contribuir!",
        "arquivado": "📁 *Arquivada* — Esta denúncia foi arquivada após análise.",
    }

    status_texto = status_map.get(d["status"], f"Status atual: {d['status']}")

    msg = f"📋 *Denúncia {d['protocolo']}*\n"
    msg += f"Categoria: {d.get('categoria', 'não classificada').replace('_', ' ').title()}\n\n"
    msg += f"{status_texto}\n"

    if d.get("cidadania_ativa"):
        msg += "\n💰 *Cidadão Ativo:* Sua denúncia está vinculada ao programa de recompensa."

        # Adicionar status da recompensa se for cidadania ativa
        # (o worker vai complementar com dados da tabela recompensas)

    return msg


def _mensagem_status_ocorrencia(o: dict) -> str:
    """Monta mensagem de status para ocorrência."""
    status_map = {
        "ativo": "🟡 *Ativa* — Ocorrência registrada e em monitoramento.",
        "em_atendimento": "🚔 *Em atendimento* — Equipe no local verificando.",
        "resolvido": "✅ *Resolvida* — Situação normalizada.",
    }

    status_texto = status_map.get(o["status"], f"Status atual: {o['status']}")

    msg = f"🚨 *Ocorrência {o['protocolo']}*\n"
    msg += f"Categoria: {o.get('categoria', '').replace('_', ' ').title()}\n"
    msg += f"Severidade: {'⚠️' * min(o.get('severidade', 1), 5)}\n"
    msg += f"Relatos: {o.get('total_relatos', 1)} pessoa(s) reportaram\n\n"
    msg += f"{status_texto}"

    return msg


def _mensagem_status_feedback(f: dict) -> str:
    """Monta mensagem de status para feedback."""
    status_map = {
        "novo": "📬 *Recebido* — Seu feedback foi registrado.",
        "lido": "👁️ *Lido* — Sua mensagem foi visualizada pela equipe.",
        "respondido": "💬 *Respondido* — Sua mensagem foi encaminhada ao departamento responsável.",
        "encerrado": "✅ *Encerrado* — Feedback processado. Obrigado!",
    }

    status_texto = status_map.get(f["status"], f"Status atual: {f['status']}")

    msg = f"💬 *Feedback {f['protocolo']}*\n"
    if f.get("departamento"):
        msg += f"Departamento: {f['departamento']}\n"
    msg += f"\n{status_texto}"

    return msg


def _mensagem_status_sos(s: dict) -> str:
    """Monta mensagem de status para SOS."""
    status_map = {
        "active": "🔴 *ATIVO* — Seu alerta está ativo e a equipe foi acionada.",
        "accepted": "🚔 *Aceito* — Uma viatura foi designada para atendimento.",
        "resolved": "✅ *Atendido* — Ocorrência finalizada.",
    }

    status_texto = status_map.get(s["status"], f"Status atual: {s['status']}")

    msg = f"🆘 *Alerta SOS {s['protocolo']}*\n\n"
    msg += f"{status_texto}\n\n"
    msg += "Se você está em perigo, ligue 190 (Polícia Militar)."

    return msg
