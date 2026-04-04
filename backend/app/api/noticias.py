"""
noticias.py — Radar de Notícias de Maringá
Busca notícias via Google News RSS (gratuito, sem API key).
Oferece resumo executivo gerado por IA (OpenAI GPT-4o-mini).

Endpoints:
  GET  /api/noticias/          → lista de notícias (busca por termo)
  POST /api/noticias/resumo    → resumo IA das notícias selecionadas
"""
from __future__ import annotations

import html
import re
import logging
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("noticias")
router = APIRouter()

# ─── Cache simples em memória (evita bater no Google a cada request) ───
_cache: dict = {"data": [], "query": "", "fetched_at": None}
CACHE_TTL_SECONDS = 600  # 10 minutos de cache


# ─── Modelos ───────────────────────────────────────────────────────────

class Noticia(BaseModel):
    titulo: str
    link: str
    fonte: str
    data_publicacao: str
    data_iso: Optional[str] = None
    descricao: str = ""


class ResumoRequest(BaseModel):
    noticias: list[str]  # Lista de títulos/textos para resumir


class ResumoResponse(BaseModel):
    resumo: str
    total_noticias: int
    gerado_em: str


# ─── Helpers ───────────────────────────────────────────────────────────

def _limpar_html(texto: str) -> str:
    """Remove tags HTML e decodifica entidades."""
    texto = html.unescape(texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto.strip()


def _extrair_fonte(titulo: str) -> tuple[str, str]:
    """
    Google News coloca a fonte no final do título: 'Notícia tal - Portal X'
    Retorna (titulo_limpo, fonte).
    """
    partes = titulo.rsplit(" - ", 1)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return titulo.strip(), "Fonte desconhecida"


# Fontes institucionais/governamentais que queremos EXCLUIR
# O gestor quer ver o que a IMPRENSA fala, não releases da própria prefeitura
_FONTES_EXCLUIDAS = {
    "prefeitura de maringá", "prefeitura municipal de maringá",
    "câmara de maringá", "câmara municipal de maringá",
    "governo do paraná", "governo do estado do paraná",
    "agência estadual de notícias", "portal da cidade maringá",
    "maringa.pr.gov.br", "cmm.pr.gov.br",
}


def _fonte_permitida(fonte: str) -> bool:
    """Retorna False se a fonte for institucional/governamental."""
    return fonte.lower().strip() not in _FONTES_EXCLUIDAS


def _parse_data_rss(data_str: str) -> tuple[str, str]:
    """
    Converte data do RSS (ex: 'Sat, 05 Apr 2026 14:30:00 GMT')
    para formato legível e ISO.
    """
    try:
        # Formato padrão do Google News RSS
        dt = datetime.strptime(data_str.strip(), "%a, %d %b %Y %H:%M:%S %Z")
        legivel = dt.strftime("%d/%m/%Y %H:%M")
        iso = dt.isoformat()
        return legivel, iso
    except (ValueError, AttributeError):
        return data_str or "Data indisponível", ""


async def _buscar_rss(query: str = "Maringá") -> list[Noticia]:
    """
    Busca notícias no Google News RSS.

    Como funciona: O Google News oferece um feed RSS gratuito que retorna
    as notícias mais recentes para qualquer termo de busca. Não precisa de
    API key, não tem limite de requisições razoável para nosso uso.

    URL: https://news.google.com/rss/search?q=TERMO&hl=pt-BR&gl=BR&ceid=BR:pt-419
    """
    # Monta a URL do RSS — hl=pt-BR garante resultados em português
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query}"
        f"&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Erro ao buscar RSS: {e}")
            return []

    # Parseia o XML do RSS
    try:
        root = ElementTree.fromstring(resp.text)
    except ElementTree.ParseError as e:
        logger.error(f"Erro ao parsear XML: {e}")
        return []

    noticias = []
    # O RSS do Google News segue a estrutura: rss > channel > item
    for item in root.findall(".//item"):
        titulo_raw = item.findtext("title", "")
        link = item.findtext("link", "")
        pub_date = item.findtext("pubDate", "")
        descricao_raw = item.findtext("description", "")

        titulo_limpo, fonte = _extrair_fonte(titulo_raw)

        # Filtra fontes institucionais (prefeitura, câmara, governo)
        # O gestor quer ver o que a imprensa diz, não releases oficiais
        if not _fonte_permitida(fonte):
            continue

        descricao = _limpar_html(descricao_raw)
        data_legivel, data_iso = _parse_data_rss(pub_date)

        noticias.append(Noticia(
            titulo=titulo_limpo,
            link=link,
            fonte=fonte,
            data_publicacao=data_legivel,
            data_iso=data_iso,
            descricao=descricao[:300] if descricao else "",
        ))

    return noticias


# ─── Endpoints ─────────────────────────────────────────────────────────

@router.get("/", response_model=list[Noticia])
async def listar_noticias(
    q: str = Query("Maringá", description="Termo de busca (ex: 'Maringá segurança', 'prefeitura Maringá')"),
    limite: int = Query(30, ge=1, le=100, description="Quantidade máxima de notícias"),
):
    """
    Busca notícias sobre Maringá via Google News RSS.

    Dica pro gestor: Use termos como 'Maringá segurança', 'prefeitura Maringá',
    'Maringá educação' para filtrar por assunto.

    O resultado fica em cache por 10 minutos pra não sobrecarregar o Google.
    """
    global _cache

    # Verifica cache (mesmo query e ainda não expirou)
    now = datetime.utcnow()
    if (
        _cache["data"]
        and _cache["query"] == q
        and _cache["fetched_at"]
        and (now - _cache["fetched_at"]).seconds < CACHE_TTL_SECONDS
    ):
        return _cache["data"][:limite]

    # Busca fresca
    noticias = await _buscar_rss(q)

    # Atualiza cache
    _cache = {"data": noticias, "query": q, "fetched_at": now}

    return noticias[:limite]


@router.post("/resumo", response_model=ResumoResponse)
async def gerar_resumo(payload: ResumoRequest):
    """
    Gera um resumo executivo das notícias usando IA (GPT-4o-mini).

    O gestor seleciona as notícias que quer resumir (ou manda todas do dia),
    e a IA gera um relatório conciso com os principais destaques.
    """
    if not payload.noticias:
        raise HTTPException(status_code=400, detail="Envie pelo menos uma notícia para resumir.")

    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Chave OpenAI não configurada.")

    # Monta o texto das notícias pro prompt
    texto_noticias = "\n".join(
        f"- {n}" for n in payload.noticias[:50]  # Limita a 50 pra não estourar tokens
    )

    prompt = f"""Você é um analista de inteligência da Prefeitura de Maringá-PR.
Analise as seguintes manchetes e notícias do dia e produza um RELATÓRIO EXECUTIVO conciso para o gestor público.

NOTÍCIAS:
{texto_noticias}

FORMATO DO RELATÓRIO:
1. **Resumo Geral** (2-3 frases sobre o panorama do dia)
2. **Destaques Principais** (3-5 pontos mais relevantes para a gestão municipal)
3. **Alertas** (se houver notícias que exijam atenção imediata do gestor — segurança, saúde, infraestrutura)
4. **Sentimento Geral** (positivo, neutro ou negativo em relação à cidade)

Seja objetivo e direto. Use linguagem formal mas acessível. Foque no que impacta a administração pública."""

    # Chama a OpenAI via httpx (sem instalar o SDK da openai — menos uma dependência)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "Você é um analista de inteligência municipal especializado em Maringá-PR."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 1500,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            resumo_texto = data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            logger.error(f"Erro na OpenAI: {e}")
            raise HTTPException(status_code=502, detail="Erro ao gerar resumo com IA. Tente novamente.")
        except (KeyError, IndexError) as e:
            logger.error(f"Resposta inesperada da OpenAI: {e}")
            raise HTTPException(status_code=502, detail="Resposta inesperada da IA.")

    return ResumoResponse(
        resumo=resumo_texto,
        total_noticias=len(payload.noticias),
        gerado_em=datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
    )
