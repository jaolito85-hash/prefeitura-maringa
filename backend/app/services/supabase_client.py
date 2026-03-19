"""
supabase_client.py — Conexão com o Supabase
Cria um cliente único que é reutilizado em toda a aplicação (singleton)
"""
from supabase import create_client, Client
from app.config import settings

# Cria o cliente uma vez e reutiliza
_client: Client = None


def get_supabase() -> Client:
    """Retorna o cliente Supabase. Cria se ainda não existe."""
    global _client
    if _client is None:
        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_key  # Service key tem acesso total (usar só no backend!)
        )
    return _client
