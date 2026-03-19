"""
main.py — Ponto de entrada do servidor FastAPI
Para rodar: uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import denuncias, ocorrencias, sos, dashboard
from app.webhooks import denuncias as wh_denuncias
from app.webhooks import sos_mulher as wh_sos
from app.webhooks import ocorrencias as wh_ocorrencias

app = FastAPI(
    title="Node Data Maringá — API",
    description="Plataforma de Segurança Pública — Prefeitura de Maringá",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # Desativa docs em produção
)

# CORS — Permite que o dashboard React acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://dashboard.seudominio.com.br"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Rotas REST (usadas pelo Dashboard) ----
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
app.include_router(denuncias.router, prefix="/api/denuncias", tags=["Denúncias"])
app.include_router(ocorrencias.router, prefix="/api/ocorrencias", tags=["Ocorrências"])
app.include_router(sos.router, prefix="/api/sos", tags=["SOS Mulher"])

# ---- Webhooks (recebem mensagens do WhatsApp via Evolution API) ----
app.include_router(wh_denuncias.router, prefix="/webhook", tags=["Webhooks"])
app.include_router(wh_sos.router, prefix="/webhook", tags=["Webhooks"])
app.include_router(wh_ocorrencias.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/health")
async def health_check():
    """Verifica se o servidor está vivo. Usado pelo UptimeRobot."""
    return {"status": "ok", "service": "Node Data Maringá"}
