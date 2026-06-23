"""
auth.py — Autenticação via Supabase Auth + controle de acesso por papel (RBAC).

O frontend faz login com Supabase Auth (e-mail/senha) e envia o access_token no
header `Authorization: Bearer <token>`. Aqui o token é validado no Supabase e o
papel do operador é lido da tabela `operadores`.

Webhooks (/webhook/*) NÃO usam este módulo — continuam autenticados pela apikey
da Evolution. Esta autenticação protege apenas as rotas /api/* (painel).

Papéis: 'operador' | 'financeiro' | 'admin'. 'admin' passa por qualquer require_role.
"""
from __future__ import annotations

import httpx
from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.services.supabase_client import get_supabase


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Valida o Bearer token no Supabase Auth e retorna o operador autenticado.

    Retorna: {id, email, nome, papel}. Levanta 401 (sem/invalid token),
    403 (sem cadastro/papel ou inativo) ou 503 (Supabase indisponível).
    """
    # Interruptor de ativação: enquanto AUTH_ENABLED=false (ex.: antes do frontend
    # de login estar pronto), a API segue aberta para não travar o painel.
    if not settings.auth_enabled:
        return {"id": None, "email": None, "nome": "Sistema", "papel": "admin"}

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária.",
        )
    token = authorization.split(" ", 1)[1].strip()

    # 1) Valida o token diretamente no Supabase Auth (robusto a qualquer algoritmo de assinatura).
    # Usa a SERVICE KEY como apikey (sempre presente/correta no backend) — não depende de
    # SUPABASE_ANON_KEY estar setada certa. O usuário é determinado pelo Bearer token.
    apikey = settings.supabase_service_key or settings.supabase_anon_key
    try:
        resp = httpx.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": apikey},
            timeout=10.0,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível validar a autenticação.",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )
    user = resp.json()
    user_id = user.get("id")
    email = user.get("email")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sem identificação de usuário.",
        )

    # 2) Resolve o papel do operador na tabela `operadores`
    try:
        sb = get_supabase()
        res = (
            sb.table("operadores")
            .select("nome, papel, ativo")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao carregar o perfil do operador.",
        )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operador sem cadastro/permissão no sistema.",
        )
    op = res.data[0]
    if not op.get("ativo", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operador inativo.",
        )

    return {
        "id": user_id,
        "email": email,
        "nome": op.get("nome") or email,
        "papel": op.get("papel") or "operador",
    }


def require_role(*papeis: str):
    """Dependency-factory: exige um dos papéis informados (admin sempre passa)."""
    permitidos = set(papeis) | {"admin"}

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user.get("papel") not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação.",
            )
        return user

    return _dep
