"""
cameras.py · Câmeras próximas da vítima no SOS Mulher

Fluxo: o painel manda o último ponto GPS da vítima, a API devolve as
câmeras AUTORIZADAS mais próximas (tabela `cameras`, migration 029) já
ordenadas, e o navegador toca o vídeo pelo MediaMTX (WebRTC, com HLS de
reserva) usando só o `stream_path`. A `url_stream` (que carrega usuário e
senha do equipamento) nunca sai do servidor.

Rotas públicas do painel (protegidas pelo login, ver main.py):
  GET  /api/cameras/proximas?lat=&lng=&raio=&limite=
  GET  /api/cameras
  POST /api/cameras/visualizacoes        (trilha de auditoria LGPD)

Rota interna (só na rede do Docker, o nginx não publica /internal):
  POST /internal/mediamtx/auth           (MediaMTX pergunta se pode tocar)
"""
from __future__ import annotations

import logging
import math
import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.auth import get_current_user
from app.services.supabase_client import get_supabase

logger = logging.getLogger("api.cameras")

router = APIRouter()
router_interno = APIRouter()

# Prefixos que o nginx do frontend encaminha para o MediaMTX.
WEBRTC_PREFIX = os.environ.get("CAMERAS_WEBRTC_PREFIX", "/cam/webrtc")
HLS_PREFIX = os.environ.get("CAMERAS_HLS_PREFIX", "/cam/hls")
# "auto" = banco, com catálogo demo se a tabela não existir; "demo" = só demo.
FONTE = os.environ.get("CAMERAS_FONTE", "auto").lower()

_CAMPOS_PUBLICOS = (
    "id, nome, descricao, lat, lng, direcao_graus, campo_visao_graus, alcance_m, "
    "tipo, stream_path, orgao_responsavel, convenio_ref, demo"
)

# Catálogo de DEMONSTRAÇÃO, idêntico ao seed da migration 029. Usado quando
# a tabela ainda não existe (ambiente local, banco sem a migration).
# Câmeras fictícias: o vídeo é sinal de teste sintético do MediaMTX.
_DEMO = [
    ("ca000000-0000-4000-a000-000000000001", "DEMO 01 · Jd. Alvorada (sul)", -23.44345, -51.92110, 35, 90, 80, "cam-demo-01"),
    ("ca000000-0000-4000-a000-000000000002", "DEMO 02 · Jd. Alvorada (meio da quadra)", -23.44255, -51.92025, 200, 90, 80, "cam-demo-02"),
    ("ca000000-0000-4000-a000-000000000003", "DEMO 03 · Jd. Alvorada (norte)", -23.44150, -51.91960, 210, 100, 80, "cam-demo-03"),
    ("ca000000-0000-4000-a000-000000000004", "DEMO 04 · Vila Morangueira (sul)", -23.40690, -51.93290, 30, 90, 80, "cam-demo-04"),
    ("ca000000-0000-4000-a000-000000000005", "DEMO 05 · Vila Morangueira (esquina)", -23.40520, -51.93150, 220, 120, 80, "cam-demo-05"),
    ("ca000000-0000-4000-a000-000000000006", "DEMO 06 · Zona 7 (PTZ)", -23.43330, -51.92370, None, None, 120, "cam-demo-06"),
]
CAMERAS_DEMO = [
    {
        "id": i, "nome": n, "descricao": "Câmera fictícia de demonstração. Sinal de teste sintético.",
        "lat": la, "lng": lo, "direcao_graus": d, "campo_visao_graus": f, "alcance_m": a,
        "tipo": "demo", "stream_path": p, "orgao_responsavel": "Demonstração Node Data",
        "convenio_ref": "DEMO (sem convênio, câmera inexistente)", "demo": True,
    }
    for (i, n, la, lo, d, f, a, p) in _DEMO
]


# ── Geometria ────────────────────────────────────────────────

def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _rumo_graus(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Azimute de (lat1,lng1) para (lat2,lng2). 0 = norte, 90 = leste."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _avaliar(cam: dict, lat: float, lng: float) -> dict:
    """Distância, se o ponto cai no cone de visão e a nota de prioridade."""
    dist = _haversine_m(cam["lat"], cam["lng"], lat, lng)
    rumo = _rumo_graus(cam["lat"], cam["lng"], lat, lng)
    direcao, fov = cam.get("direcao_graus"), cam.get("campo_visao_graus")
    no_campo = None
    if direcao is not None and fov:
        diff = abs((rumo - direcao + 180) % 360 - 180)
        no_campo = diff <= fov / 2 or dist < 8  # colado na câmera conta como visível
    alcance = cam.get("alcance_m") or 60
    # Nota menor = melhor. Câmera apontada para a vítima e dentro do alcance
    # vale mais que uma um pouco mais perto mas de costas.
    nota = dist
    if no_campo is True:
        nota *= 0.6 if dist <= alcance else 0.85
    elif no_campo is False:
        nota *= 1.25
    elif cam.get("tipo") == "ptz":
        nota *= 0.9  # PTZ pode ser girada pelo operador do órgão responsável
    return {
        "distancia_m": round(dist, 1),
        "rumo_graus": round(rumo),
        "no_campo_visao": no_campo,
        "dentro_alcance": dist <= alcance,
        "nota": round(nota, 1),
    }


def _publico(cam: dict, extra: dict) -> dict:
    path = cam.get("stream_path")
    return {
        **{k: cam.get(k) for k in (
            "id", "nome", "descricao", "lat", "lng", "direcao_graus", "campo_visao_graus",
            "alcance_m", "tipo", "orgao_responsavel", "convenio_ref", "demo",
        )},
        **extra,
        "stream": {
            "path": path,
            "webrtc": f"{WEBRTC_PREFIX}/{path}/whep" if path else None,
            "hls": f"{HLS_PREFIX}/{path}/index.m3u8" if path else None,
        },
    }


# ── Leitura do cadastro ──────────────────────────────────────

def _caixa(lat: float, lng: float, raio_m: float) -> tuple[float, float, float, float]:
    dlat = raio_m / 111320.0
    dlng = raio_m / (111320.0 * max(0.01, math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def _candidatas(lat: float, lng: float, raio_m: float) -> tuple[list[dict], str]:
    """Câmeras ativas dentro da caixa do raio. Devolve (lista, fonte)."""
    la0, la1, lo0, lo1 = _caixa(lat, lng, raio_m)
    if FONTE != "demo":
        try:
            res = (
                get_supabase().table("cameras").select(_CAMPOS_PUBLICOS)
                .eq("ativo", True)
                .gte("lat", la0).lte("lat", la1)
                .gte("lng", lo0).lte("lng", lo1)
                .limit(500).execute()
            )
            return res.data or [], "banco"
        except Exception as e:  # tabela ausente, banco fora do ar
            logger.warning("cameras: usando catálogo demo (%s)", type(e).__name__)
    dentro = [c for c in CAMERAS_DEMO if la0 <= c["lat"] <= la1 and lo0 <= c["lng"] <= lo1]
    return dentro, "demo_local"


# ── Limitação de finalidade ──────────────────────────────────
# Com CAMERAS_EXIGIR_ALERTA=true, a busca de câmeras só funciona quando vem
# amarrada a um alerta SOS ativo ou em atendimento. Fecha a porta para usar
# o painel como "olho" genérico sobre a cidade. Desligado por padrão para o
# protótipo rodar sem banco.
EXIGIR_ALERTA = os.environ.get("CAMERAS_EXIGIR_ALERTA", "false").lower() == "true"


def _exigir_alerta_ativo(alerta_id: str | None) -> None:
    if not alerta_id:
        raise HTTPException(status_code=403, detail="Câmeras só podem ser abertas a partir de um alerta SOS.")
    try:
        res = get_supabase().table("sos_alertas").select("status").eq("id", alerta_id).limit(1).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Não foi possível validar o alerta.")
    if not res.data or res.data[0].get("status") not in ("active", "attending"):
        raise HTTPException(status_code=403, detail="Alerta encerrado ou inexistente: câmeras bloqueadas.")


# ── Rotas do painel ──────────────────────────────────────────

@router.get("/proximas")
def cameras_proximas(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    raio: int = Query(300, ge=20, le=5000, description="Raio em metros"),
    limite: int = Query(4, ge=1, le=8),
    alerta_id: str | None = Query(None, description="Alerta SOS que justifica a consulta"),
):
    """Câmeras autorizadas mais próximas do ponto, da melhor para a pior."""
    if EXIGIR_ALERTA:
        # Limitação de finalidade (LGPD): câmera só abre com SOS em andamento.
        _exigir_alerta_ativo(alerta_id)
    cands, fonte = _candidatas(lat, lng, raio)
    avaliadas = []
    for c in cands:
        ev = _avaliar(c, lat, lng)
        if ev["distancia_m"] <= raio:
            avaliadas.append(_publico(c, ev))
    avaliadas.sort(key=lambda c: c["nota"])

    mais_proxima_fora = None
    if not avaliadas:
        # Nada no raio: avisa o operador qual é a mais perto, até 5 km.
        cands2, _ = _candidatas(lat, lng, 5000)
        if cands2:
            melhor = min(cands2, key=lambda c: _haversine_m(c["lat"], c["lng"], lat, lng))
            mais_proxima_fora = _publico(melhor, _avaliar(melhor, lat, lng))

    return {
        "ponto": {"lat": lat, "lng": lng},
        "raio_m": raio,
        "fonte": fonte,
        "cameras": avaliadas[:limite],
        "total_no_raio": len(avaliadas),
        "mais_proxima_fora_do_raio": mais_proxima_fora,
    }


@router.get("/")
def listar_cameras():
    """Todas as câmeras ativas (sem url_stream), para a camada do mapa."""
    if FONTE != "demo":
        try:
            res = get_supabase().table("cameras").select(_CAMPOS_PUBLICOS).eq("ativo", True).limit(5000).execute()
            return [_publico(c, {}) for c in (res.data or [])]
        except Exception as e:
            logger.warning("cameras: lista demo (%s)", type(e).__name__)
    return [_publico(c, {}) for c in CAMERAS_DEMO]


@router.post("/visualizacoes")
def registrar_visualizacao(body: dict, request: Request, user: dict = Depends(get_current_user)):
    """Registra no audit_log que o operador abriu (ou fechou) o vídeo de uma
    câmera durante um SOS. Responde a pergunta da LGPD: quem viu o quê, quando
    e por qual motivo (o alerta)."""
    camera_id = body.get("camera_id")
    if not camera_id:
        raise HTTPException(status_code=422, detail="camera_id obrigatório")
    evento = body.get("evento") or "inicio"
    if evento not in ("inicio", "fim"):
        raise HTTPException(status_code=422, detail="evento deve ser 'inicio' ou 'fim'")
    try:
        get_supabase().table("audit_log").insert({
            "tabela": "cameras",
            "registro_id": camera_id,
            "acao": "view_stream" if evento == "inicio" else "view_stream_end",
            "operador": user.get("email") or user.get("nome"),
            "dados_depois": {
                "alerta_id": body.get("alerta_id"),
                "lat": body.get("lat"),
                "lng": body.get("lng"),
                "distancia_m": body.get("distancia_m"),
                "finalidade": "atendimento SOS Mulher",
            },
            "ip": request.client.host if request.client else None,
        }).execute()
        return {"ok": True}
    except Exception as e:
        # Não derruba o vídeo por falha de auditoria, mas avisa o painel.
        logger.error("cameras: falha ao gravar audit_log (%s)", type(e).__name__)
        return {"ok": False}


# ── Autorização do MediaMTX (rede interna) ───────────────────
# Com MTX_AUTHMETHOD=http, o MediaMTX pergunta aqui antes de entregar vídeo.
# Corpo enviado por ele: user, password, token, ip, action, path, protocol,
# id, query, userAgent. 2xx = libera.

_TOKENS_OK: dict[str, float] = {}
_TTL_TOKEN = 60.0


def _token_valido(token: str) -> bool:
    agora = time.time()
    exp = _TOKENS_OK.get(token)
    if exp and exp > agora:
        return True
    try:
        get_current_user(f"Bearer {token}")
    except HTTPException:
        return False
    if len(_TOKENS_OK) > 2000:
        _TOKENS_OK.clear()
    _TOKENS_OK[token] = agora + _TTL_TOKEN
    return True


@router_interno.post("/internal/mediamtx/auth")
def mediamtx_auth(body: dict):
    acao = body.get("action")
    ip = body.get("ip") or ""
    path = body.get("path") or ""
    # O ffmpeg do sinal de teste publica de dentro do próprio container.
    if acao == "publish":
        if ip in ("127.0.0.1", "::1") and path.startswith("cam-demo-"):
            return Response(status_code=204)
        raise HTTPException(status_code=403)
    if acao == "read":
        token = body.get("token") or body.get("password") or ""
        if not token:
            q = body.get("query") or ""
            for parte in q.split("&"):
                if parte.startswith("token="):
                    token = parte[6:]
        # Com AUTH_ENABLED=false, get_current_user libera (modo demo).
        if _token_valido(token):
            return Response(status_code=204)
        raise HTTPException(status_code=401)
    raise HTTPException(status_code=403)
