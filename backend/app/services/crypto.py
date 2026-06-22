"""
crypto.py — Criptografia AES-256-GCM de dados sensíveis (CPF, chave PIX, dados bancários).

Substitui o antigo placeholder Base64 (que NÃO era criptografia). Mantém compatibilidade
de LEITURA com os formatos legados para não quebrar dados já gravados:

  - "ENCv2:<base64>"   → AES-256-GCM real  (NOVO formato — usado em toda gravação nova)
  - "ENC_<base64>"     → Base64 legado (demo antiga) — ainda é lido
  - "ENC_AES256_*"     → literais de seed de demonstração (não são dados reais) → mascarado
  - texto puro         → legado sem prefixo → devolvido como está

A chave vem de AES_KEY (variável de ambiente) e pode ser qualquer string forte: derivamos
uma chave AES-256 (32 bytes) via SHA-256. ⚠️ A AES_KEY DEVE ser FIXA e ESTÁVEL em produção —
trocar a chave torna ilegíveis todos os dados já gravados no formato ENCv2.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX_V2 = "ENCv2:"        # formato novo (AES-256-GCM)
_PREFIX_SEED = "ENC_AES256_"  # literais de seed de demo
_PREFIX_LEGADO = "ENC_"       # base64 legado
_NONCE_BYTES = 12             # 96 bits — tamanho recomendado para AES-GCM


def _aes_key() -> bytes | None:
    """Deriva uma chave AES-256 (32 bytes) a partir da AES_KEY do ambiente."""
    raw = os.environ.get("AES_KEY", "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()  # sempre 32 bytes


def encrypt(valor: str) -> str:
    """Encripta um valor com AES-256-GCM. Retorna 'ENCv2:<base64(nonce+ciphertext+tag)>'.

    Levanta RuntimeError se a AES_KEY não estiver configurada — proposital:
    é melhor falhar do que gravar dado sensível sem cifra (foi exatamente esse o bug antigo).
    """
    if not valor:
        return ""
    key = _aes_key()
    if key is None:
        raise RuntimeError(
            "AES_KEY não configurada no ambiente — recusando gravar dado sensível sem criptografia."
        )
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, valor.encode("utf-8"), None)
    blob = base64.b64encode(nonce + ciphertext).decode("utf-8")
    return f"{_PREFIX_V2}{blob}"


def decrypt(valor_enc: str | None) -> str:
    """Decripta. Compatível com formato novo (ENCv2), seed de demo e Base64 legado."""
    if not valor_enc:
        return "—"

    # Formato novo: AES-256-GCM
    if valor_enc.startswith(_PREFIX_V2):
        key = _aes_key()
        if key is None:
            return "—"
        try:
            raw = base64.b64decode(valor_enc[len(_PREFIX_V2):].encode("utf-8"))
            nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
            return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception:
            return "—"

    # Literais de seed de demonstração (não são dados reais)
    if valor_enc.startswith(_PREFIX_SEED):
        return f"***{valor_enc[-4:]}"

    # Base64 legado (demo antiga)
    if valor_enc.startswith(_PREFIX_LEGADO):
        try:
            return base64.b64decode(valor_enc[len(_PREFIX_LEGADO):].encode("utf-8")).decode("utf-8")
        except Exception:
            return valor_enc

    # Texto puro legado
    return valor_enc


def mask_cpf(cpf_enc: str | None) -> str:
    """Decripta e mascara um CPF para exibição segura: 12345678900 → ***.***.789-00.

    Para valores que não decifram num CPF de 11 dígitos (seed/legado), devolve máscara genérica.
    """
    if not cpf_enc:
        return "—"
    valor = decrypt(cpf_enc)
    digitos = "".join(c for c in valor if c.isdigit())
    if len(digitos) == 11:
        return f"***.***.{digitos[6:9]}-{digitos[9:]}"
    return "***.***.***-**"
