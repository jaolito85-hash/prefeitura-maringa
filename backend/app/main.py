"""
main.py — Ponto de entrada do servidor FastAPI
Para rodar: uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import denuncias, ocorrencias, sos, dashboard, feedbacks, recompensas
from app.webhooks import denuncias as wh_denuncias
from app.webhooks import sos_mulher as wh_sos
from app.webhooks import ocorrencias as wh_ocorrencias
from app.webhooks import unificado as wh_unificado

app = FastAPI(
    title="Node Data Maringá — API",
    description="Plataforma de Segurança Pública — Prefeitura de Maringá",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
)

# CORS — Permite que o dashboard React acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "https://dashboard.seudominio.com.br"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Rotas REST (usadas pelo Dashboard) ----
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(denuncias.router, prefix="/api/denuncias", tags=["Denúncias"])
app.include_router(ocorrencias.router, prefix="/api/ocorrencias", tags=["Ocorrências"])
app.include_router(sos.router, prefix="/api/sos", tags=["SOS Mulher"])
app.include_router(feedbacks.router, prefix="/api/feedbacks", tags=["Feedbacks"])
app.include_router(recompensas.router, prefix="/api/recompensas", tags=["Recompensas"])

# ---- Webhook UNIFICADO (demo com numero unico — IA classifica tudo) ----
app.include_router(wh_unificado.router, prefix="/webhook", tags=["Webhook Unificado"])

# ---- Webhooks por canal (producao com 3 numeros separados) ----
app.include_router(wh_denuncias.router, prefix="/webhook", tags=["Webhooks"])
app.include_router(wh_sos.router, prefix="/webhook", tags=["Webhooks"])
app.include_router(wh_ocorrencias.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/health")
async def health_check():
    """Verifica se o servidor está vivo. Usado pelo UptimeRobot."""
    return {"status": "ok", "service": "Node Data Maringá", "version": "2.0.0"}
