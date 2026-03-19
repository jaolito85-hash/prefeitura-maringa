"""
protocol.py — Gerador de protocolos MGA-2026-XXXXX
Usa a sequence do PostgreSQL para garantir números únicos
"""
from datetime import date
from app.services.supabase_client import get_supabase


def gerar_protocolo() -> str:
    """
    Gera o próximo protocolo no formato MGA-2026-XXXXX
    Exemplo: MGA-2026-00042
    """
    sb = get_supabase()
    ano = date.today().year

    # Usa a sequence do PostgreSQL — thread-safe, nunca repete
    result = sb.rpc("nextval", {"seq_name": "protocolo_seq"}).execute()
    seq = result.data

    return f"MGA-{ano}-{str(seq).zfill(5)}"
